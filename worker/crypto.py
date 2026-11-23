"""AES-256-GCM decryption compatible with the web app's `crypto.server.ts`.

Wire format: ``v1.<iv>.<ciphertext>.<tag>`` where each part is unpadded
base64url. The IV is 12 bytes and the tag is 16 bytes.
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = "v1"


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_key(key_b64: str) -> bytes:
    try:
        key = base64.b64decode(key_b64, validate=True)
    except Exception as exc:  # noqa: BLE001 - surface a clear message
        raise ValueError(
            "CREDENTIALS_ENCRYPTION_KEY is not valid base64."
        ) from exc
    if len(key) != 32:
        raise ValueError(
            "CREDENTIALS_ENCRYPTION_KEY must be 32 bytes (base64 of 32 bytes)."
        )
    return key


def decrypt_secret(payload: str, key_b64: str) -> str:
    parts = payload.split(".")
    if len(parts) != 4 or parts[0] != VERSION:
        raise ValueError("Malformed encrypted payload")

    _, iv_part, ciphertext_part, tag_part = parts
    iv = _b64url_decode(iv_part)
    ciphertext = _b64url_decode(ciphertext_part)
    tag = _b64url_decode(tag_part)

    if len(iv) != 12 or len(tag) != 16:
        raise ValueError("Malformed encrypted payload lengths")

    plaintext = AESGCM(_decode_key(key_b64)).decrypt(
        iv, ciphertext + tag, None
    )
    return plaintext.decode("utf-8")
