#!/usr/bin/env python3
"""Password hashing concepts lab; secrets are read without terminal echo."""
import argparse, base64, getpass, hashlib, hmac, os, re, sys

def hash_password(secret, backend="auto"):
    if backend=="auto":
        try: import argon2  # noqa: F401
        except ImportError: backend="scrypt"
        else: backend="argon2"
    if backend=="argon2":
        from argon2 import PasswordHasher
        return PasswordHasher().hash(secret)
    if backend=="bcrypt":
        import bcrypt
        return bcrypt.hashpw(secret.encode(),bcrypt.gensalt()).decode()
    if backend=="scrypt":
        salt=os.urandom(16); n,r,p=2**14,8,1
        digest=hashlib.scrypt(secret.encode(),salt=salt,n=n,r=r,p=p,dklen=32)
        return "$scrypt${}${}${}${}${}".format(n,r,p,base64.urlsafe_b64encode(salt).decode(),base64.urlsafe_b64encode(digest).decode())
    raise ValueError("backend must be auto, argon2, bcrypt, or scrypt")
def verify(secret, encoded):
    if encoded.startswith("$scrypt$"):
        try:
            _,_,n,r,p,salt,digest=encoded.split("$")
            n,r,p=int(n),int(r),int(p)
            if n<2**12 or n>2**18 or n&(n-1) or not 1<=r<=16 or not 1<=p<=8:return False
            salt=base64.urlsafe_b64decode(salt.encode()); expected=base64.urlsafe_b64decode(digest.encode())
            actual=hashlib.scrypt(secret.encode(),salt=salt,n=n,r=r,p=p,dklen=len(expected),maxmem=512*1024*1024)
            return hmac.compare_digest(actual,expected)
        except (ValueError,TypeError):return False
    if encoded.startswith("$argon2"):
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        try:return PasswordHasher().verify(encoded,secret)
        except VerifyMismatchError:return False
    if encoded.startswith("$2"):
        import bcrypt
        return bcrypt.checkpw(secret.encode(),encoded.encode())
    raise ValueError("unknown encoded hash format")
def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="cmd",required=True)
    h=sub.add_parser("hash"); h.add_argument("--backend",choices=["auto","argon2","bcrypt","scrypt"],default="auto")
    v=sub.add_parser("verify");v.add_argument("encoded_hash")
    sub.add_parser("check"); a=p.parse_args()
    try:
        secret=getpass.getpass("Test password: ")
        if a.cmd=="hash": print(hash_password(secret,a.backend))
        elif a.cmd=="verify": print("MATCH" if verify(secret,a.encoded_hash) else "NO MATCH")
        else:
            checks={"12+ characters":len(secret)>=12,"upper and lower case":bool(re.search("[a-z]",secret) and re.search("[A-Z]",secret)),"number or symbol":bool(re.search("[0-9]|[^A-Za-z0-9]",secret))}
            for name,ok in checks.items():print(("OK   " if ok else "HINT ")+name)
            print("Use a unique passphrase and a password manager; composition checks cannot establish that a password is uncompromised.")
    except ImportError as e: print(f"Install the selected backend dependency: {e}",file=sys.stderr);return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
