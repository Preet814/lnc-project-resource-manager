"""OTP generation and hashing for email verification."""

from __future__ import annotations

import hashlib
import secrets


def generate_numeric_otp(length: int) -> str:
    upper = 10**length
    value = secrets.randbelow(upper)
    return str(value).zfill(length)


def hash_otp(*, otp: str, secret: str) -> str:
    payload = f"{secret}:{otp}".encode()
    return hashlib.sha256(payload).hexdigest()


def verify_otp(*, otp: str, secret: str, expected_hash: str) -> bool:
    return hash_otp(otp=otp, secret=secret) == expected_hash
