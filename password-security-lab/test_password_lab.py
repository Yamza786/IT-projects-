import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("password_lab",Path(__file__).with_name("password_lab.py"))
password_lab=importlib.util.module_from_spec(spec)
spec.loader.exec_module(password_lab)

def test_scrypt_hash_verifies_and_is_salted():
    first=password_lab.hash_password("Portfolio-demo-123!", "scrypt")
    second=password_lab.hash_password("Portfolio-demo-123!", "scrypt")
    assert first != second
    assert password_lab.verify("Portfolio-demo-123!", first)
    assert not password_lab.verify("incorrect", first)

def test_auto_backend_works_without_optional_packages():
    encoded=password_lab.hash_password("example passphrase")
    assert encoded.startswith(("$argon2", "$scrypt$"))
    assert password_lab.verify("example passphrase", encoded)

def test_unknown_hash_is_rejected():
    try:
        password_lab.verify("secret", "$unknown$bad")
    except ValueError as error:
        assert "unknown" in str(error)
    else:
        raise AssertionError("unknown hash format should be rejected")
