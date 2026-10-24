use std::ffi::{c_int, c_void};
use std::ptr;
use std::sync::atomic::{compiler_fence, Ordering};

const KEY_BYTES: usize = 32;
const SALT_BYTES: usize = 16;
const NONCE_BYTES: usize = 12;
const TAG_BYTES: usize = 16;
const SCRYPT_N: u64 = 1 << 15;
const SCRYPT_R: u64 = 8;
const SCRYPT_P: u64 = 1;
const SCRYPT_MAX_MEMORY: u64 = 64 * 1024 * 1024;
const EVP_CTRL_GCM_SET_IVLEN: c_int = 0x9;
const EVP_CTRL_GCM_GET_TAG: c_int = 0x10;
const EVP_CTRL_GCM_SET_TAG: c_int = 0x11;

#[link(name = "crypto")]
unsafe extern "C" {
    fn RAND_bytes(buffer: *mut u8, length: c_int) -> c_int;
    fn EVP_PBE_scrypt(
        password: *const i8,
        password_length: usize,
        salt: *const u8,
        salt_length: usize,
        n: u64,
        r: u64,
        p: u64,
        max_memory: u64,
        key: *mut u8,
        key_length: usize,
    ) -> c_int;
    fn EVP_CIPHER_CTX_new() -> *mut c_void;
    fn EVP_CIPHER_CTX_free(context: *mut c_void);
    fn EVP_aes_256_gcm() -> *const c_void;
    fn EVP_CIPHER_CTX_ctrl(
        context: *mut c_void,
        command: c_int,
        argument: c_int,
        data: *mut c_void,
    ) -> c_int;
    fn EVP_EncryptInit_ex(
        context: *mut c_void,
        cipher: *const c_void,
        implementation: *mut c_void,
        key: *const u8,
        nonce: *const u8,
    ) -> c_int;
    fn EVP_EncryptUpdate(
        context: *mut c_void,
        output: *mut u8,
        output_length: *mut c_int,
        input: *const u8,
        input_length: c_int,
    ) -> c_int;
    fn EVP_EncryptFinal_ex(
        context: *mut c_void,
        output: *mut u8,
        output_length: *mut c_int,
    ) -> c_int;
    fn EVP_DecryptInit_ex(
        context: *mut c_void,
        cipher: *const c_void,
        implementation: *mut c_void,
        key: *const u8,
        nonce: *const u8,
    ) -> c_int;
    fn EVP_DecryptUpdate(
        context: *mut c_void,
        output: *mut u8,
        output_length: *mut c_int,
        input: *const u8,
        input_length: c_int,
    ) -> c_int;
    fn EVP_DecryptFinal_ex(
        context: *mut c_void,
        output: *mut u8,
        output_length: *mut c_int,
    ) -> c_int;
}

pub struct SecretKey([u8; KEY_BYTES]);

impl SecretKey {
    pub fn bytes(&self) -> &[u8; KEY_BYTES] {
        &self.0
    }
}

impl Drop for SecretKey {
    fn drop(&mut self) {
        wipe(&mut self.0);
    }
}

pub fn wipe(bytes: &mut [u8]) {
    for byte in bytes {
        unsafe { ptr::write_volatile(byte, 0) };
    }
    compiler_fence(Ordering::SeqCst);
}

pub fn random_bytes<const N: usize>() -> Result<[u8; N], String> {
    if N > c_int::MAX as usize {
        return Err("random buffer is too large".into());
    }
    let mut bytes = [0u8; N];
    let result = unsafe { RAND_bytes(bytes.as_mut_ptr(), N as c_int) };
    if result != 1 {
        wipe(&mut bytes);
        return Err("OpenSSL random generator failed".into());
    }
    Ok(bytes)
}

pub fn derive_key(passphrase: &str, salt: &[u8; SALT_BYTES]) -> Result<SecretKey, String> {
    if passphrase.len() < 12 || passphrase.len() > 1024 {
        return Err("passphrase must contain between 12 and 1024 bytes".into());
    }
    let mut key = SecretKey([0u8; KEY_BYTES]);
    let result = unsafe {
        EVP_PBE_scrypt(
            passphrase.as_ptr() as *const i8,
            passphrase.len(),
            salt.as_ptr(),
            salt.len(),
            SCRYPT_N,
            SCRYPT_R,
            SCRYPT_P,
            SCRYPT_MAX_MEMORY,
            key.0.as_mut_ptr(),
            key.0.len(),
        )
    };
    if result != 1 {
        return Err("OpenSSL scrypt key derivation failed".into());
    }
    Ok(key)
}

struct CipherContext(*mut c_void);

impl CipherContext {
    fn new() -> Result<Self, String> {
        let context = unsafe { EVP_CIPHER_CTX_new() };
        if context.is_null() {
            Err("OpenSSL could not allocate a cipher context".into())
        } else {
            Ok(Self(context))
        }
    }
}

impl Drop for CipherContext {
    fn drop(&mut self) {
        unsafe { EVP_CIPHER_CTX_free(self.0) }
    }
}

fn checked_length(length: usize) -> Result<c_int, String> {
    c_int::try_from(length).map_err(|_| "encrypted field exceeds OpenSSL's input limit".into())
}

pub fn encrypt(
    key: &SecretKey,
    nonce: &[u8; NONCE_BYTES],
    associated_data: &[u8],
    plaintext: &[u8],
) -> Result<Vec<u8>, String> {
    let aad_length = checked_length(associated_data.len())?;
    let plaintext_length = checked_length(plaintext.len())?;
    let context = CipherContext::new()?;
    let cipher = unsafe { EVP_aes_256_gcm() };
    if cipher.is_null() {
        return Err("AES-256-GCM is unavailable".into());
    }
    let initialized =
        unsafe { EVP_EncryptInit_ex(context.0, cipher, ptr::null_mut(), ptr::null(), ptr::null()) };
    if initialized != 1 {
        return Err("OpenSSL cipher initialization failed".into());
    }
    if unsafe {
        EVP_CIPHER_CTX_ctrl(
            context.0,
            EVP_CTRL_GCM_SET_IVLEN,
            NONCE_BYTES as c_int,
            ptr::null_mut(),
        )
    } != 1
    {
        return Err("OpenSSL nonce configuration failed".into());
    }
    if unsafe {
        EVP_EncryptInit_ex(
            context.0,
            ptr::null(),
            ptr::null_mut(),
            key.bytes().as_ptr(),
            nonce.as_ptr(),
        )
    } != 1
    {
        return Err("OpenSSL key initialization failed".into());
    }
    let mut ignored = 0;
    if !associated_data.is_empty()
        && unsafe {
            EVP_EncryptUpdate(
                context.0,
                ptr::null_mut(),
                &mut ignored,
                associated_data.as_ptr(),
                aad_length,
            )
        } != 1
    {
        return Err("OpenSSL authentication-data processing failed".into());
    }
    let mut ciphertext = vec![0u8; plaintext.len().saturating_add(TAG_BYTES).saturating_add(16)];
    let mut written = 0;
    let input = if plaintext.is_empty() {
        [0u8].as_ptr()
    } else {
        plaintext.as_ptr()
    };
    if unsafe {
        EVP_EncryptUpdate(
            context.0,
            ciphertext.as_mut_ptr(),
            &mut written,
            input,
            plaintext_length,
        )
    } != 1
    {
        wipe(&mut ciphertext);
        return Err("OpenSSL encryption failed".into());
    }
    let mut final_length = 0;
    if unsafe {
        EVP_EncryptFinal_ex(
            context.0,
            ciphertext.as_mut_ptr().add(written as usize),
            &mut final_length,
        )
    } != 1
    {
        wipe(&mut ciphertext);
        return Err("OpenSSL encryption finalization failed".into());
    }
    let ciphertext_length = (written + final_length) as usize;
    ciphertext.truncate(ciphertext_length + TAG_BYTES);
    if unsafe {
        EVP_CIPHER_CTX_ctrl(
            context.0,
            EVP_CTRL_GCM_GET_TAG,
            TAG_BYTES as c_int,
            ciphertext.as_mut_ptr().add(ciphertext_length).cast(),
        )
    } != 1
    {
        wipe(&mut ciphertext);
        return Err("OpenSSL authentication-tag generation failed".into());
    }
    Ok(ciphertext)
}

pub fn decrypt(
    key: &SecretKey,
    nonce: &[u8; NONCE_BYTES],
    associated_data: &[u8],
    ciphertext_and_tag: &[u8],
) -> Result<Vec<u8>, String> {
    if ciphertext_and_tag.len() < TAG_BYTES {
        return Err("encrypted data is truncated".into());
    }
    let aad_length = checked_length(associated_data.len())?;
    let ciphertext_length = ciphertext_and_tag.len() - TAG_BYTES;
    let data_length = checked_length(ciphertext_length)?;
    let context = CipherContext::new()?;
    let cipher = unsafe { EVP_aes_256_gcm() };
    if cipher.is_null() {
        return Err("AES-256-GCM is unavailable".into());
    }
    if unsafe { EVP_DecryptInit_ex(context.0, cipher, ptr::null_mut(), ptr::null(), ptr::null()) }
        != 1
    {
        return Err("OpenSSL cipher initialization failed".into());
    }
    if unsafe {
        EVP_CIPHER_CTX_ctrl(
            context.0,
            EVP_CTRL_GCM_SET_IVLEN,
            NONCE_BYTES as c_int,
            ptr::null_mut(),
        )
    } != 1
    {
        return Err("OpenSSL nonce configuration failed".into());
    }
    if unsafe {
        EVP_DecryptInit_ex(
            context.0,
            ptr::null(),
            ptr::null_mut(),
            key.bytes().as_ptr(),
            nonce.as_ptr(),
        )
    } != 1
    {
        return Err("OpenSSL key initialization failed".into());
    }
    let mut ignored = 0;
    if !associated_data.is_empty()
        && unsafe {
            EVP_DecryptUpdate(
                context.0,
                ptr::null_mut(),
                &mut ignored,
                associated_data.as_ptr(),
                aad_length,
            )
        } != 1
    {
        return Err("OpenSSL authentication-data processing failed".into());
    }
    let mut plaintext = vec![0u8; ciphertext_length.saturating_add(16)];
    let input = if ciphertext_length == 0 {
        [0u8].as_ptr()
    } else {
        ciphertext_and_tag.as_ptr()
    };
    let mut written = 0;
    if unsafe {
        EVP_DecryptUpdate(
            context.0,
            plaintext.as_mut_ptr(),
            &mut written,
            input,
            data_length,
        )
    } != 1
    {
        wipe(&mut plaintext);
        return Err("OpenSSL decryption failed".into());
    }
    let tag_pointer = unsafe { ciphertext_and_tag.as_ptr().add(ciphertext_length) as *mut c_void };
    if unsafe {
        EVP_CIPHER_CTX_ctrl(
            context.0,
            EVP_CTRL_GCM_SET_TAG,
            TAG_BYTES as c_int,
            tag_pointer,
        )
    } != 1
    {
        wipe(&mut plaintext);
        return Err("OpenSSL authentication-tag setup failed".into());
    }
    let mut final_length = 0;
    if unsafe {
        EVP_DecryptFinal_ex(
            context.0,
            plaintext.as_mut_ptr().add(written as usize),
            &mut final_length,
        )
    } != 1
    {
        wipe(&mut plaintext);
        return Err("vault authentication failed (wrong passphrase or modified data)".into());
    }
    plaintext.truncate((written + final_length) as usize);
    Ok(plaintext)
}

const _: [(); SALT_BYTES] = [(); 16];

#[cfg(test)]
mod tests {
    use super::{decrypt, derive_key, encrypt, random_bytes};

    #[test]
    fn authenticated_encryption_round_trips_and_rejects_modification() {
        let salt = random_bytes::<16>().expect("salt");
        let nonce = random_bytes::<12>().expect("nonce");
        let key = derive_key("a-long-synthetic-passphrase", &salt).expect("key");
        let encrypted =
            encrypt(&key, &nonce, b"entry:v1:test-id", b"synthetic secret").expect("encrypt");
        assert_ne!(encrypted, b"synthetic secret");
        assert_eq!(
            decrypt(&key, &nonce, b"entry:v1:test-id", &encrypted).expect("decrypt"),
            b"synthetic secret"
        );
        assert!(decrypt(&key, &nonce, b"entry:v1:other-id", &encrypted).is_err());
        let mut altered = encrypted;
        altered[0] ^= 1;
        assert!(decrypt(&key, &nonce, b"entry:v1:test-id", &altered).is_err());
    }

    #[test]
    fn rejects_short_passphrases() {
        let salt = [1u8; 16];
        assert!(derive_key("too-short", &salt).is_err());
    }
}
