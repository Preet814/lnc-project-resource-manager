"""Unit tests for password hashing."""

from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_PASSWORD


def test_hash_and_verify_password() -> None:
    hasher = BcryptPasswordHasher()
    password_hash = hasher.hash(TEST_PASSWORD)

    assert password_hash != TEST_PASSWORD
    assert hasher.verify(TEST_PASSWORD, password_hash)
    assert not hasher.verify("wrong-password", password_hash)
