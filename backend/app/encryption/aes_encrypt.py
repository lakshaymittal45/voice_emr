import base64
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

# AES block size (bytes)
BLOCK_SIZE = 16


def encrypt_text(plain_text: str, secret_key: bytes) -> str:
    """
    Encrypt text using AES-256-CBC.

    - Generates a random 16-byte IV
    - Encrypts padded UTF-8 text
    - Returns base64-encoded (IV + ciphertext)

    This function MUST always succeed for valid inputs.
    """

    if plain_text is None:
        plain_text = ""

    # 🔐 Generate random IV
    iv = get_random_bytes(BLOCK_SIZE)

    cipher = AES.new(secret_key, AES.MODE_CBC, iv)

    encrypted_bytes = cipher.encrypt(
        pad(plain_text.encode("utf-8"), BLOCK_SIZE)
    )

    # Store IV + ciphertext together
    encrypted_payload = iv + encrypted_bytes

    return base64.b64encode(encrypted_payload).decode("utf-8")


def decrypt_text(encrypted_text: str, secret_key: bytes) -> str:
    """
    Safely decrypt base64 encoded AES-256-CBC text.

    ❗ This function is intentionally defensive:
    - Never raises exceptions
    - Never crashes API
    - Returns empty string on corrupted / legacy / invalid data
    """

    # 🛑 Guard 1: NULL or empty DB value
    if not encrypted_text:
        return ""

    try:
        raw = base64.b64decode(encrypted_text)

        # 🛑 Guard 2: Must contain at least IV
        if len(raw) < BLOCK_SIZE:
            return ""

        iv = raw[:BLOCK_SIZE]
        encrypted_bytes = raw[BLOCK_SIZE:]

        # 🛑 Guard 3: IV must be exactly 16 bytes
        if len(iv) != BLOCK_SIZE:
            return ""

        cipher = AES.new(secret_key, AES.MODE_CBC, iv)

        decrypted = unpad(
            cipher.decrypt(encrypted_bytes),
            BLOCK_SIZE
        )

        return decrypted.decode("utf-8")

    except Exception:
        # 🧯 ABSOLUTELY NO EXCEPTIONS ESCAPE
        # Bad rows should never take down the API
        return ""
