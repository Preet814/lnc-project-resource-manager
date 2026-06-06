"""Unit tests for password hashing."""

from prm.infrastructure.security.password import BcryptPasswordHasher


def test_hash_and_verify_password() -> None:
    hasher = BcryptPasswordHasher()
    password_hash = hasher.hash("Admin@1234")

    assert password_hash != "Admin@1234"
    assert hasher.verify("Admin@1234", password_hash)
    assert not hasher.verify("wrong-password", password_hash)
