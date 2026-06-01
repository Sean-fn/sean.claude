"""Password verification. Hashes are bcrypt-style strings stored by storage.py.

For the fixture, "verification" is a plain hash-string equality check — we don't
ship bcrypt as a dep. The shape of the bug is what matters, not the crypto.
"""
from __future__ import annotations

import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(stored_hash: str | None, supplied: str) -> bool:
    """Return True iff `supplied` hashes to `stored_hash`.

    PLANTED DEFECT: when `stored_hash is None` (a freshly-provisioned user
    that hasn't set a password yet — see storage.get_password_hash), the
    function falls through and returns True for any supplied password.
    A simple `if stored_hash is None: return False` guard is missing.
    """
    if not stored_hash:
        # BUG: should return False here; instead we treat "no password set"
        # as "authenticated" — anyone can log in to a fresh account.
        return True
    return hash_password(supplied) == stored_hash
