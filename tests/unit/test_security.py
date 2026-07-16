"""Unit tests for security utilities (JWT, password hashing)."""

from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    TokenType,
)

SECRET = "test-secret-key-min-32-chars-for-tests"


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        h = hash_password("MyPassword123!")
        assert h != "MyPassword123!"

    def test_verify_correct_password(self) -> None:
        h = hash_password("MyPassword123!")
        assert verify_password("MyPassword123!", h) is True

    def test_reject_wrong_password(self) -> None:
        h = hash_password("MyPassword123!")
        assert verify_password("WrongPassword!", h) is False

    def test_two_hashes_of_same_password_differ(self) -> None:
        h1 = hash_password("SamePassword")
        h2 = hash_password("SamePassword")
        assert h1 != h2   # bcrypt uses random salt


class TestJWT:
    def test_create_and_decode_access_token(self) -> None:
        token = create_access_token(subject="user1", secret_key=SECRET)
        payload = decode_token(token, secret_key=SECRET)
        assert payload["sub"] == "user1"
        assert payload["type"] == TokenType.ACCESS

    def test_create_and_decode_refresh_token(self) -> None:
        token = create_refresh_token(subject="user1", secret_key=SECRET)
        payload = decode_token(
            token, secret_key=SECRET, expected_type=TokenType.REFRESH
        )
        assert payload["sub"] == "user1"
        assert payload["type"] == TokenType.REFRESH

    def test_wrong_token_type_raises(self) -> None:
        access = create_access_token(subject="user1", secret_key=SECRET)
        with pytest.raises(ValueError, match="Expected token type"):
            decode_token(access, secret_key=SECRET, expected_type=TokenType.REFRESH)

    def test_invalid_token_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token("not.a.valid.token", secret_key=SECRET)

    def test_wrong_secret_raises(self) -> None:
        token = create_access_token(subject="user1", secret_key=SECRET)
        with pytest.raises(ValueError):
            decode_token(token, secret_key="different-secret-key-min-32-chars-x")

    def test_additional_claims_included(self) -> None:
        token = create_access_token(
            subject="user1",
            secret_key=SECRET,
            additional_claims={"role": "admin"},
        )
        payload = decode_token(token, secret_key=SECRET)
        assert payload["role"] == "admin"
