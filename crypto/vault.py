import binascii
import hashlib
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import config


def _key() -> bytes:
    raw = config.CIPHER_KEY.strip()
    return hashlib.sha256(raw.encode()).digest()


def seal(plaintext: str) -> str:
    nonce = secrets.token_bytes(12)
    ct    = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return binascii.hexlify(nonce + ct).decode()


def unseal(ciphertext_hex: str) -> str:
    raw = bytes.fromhex(ciphertext_hex)
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], None).decode()


def random_token() -> str:
    return binascii.hexlify(secrets.token_bytes(16)).decode()