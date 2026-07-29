import pytest
from backend.adapters.auth.simple_auth import SimpleAuthAdapter
from backend.ports.auth import EmailAlreadyRegisteredError, InvalidCredentialsError


def make_auth():
    return SimpleAuthAdapter(":memory:")


def test_register_and_login():
    auth = make_auth()
    user = auth.register("student@example.com", "password123")
    assert user.email == "student@example.com"
    token = auth.login("student@example.com", "password123")
    assert token
    resolved = auth.get_user_from_session(token)
    assert resolved.id == user.id


def test_duplicate_email_rejected():
    auth = make_auth()
    auth.register("student@example.com", "password123")
    with pytest.raises(EmailAlreadyRegisteredError):
        auth.register("student@example.com", "different_password")


def test_wrong_password_rejected():
    auth = make_auth()
    auth.register("student@example.com", "password123")
    with pytest.raises(InvalidCredentialsError):
        auth.login("student@example.com", "wrong_password")


def test_invalid_session_returns_none_not_raises():
    auth = make_auth()
    assert auth.get_user_from_session("not-a-real-token") is None


def test_logout_invalidates_session():
    auth = make_auth()
    auth.register("student@example.com", "password123")
    token = auth.login("student@example.com", "password123")
    auth.logout(token)
    assert auth.get_user_from_session(token) is None
