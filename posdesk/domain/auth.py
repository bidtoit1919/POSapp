from __future__ import annotations

import hashlib
import hmac
import os


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 10: raise ValueError("Password must be at least 10 characters")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return "pbkdf2_sha256$310000$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    algorithm, rounds, salt_hex, expected = stored.split("$", 3)
    if algorithm != "pbkdf2_sha256": return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
    return hmac.compare_digest(got, expected)
