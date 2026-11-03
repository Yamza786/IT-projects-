use crate::crypto::{decrypt, encrypt, random_bytes, wipe, SecretKey};
use crate::sqlite::Connection;
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::Path;

const SCHEMA: &str = include_str!("../migrations/001_initial.sql");
const VERIFIER: &[u8] = b"vaultsmith verifier v1";
const VERIFIER_AAD: &[u8] = b"vaultsmith:verifier:v1";
const NONCE_BYTES: usize = 12;
const MAX_SERVICE_BYTES: usize = 120;
const MAX_USERNAME_BYTES: usize = 512;
const MAX_PASSWORD_BYTES: usize = 4096;
const BACKUP_MAGIC: &[u8] = b"VSBK\x01";
const BACKUP_AAD: &[u8] = b"vaultsmith:backup:v1";
const MAX_BACKUP_BYTES: usize = 4 * 1024 * 1024;

struct SecretBuffer(Vec<u8>);

impl Drop for SecretBuffer {
    fn drop(&mut self) {
        wipe(&mut self.0);
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EntrySummary {
    pub id: String,
    pub service: String,
    pub created_at: String,
}

#[derive(PartialEq, Eq)]
pub struct EntrySecret {
    pub service: String,
    pub username: String,
    pub password: String,
}

impl Drop for EntrySecret {
    fn drop(&mut self) {
        wipe(unsafe { self.service.as_bytes_mut() });
        wipe(unsafe { self.username.as_bytes_mut() });
        wipe(unsafe { self.password.as_bytes_mut() });
    }
}

pub fn open_database(path: &str) -> Result<Connection, String> {
    if path.is_empty() {
        return Err("database path cannot be empty".into());
    }
    prepare_database_path(path)?;
    set_private_file_permissions(path)?;
    let connection = Connection::open(path)?;
    let version = connection.user_version()?;
    match version {
        0 => {
            connection.execute("BEGIN IMMEDIATE")?;
            if let Err(error) = connection.execute(SCHEMA) {
                let _ = connection.execute("ROLLBACK");
                return Err(error);
            }
            connection.execute("COMMIT")?;
        }
        1 => {}
        other => {
            return Err(format!(
                "database schema version {other} is newer than this application"
            ))
        }
    }
    if connection.user_version()? != 1 {
        return Err("database migration did not set schema version 1".into());
    }
    Ok(connection)
}

#[cfg(unix)]
fn prepare_database_path(path: &str) -> Result<(), String> {
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
    if path == ":memory:" {
        return Ok(());
    }
    let database = Path::new(path);
    if let Ok(metadata) = fs::symlink_metadata(database) {
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err("database path must be a regular file, not a symlink".into());
        }
    }
    if let Some(parent) = database.parent() {
        if !parent.as_os_str().is_empty() && !parent.exists() {
            fs::create_dir_all(parent)
                .map_err(|error| format!("create database directory: {error}"))?;
            fs::set_permissions(parent, fs::Permissions::from_mode(0o700))
                .map_err(|error| format!("secure database directory: {error}"))?;
        }
    }
    if !database.exists() {
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(database)
            .map_err(|error| format!("create private database file: {error}"))?;
    }
    let metadata = fs::symlink_metadata(database)
        .map_err(|error| format!("inspect database file: {error}"))?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err("database path must be a regular file, not a symlink".into());
    }
    Ok(())
}

#[cfg(not(unix))]
fn prepare_database_path(path: &str) -> Result<(), String> {
    if path == ":memory:" {
        return Ok(());
    }
    let database = Path::new(path);
    if let Ok(metadata) = fs::symlink_metadata(database) {
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err("database path must be a regular file, not a symlink".into());
        }
    }
    if let Some(parent) = database.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create database directory: {error}"))?;
    }
    if !database.exists() {
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(database)
            .map_err(|error| format!("create database file: {error}"))?;
    }
    Ok(())
}

#[cfg(unix)]
fn set_private_file_permissions(path: &str) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    if path != ":memory:" {
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))
            .map_err(|error| format!("secure database permissions: {error}"))?;
    }
    Ok(())
}

#[cfg(not(unix))]
fn set_private_file_permissions(_path: &str) -> Result<(), String> {
    Ok(())
}

pub fn create_vault(connection: &Connection, passphrase: &str) -> Result<(), String> {
    let existing = connection.prepare("SELECT 1 FROM vault_metadata WHERE id = 1")?;
    let mut existing = existing;
    if existing.step()? {
        return Err("vault is already initialized".into());
    }

    connection.execute("BEGIN IMMEDIATE")?;
    let result = (|| {
        let salt = random_bytes::<16>()?;
        let key = crate::crypto::derive_key(passphrase, &salt)?;
        let nonce = random_bytes::<NONCE_BYTES>()?;
        let ciphertext = encrypt(&key, &nonce, VERIFIER_AAD, VERIFIER)?;
        let mut statement = connection.prepare("INSERT INTO vault_metadata (id, format_version, salt, verifier_nonce, verifier_ciphertext) VALUES (1, 1, ?, ?, ?)")?;
        statement.bind_blob(1, &salt)?;
        statement.bind_blob(2, &nonce)?;
        statement.bind_blob(3, &ciphertext)?;
        if statement.step()? {
            return Err("metadata insert returned unexpected row".into());
        }
        Ok(())
    })();
    match result {
        Ok(()) => connection.execute("COMMIT"),
        Err(error) => {
            let _ = connection.execute("ROLLBACK");
            Err(error)
        }
    }
}

pub fn unlock(connection: &Connection, passphrase: &str) -> Result<SecretKey, String> {
    let mut statement = connection.prepare("SELECT format_version, salt, verifier_nonce, verifier_ciphertext FROM vault_metadata WHERE id = 1")?;
    if !statement.step()? {
        return Err("vault is not initialized; run `vaultsmith init` first".into());
    }
    if statement.integer(0) != 1 {
        return Err("unsupported vault data format".into());
    }
    let salt = fixed::<16>(statement.blob(1)?, "salt")?;
    let nonce = fixed::<NONCE_BYTES>(statement.blob(2)?, "verification nonce")?;
    let ciphertext = statement.blob(3)?;
    let key = crate::crypto::derive_key(passphrase, &salt)?;
    let mut verifier = decrypt(&key, &nonce, VERIFIER_AAD, &ciphertext)
        .map_err(|_| "vault unlock failed: incorrect passphrase or damaged metadata".to_string())?;
    let valid = verifier == VERIFIER;
    wipe(&mut verifier);
    if !valid {
        return Err("vault unlock failed: incorrect passphrase or damaged metadata".into());
    }
    Ok(key)
}

pub fn add_entry(
    connection: &Connection,
    key: &SecretKey,
    service: &str,
    username: &str,
    password: &str,
) -> Result<String, String> {
    validate_field("service", service, 1, MAX_SERVICE_BYTES)?;
    validate_field("username", username, 1, MAX_USERNAME_BYTES)?;
    validate_field("password", password, 1, MAX_PASSWORD_BYTES)?;
    let id = uuid_v4()?;
    let nonce = random_bytes::<NONCE_BYTES>()?;
    let mut payload = Vec::with_capacity(4 + username.len() + password.len());
    payload.extend_from_slice(&(username.len() as u32).to_be_bytes());
    payload.extend_from_slice(username.as_bytes());
    payload.extend_from_slice(password.as_bytes());
    let associated_data = format!("vaultsmith:entry:v1:{id}:{service}");
    let ciphertext = encrypt(key, &nonce, associated_data.as_bytes(), &payload);
    wipe(&mut payload);
    let ciphertext = ciphertext?;
    let mut statement = connection
        .prepare("INSERT INTO entries (id, service, nonce, ciphertext) VALUES (?, ?, ?, ?)")?;
    statement.bind_text(1, &id)?;
    statement.bind_text(2, service)?;
    statement.bind_blob(3, &nonce)?;
    statement.bind_blob(4, &ciphertext)?;
    if statement.step()? {
        return Err("entry insert returned unexpected row".into());
    }
    Ok(id)
}

pub fn list_entries(connection: &Connection) -> Result<Vec<EntrySummary>, String> {
    let mut statement = connection.prepare(
        "SELECT id, service, created_at FROM entries ORDER BY service COLLATE NOCASE, id",
    )?;
    let mut entries = Vec::new();
    while statement.step()? {
        entries.push(EntrySummary {
            id: statement.text(0)?,
            service: statement.text(1)?,
            created_at: statement.text(2)?,
        });
    }
    Ok(entries)
}

pub fn read_entry(
    connection: &Connection,
    key: &SecretKey,
    id: &str,
) -> Result<EntrySecret, String> {
    validate_field("entry id", id, 1, 64)?;
    let mut statement =
        connection.prepare("SELECT service, nonce, ciphertext FROM entries WHERE id = ?")?;
    statement.bind_text(1, id)?;
    if !statement.step()? {
        return Err("entry not found".into());
    }
    let service = statement.text(0)?;
    let nonce = fixed::<NONCE_BYTES>(statement.blob(1)?, "entry nonce")?;
    let ciphertext = statement.blob(2)?;
    let associated_data = format!("vaultsmith:entry:v1:{id}:{service}");
    let mut payload = decrypt(key, &nonce, associated_data.as_bytes(), &ciphertext)?;
    let decoded = decode_payload(&payload);
    wipe(&mut payload);
    let (username, password) = decoded?;
    Ok(EntrySecret {
        service,
        username,
        password,
    })
}

pub fn remove_entry(connection: &Connection, id: &str) -> Result<bool, String> {
    validate_field("entry id", id, 1, 64)?;
    let mut statement = connection.prepare("DELETE FROM entries WHERE id = ?")?;
    statement.bind_text(1, id)?;
    if statement.step()? {
        return Err("entry removal returned unexpected row".into());
    }
    Ok(connection.changes() == 1)
}

/// Write a portable AES-GCM encrypted backup using a separately derived backup passphrase.
/// The target is created exclusively with private permissions and is never overwritten.
pub fn export_backup(
    connection: &Connection,
    vault_key: &SecretKey,
    backup_passphrase: &str,
    path: &str,
) -> Result<usize, String> {
    if backup_passphrase.len() < 12 || backup_passphrase.len() > 1024 {
        return Err("backup passphrase must contain 12..=1024 bytes".into());
    }
    let entries = list_entries(connection)?;
    if entries.len() > 10_000 {
        return Err("backup exceeds 10,000 entries".into());
    }
    let mut plaintext = SecretBuffer(Vec::new());
    plaintext
        .0
        .extend_from_slice(&(entries.len() as u32).to_be_bytes());
    for summary in &entries {
        let entry = read_entry(connection, vault_key, &summary.id)?;
        for field in [&entry.service, &entry.username, &entry.password] {
            let length = u16::try_from(field.len()).map_err(|_| "backup field is too large")?;
            plaintext.0.extend_from_slice(&length.to_be_bytes());
            plaintext.0.extend_from_slice(field.as_bytes());
        }
        if plaintext.0.len() > MAX_BACKUP_BYTES {
            return Err("backup exceeds 4 MiB".into());
        }
    }
    let salt = random_bytes::<16>()?;
    let key = crate::crypto::derive_key(backup_passphrase, &salt)?;
    let nonce = random_bytes::<NONCE_BYTES>()?;
    let encrypted = encrypt(&key, &nonce, BACKUP_AAD, &plaintext.0);
    let ciphertext = encrypted?;
    let mut bytes =
        Vec::with_capacity(BACKUP_MAGIC.len() + salt.len() + nonce.len() + ciphertext.len());
    bytes.extend_from_slice(BACKUP_MAGIC);
    bytes.extend_from_slice(&salt);
    bytes.extend_from_slice(&nonce);
    bytes.extend_from_slice(&ciphertext);

    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = match options.open(path) {
        Ok(file) => file,
        Err(error) => {
            wipe(&mut bytes);
            return Err(format!("create encrypted backup: {error}"));
        }
    };
    let write_result = (|| {
        file.write_all(&bytes)
            .map_err(|error| format!("write encrypted backup: {error}"))?;
        file.sync_all()
            .map_err(|error| format!("sync encrypted backup: {error}"))?;
        Ok(())
    })();
    wipe(&mut bytes);
    if let Err(error) = write_result {
        let _ = fs::remove_file(path);
        return Err(error);
    }
    Ok(entries.len())
}

/// Restore backup records and re-encrypt them under the destination vault key atomically.
pub fn import_backup(
    connection: &Connection,
    vault_key: &SecretKey,
    backup_passphrase: &str,
    path: &str,
) -> Result<usize, String> {
    if backup_passphrase.len() < 12 || backup_passphrase.len() > 1024 {
        return Err("backup passphrase must contain 12..=1024 bytes".into());
    }
    let metadata =
        fs::symlink_metadata(path).map_err(|error| format!("inspect encrypted backup: {error}"))?;
    if metadata.file_type().is_symlink()
        || !metadata.is_file()
        || metadata.len() as usize > MAX_BACKUP_BYTES
    {
        return Err("backup must be a regular file no larger than 4 MiB".into());
    }
    let mut bytes = Vec::new();
    fs::File::open(path)
        .and_then(|file| {
            file.take((MAX_BACKUP_BYTES + 1) as u64)
                .read_to_end(&mut bytes)
        })
        .map_err(|error| format!("read encrypted backup: {error}"))?;
    if bytes.len() > MAX_BACKUP_BYTES || bytes.len() < BACKUP_MAGIC.len() + 16 + NONCE_BYTES + 16 {
        wipe(&mut bytes);
        return Err("encrypted backup has an invalid size".into());
    }
    if !bytes.starts_with(BACKUP_MAGIC) {
        wipe(&mut bytes);
        return Err("unsupported encrypted backup format".into());
    }
    let salt = fixed::<16>(
        bytes[BACKUP_MAGIC.len()..BACKUP_MAGIC.len() + 16].to_vec(),
        "backup salt",
    )?;
    let nonce_start = BACKUP_MAGIC.len() + 16;
    let nonce = fixed::<NONCE_BYTES>(
        bytes[nonce_start..nonce_start + NONCE_BYTES].to_vec(),
        "backup nonce",
    )?;
    let key = crate::crypto::derive_key(backup_passphrase, &salt)?;
    let plaintext_result = decrypt(
        &key,
        &nonce,
        BACKUP_AAD,
        &bytes[nonce_start + NONCE_BYTES..],
    );
    wipe(&mut bytes);
    let mut plaintext = plaintext_result?;
    let decoded = decode_backup(&plaintext);
    wipe(&mut plaintext);
    let mut records = decoded?;

    connection.execute("BEGIN IMMEDIATE")?;
    let mut imported = 0usize;
    let result = (|| {
        for record in &records {
            add_entry(
                connection,
                vault_key,
                &record.service,
                &record.username,
                &record.password,
            )?;
            imported += 1;
        }
        Ok(())
    })();
    for record in &mut records {
        wipe(unsafe { record.service.as_bytes_mut() });
        wipe(unsafe { record.username.as_bytes_mut() });
        wipe(unsafe { record.password.as_bytes_mut() });
    }
    match result {
        Ok(()) => connection.execute("COMMIT").map(|()| imported),
        Err(error) => {
            let _ = connection.execute("ROLLBACK");
            Err(error)
        }
    }
}

fn decode_backup(bytes: &[u8]) -> Result<Vec<EntrySecret>, String> {
    if bytes.len() < 4 {
        return Err("encrypted backup payload is truncated".into());
    }
    let count = u32::from_be_bytes(
        bytes[..4]
            .try_into()
            .map_err(|_| "invalid backup entry count")?,
    ) as usize;
    if count > 10_000 {
        return Err("backup contains more than 10,000 entries".into());
    }
    let mut position = 4usize;
    let mut records = Vec::with_capacity(count);
    for _ in 0..count {
        let mut fields = Vec::with_capacity(3);
        for (label, maximum) in [
            ("service", MAX_SERVICE_BYTES),
            ("username", MAX_USERNAME_BYTES),
            ("password", MAX_PASSWORD_BYTES),
        ] {
            let length_end = position
                .checked_add(2)
                .ok_or("backup field length overflow")?;
            if length_end > bytes.len() {
                return Err("encrypted backup record is truncated".into());
            }
            let length = u16::from_be_bytes(
                bytes[position..length_end]
                    .try_into()
                    .map_err(|_| "invalid backup field length")?,
            ) as usize;
            position = length_end;
            let field_end = position
                .checked_add(length)
                .ok_or("backup field length overflow")?;
            if length > maximum || field_end > bytes.len() {
                return Err(format!("encrypted backup {label} length is invalid"));
            }
            let field = String::from_utf8(bytes[position..field_end].to_vec())
                .map_err(|_| format!("encrypted backup {label} is not UTF-8"))?;
            validate_field(label, &field, 1, maximum)?;
            fields.push(field);
            position = field_end;
        }
        records.push(EntrySecret {
            service: fields.remove(0),
            username: fields.remove(0),
            password: fields.remove(0),
        });
    }
    if position != bytes.len() {
        return Err("encrypted backup contains trailing data".into());
    }
    Ok(records)
}

fn validate_field(label: &str, value: &str, minimum: usize, maximum: usize) -> Result<(), String> {
    if value.len() < minimum
        || value.len() > maximum
        || value.contains('\0')
        || value.trim().is_empty()
    {
        return Err(format!(
            "{label} must contain {minimum}..={maximum} non-whitespace bytes and no NUL"
        ));
    }
    Ok(())
}

fn fixed<const N: usize>(bytes: Vec<u8>, label: &str) -> Result<[u8; N], String> {
    bytes
        .try_into()
        .map_err(|_| format!("vault {label} has an invalid length"))
}

fn decode_payload(payload: &[u8]) -> Result<(String, String), String> {
    if payload.len() < 4 {
        return Err("encrypted entry payload is truncated".into());
    }
    let username_length = u32::from_be_bytes(
        payload[..4]
            .try_into()
            .map_err(|_| "invalid username length")?,
    ) as usize;
    let username_end = 4usize
        .checked_add(username_length)
        .ok_or("username length overflow")?;
    if username_end > payload.len() {
        return Err("encrypted entry payload has an invalid username length".into());
    }
    let username = String::from_utf8(payload[4..username_end].to_vec())
        .map_err(|_| "stored username is not UTF-8")?;
    let password = String::from_utf8(payload[username_end..].to_vec())
        .map_err(|_| "stored password is not UTF-8")?;
    Ok((username, password))
}

fn uuid_v4() -> Result<String, String> {
    let mut bytes = random_bytes::<16>()?;
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    Ok(format!("{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
        bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7], bytes[8], bytes[9],
        bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]))
}

pub fn database_path_from_environment() -> String {
    std::env::var("VAULTSMITH_DB").unwrap_or_else(|_| "./vaultsmith.sqlite".into())
}

#[cfg(test)]
mod tests {
    use super::{
        add_entry, create_vault, export_backup, import_backup, list_entries, open_database,
        read_entry, remove_entry, unlock,
    };

    #[test]
    fn encrypted_entries_are_isolated_by_unlock_and_delete() {
        let database = open_database(":memory:").expect("database");
        create_vault(&database, "long synthetic test passphrase").expect("initialize");
        assert!(create_vault(&database, "another synthetic passphrase").is_err());
        assert!(unlock(&database, "incorrect synthetic passphrase").is_err());
        let key = unlock(&database, "long synthetic test passphrase").expect("unlock");
        let id = add_entry(
            &database,
            &key,
            "example.test",
            "demo-user",
            "synthetic-secret-123",
        )
        .expect("add");
        let summaries = list_entries(&database).expect("list");
        assert_eq!(summaries.len(), 1);
        assert_eq!(summaries[0].service, "example.test");
        let value = read_entry(&database, &key, &id).expect("read");
        assert_eq!(value.username, "demo-user");
        assert_eq!(value.password, "synthetic-secret-123");
        assert!(remove_entry(&database, &id).expect("remove"));
        assert!(!remove_entry(&database, &id).expect("remove missing"));
        assert!(list_entries(&database)
            .expect("list after delete")
            .is_empty());
    }

    #[test]
    fn invalid_fields_are_rejected_before_storage() {
        let database = open_database(":memory:").expect("database");
        create_vault(&database, "long synthetic test passphrase").expect("initialize");
        let key = unlock(&database, "long synthetic test passphrase").expect("unlock");
        assert!(add_entry(&database, &key, "\0service", "user", "secret").is_err());
        assert!(add_entry(&database, &key, "service", "user", "").is_err());
        assert!(list_entries(&database).expect("list").is_empty());
    }

    #[test]
    fn file_database_keeps_credentials_encrypted_and_private() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let directory =
            std::env::temp_dir().join(format!("vaultsmith-test-{}-{unique}", std::process::id()));
        std::fs::create_dir(&directory).expect("create test-owned directory");
        let path = directory.join("vault.sqlite");
        let database = open_database(path.to_str().expect("UTF-8 temp path")).expect("database");
        create_vault(&database, "synthetic file vault passphrase").expect("initialize");
        let key = unlock(&database, "synthetic file vault passphrase").expect("unlock");
        add_entry(
            &database,
            &key,
            "fixture.example",
            "synthetic-user",
            "synthetic-at-rest-password",
        )
        .expect("add entry");
        drop(key);
        drop(database);
        let bytes = std::fs::read(&path).expect("database bytes");
        assert!(!bytes
            .windows(b"synthetic-user".len())
            .any(|window| window == b"synthetic-user"));
        assert!(!bytes
            .windows(b"synthetic-at-rest-password".len())
            .any(|window| window == b"synthetic-at-rest-password"));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                std::fs::metadata(&path)
                    .expect("metadata")
                    .permissions()
                    .mode()
                    & 0o777,
                0o600
            );
        }
        std::fs::remove_dir_all(&directory).expect("remove test-owned directory");
    }

    #[test]
    fn encrypted_backup_restores_to_a_different_vault() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let directory =
            std::env::temp_dir().join(format!("vaultsmith-backup-{}-{unique}", std::process::id()));
        std::fs::create_dir(&directory).expect("create test-owned directory");
        let backup = directory.join("vault.vsb");
        let backup_path = backup.to_str().expect("UTF-8 temp path");
        let source = open_database(":memory:").expect("source database");
        create_vault(&source, "source vault passphrase").expect("source vault");
        let source_key = unlock(&source, "source vault passphrase").expect("source unlock");
        add_entry(
            &source,
            &source_key,
            "example.test",
            "backup-user",
            "backup-password-42",
        )
        .expect("source entry");
        assert_eq!(
            export_backup(
                &source,
                &source_key,
                "separate backup passphrase",
                backup_path
            )
            .expect("export"),
            1
        );
        let bytes = std::fs::read(&backup).expect("backup bytes");
        assert!(!bytes
            .windows(b"backup-user".len())
            .any(|part| part == b"backup-user"));
        assert!(!bytes
            .windows(b"backup-password-42".len())
            .any(|part| part == b"backup-password-42"));
        assert!(export_backup(
            &source,
            &source_key,
            "separate backup passphrase",
            backup_path
        )
        .is_err());

        let target = open_database(":memory:").expect("target database");
        create_vault(&target, "different target passphrase").expect("target vault");
        let target_key = unlock(&target, "different target passphrase").expect("target unlock");
        assert!(
            import_backup(&target, &target_key, "wrong backup passphrase", backup_path).is_err()
        );
        assert!(list_entries(&target)
            .expect("empty after failed import")
            .is_empty());
        let tampered_path = directory.join("tampered.vsb");
        let mut tampered = bytes.clone();
        let last = tampered.len() - 1;
        tampered[last] ^= 0x40;
        std::fs::write(&tampered_path, &tampered).expect("write tampered fixture");
        assert!(import_backup(
            &target,
            &target_key,
            "separate backup passphrase",
            tampered_path.to_str().expect("UTF-8 temp path")
        )
        .is_err());
        assert!(list_entries(&target)
            .expect("empty after tampered import")
            .is_empty());
        assert_eq!(
            import_backup(
                &target,
                &target_key,
                "separate backup passphrase",
                backup_path
            )
            .expect("import"),
            1
        );
        let summaries = list_entries(&target).expect("restored entries");
        let restored = read_entry(&target, &target_key, &summaries[0].id).expect("restored secret");
        assert_eq!(restored.username, "backup-user");
        assert_eq!(restored.password, "backup-password-42");
        drop(restored);
        drop(target_key);
        drop(target);
        drop(source_key);
        drop(source);
        std::fs::remove_dir_all(directory).expect("remove test-owned directory");
    }
}
