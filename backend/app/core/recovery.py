import base64
import hashlib
import secrets
import bcrypt
from pathlib import Path

from app.config import settings


def _load_wordlist() -> list[str]:
    path = Path(settings.recovery_word_list_path)
    return [w.strip() for w in path.read_text().splitlines() if w.strip()]


def generate_recovery_words(count: int = 12) -> list[str]:
    wordlist = _load_wordlist()
    return [secrets.choice(wordlist) for _ in range(count)]


def hash_recovery_words(words: list[str]) -> str:
    # Recovery words exceed the 72 byte limit for bcrypt, so they should be hashed 
    # see https://stackoverflow.com/questions/65067575/python-bcrypt-how-to-check-a-long-encrypted-by-sha256-password
    encoded_words = " ".join(words).encode("utf-8")
    return bcrypt.hashpw(
        base64.b64encode(hashlib.sha256(encoded_words).digest()),
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_recovery_words(words: list[str], hashed: str) -> bool:
    encoded_words = " ".join(words).encode("utf-8")
    return bcrypt.checkpw(
        base64.b64encode(hashlib.sha256(encoded_words).digest()),
        hashed.encode("utf-8"),
    )
