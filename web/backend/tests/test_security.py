import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security import hash_password, verify_password


def test_hash_password_is_not_plaintext():
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"


def test_verify_password_accepts_correct_password():
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("hunter2")
    assert verify_password("wrong", hashed) is False


def test_verify_password_handles_malformed_hash_without_raising():
    assert verify_password("hunter2", "not-a-real-bcrypt-hash") is False


def test_same_password_hashes_differently_each_time():
    # bcrypt salts per-call — two hashes of the same password must differ,
    # otherwise the salt isn't doing its job
    assert hash_password("hunter2") != hash_password("hunter2")
