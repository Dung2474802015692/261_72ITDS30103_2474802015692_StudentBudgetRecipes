"""Password hashing with scrypt from the standard library, so no extra dependency is needed.

A stored hash looks like: scrypt$16384$8$1$<salt hex>$<digest hex>
Only the hash is stored; the password itself is never written anywhere.
"""

import hashlib
import hmac
import secrets

N, R, P, DKLEN = 2**14, 8, 1, 32  # scrypt cost: about 16 MB of memory per hash
PREFIX = "scrypt"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=DKLEN)
    return f"{PREFIX}${N}${R}${P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        prefix, n, r, p, salt_hex, digest_hex = stored.split("$")
        if prefix != PREFIX:
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p),
            dklen=len(digest_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest_hex)
