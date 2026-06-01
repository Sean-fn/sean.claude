"""Auth tests. Does NOT exercise the None-hash path.

Every test here uses a real password hash, so the planted bug in
verify_password (which fires only when stored_hash is None) is invisible.
"""
from __future__ import annotations

from note_cli import auth


def test_hash_is_deterministic() -> None:
    assert auth.hash_password("hunter2") == auth.hash_password("hunter2")


def test_verify_correct_password() -> None:
    h = auth.hash_password("hunter2")
    assert auth.verify_password(h, "hunter2") is True


def test_verify_wrong_password() -> None:
    h = auth.hash_password("hunter2")
    assert auth.verify_password(h, "wrong") is False
