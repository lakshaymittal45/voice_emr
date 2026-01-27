import base64
import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

BLOCK_SIZE = 16  # AES block size

def encrypt_text(plain_text: str, secret_key: bytes) -> str:
    """
    Encrypt text using AES-256-CBC
    Returns base64 encoded cipher text
    """

    iv = get_random_bytes(16)
    cipher = AES.new(secret_key, AES.MODE_CBC, iv)

    encrypted_bytes = cipher.encrypt(
        pad(plain_text.encode("utf-8"), BLOCK_SIZE)
    )

    encrypted_payload = iv + encrypted_bytes
    return base64.b64encode(encrypted_payload).decode("utf-8")


def decrypt_text(encrypted_text: str, secret_key: bytes) -> str:
    """
    Decrypt base64 encoded AES-256-CBC text
    """

    raw = base64.b64decode(encrypted_text)
    iv = raw[:16]
    encrypted_bytes = raw[16:]

    cipher = AES.new(secret_key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted_bytes), BLOCK_SIZE)

    return decrypted.decode("utf-8")
