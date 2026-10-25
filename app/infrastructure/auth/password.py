"""Argon2id password hashing and constant-time verification."""

from __future__ import annotations

import hmac

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Hash with Argon2id."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time verify, timing-safe against mismatch."""
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def secrets_equal(left: str, right: str) -> bool:
    """Compare two strings without timing leaks."""
    return hmac.compare_digest(left.encode(), right.encode())
