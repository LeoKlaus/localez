import secrets
from pathlib import Path

from app.config import settings
from app.core.security import pwd_context


def _load_wordlist() -> list[str]:
    path = Path(settings.recovery_word_list_path)
    return [w.strip() for w in path.read_text().splitlines() if w.strip()]


def generate_recovery_words(count: int = 12) -> list[str]:
    wordlist = _load_wordlist()
    return [secrets.choice(wordlist) for _ in range(count)]


def hash_recovery_words(words: list[str]) -> str:
    return pwd_context.hash(" ".join(words))


def verify_recovery_words(words: list[str], hashed: str) -> bool:
    return pwd_context.verify(" ".join(words), hashed)
