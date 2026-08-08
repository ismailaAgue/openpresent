"""
Simple email/password/session Auth adapter. Deliberately minimal per
the Codebase Handbook — no third-party dependency required, $0 cost.
Passwords hashed with salted SHA-256 (stdlib only, no extra dependency
for this dev-stage adapter; a production adapter would use bcrypt/argon2
— that's a self-contained adapter swap, not a port change).
"""

import hashlib
import os
import secrets
import sqlite3
import time
import uuid
from backend.ports.auth import AuthPort, User, EmailAlreadyRegisteredError, InvalidCredentialsError

SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


class SimpleAuthAdapter(AuthPort):
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def register(self, email: str, password: str) -> User:
        email = email.strip().lower()
        existing = self._conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise EmailAlreadyRegisteredError(f"{email} is already registered")
        user_id = str(uuid.uuid4())
        salt = secrets.token_hex(16)
        password_hash = _hash_password(password, salt)
        self._conn.execute(
            "INSERT INTO users (id, email, password_hash, salt) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, salt),
        )
        self._conn.commit()
        return User(id=user_id, email=email)

    def login(self, email: str, password: str) -> str:
        email = email.strip().lower()
        row = self._conn.execute(
            "SELECT id, password_hash, salt FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None:
            raise InvalidCredentialsError("invalid email or password")
        user_id, stored_hash, salt = row
        if _hash_password(password, salt) != stored_hash:
            raise InvalidCredentialsError("invalid email or password")

        token = secrets.token_urlsafe(32)
        self._conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, time.time() + SESSION_TTL_SECONDS),
        )
        self._conn.commit()
        return token

    def get_user_from_session(self, session_token: str) -> User | None:
        row = self._conn.execute(
            "SELECT sessions.user_id, users.email, sessions.expires_at "
            "FROM sessions JOIN users ON sessions.user_id = users.id "
            "WHERE sessions.token = ?",
            (session_token,),
        ).fetchone()
        if row is None:
            return None
        user_id, email, expires_at = row
        if expires_at < time.time():
            return None
        return User(id=user_id, email=email)

    def logout(self, session_token: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE token = ?", (session_token,))
        self._conn.commit()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
