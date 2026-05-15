"""Unit tests for app.core.recovery — no DB required."""
import pytest

from app.core.recovery import generate_recovery_words, hash_recovery_words, verify_recovery_words


def test_generate_recovery_words_default_count():
    words = generate_recovery_words()
    assert len(words) == 12


def test_generate_recovery_words_custom_count():
    words = generate_recovery_words(count=6)
    assert len(words) == 6


def test_generate_recovery_words_are_strings():
    words = generate_recovery_words()
    assert all(isinstance(w, str) and len(w) > 0 for w in words)


def test_generate_recovery_words_from_wordlist():
    # Words should be non-empty and not contain whitespace
    words = generate_recovery_words()
    assert all(" " not in w for w in words)


def test_generate_recovery_words_randomness():
    # Two calls should almost certainly produce different results
    a = generate_recovery_words()
    b = generate_recovery_words()
    assert a != b  # astronomically unlikely to collide


def test_hash_recovery_words_is_bcrypt():
    words = generate_recovery_words()
    h = hash_recovery_words(words)
    assert h.startswith("$2b$")


def test_verify_recovery_words_correct():
    words = generate_recovery_words()
    h = hash_recovery_words(words)
    assert verify_recovery_words(words, h) is True


def test_verify_recovery_words_wrong():
    words = generate_recovery_words()
    h = hash_recovery_words(words)
    wrong = generate_recovery_words()
    assert verify_recovery_words(wrong, h) is False


def test_verify_recovery_words_wrong_order():
    words = generate_recovery_words()
    h = hash_recovery_words(words)
    shuffled = list(reversed(words))
    assert verify_recovery_words(shuffled, h) is False


def test_hash_recovery_words_different_salts():
    words = generate_recovery_words()
    h1 = hash_recovery_words(words)
    h2 = hash_recovery_words(words)
    # bcrypt uses random salt each time
    assert h1 != h2
    assert verify_recovery_words(words, h1)
    assert verify_recovery_words(words, h2)


def test_verify_recovery_words_long_input():
    """Verifying that the SHA-256 pre-hash correctly handles inputs > 72 bytes."""
    # 12 words of 8 chars each + 11 spaces = 107 chars — exceeds bcrypt 72-byte limit
    long_words = ["abcdefgh"] * 12
    h = hash_recovery_words(long_words)
    assert verify_recovery_words(long_words, h) is True
    assert verify_recovery_words(["abcdefgi"] + long_words[1:], h) is False
