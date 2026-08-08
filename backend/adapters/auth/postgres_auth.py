"""
Postgres-backed Auth adapter. Same AuthPort contract as SimpleAuthAdapter
(SQLite), but backed by a real managed database that survives web
service restarts/redeploys (ADR-018).

Revision (ADR-019): uses a ThreadedConnectionPool instead of a single
shared connection. The API now serves concurrent web requests (each
handled in a worker thread by Starlette, since these are plain `def`
routes) AND the in-process background worker thread (ADR-015)
simultaneously — a single raw psycopg2 connection is not safe to use
from multiple threads at once, and doing so caused real, intermittent
request failures (surfacing to the browser as a generic "Failed to
fetch," since a broken connection mid-request can skip normal error
handling and CORS headers). Each database call now borrows a
connection from the pool and returns it immediately after.
"""

import hashlib
import secrets
import time
import uuid
from psycopg2 import pool as pg_pool
from backend.ports.auth import AuthPort, User, EmailAlreadyRegisteredError, InvalidCredentialsError

SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


class PostgresAuthAdapter(AuthPort):
    def __init__(self, database_url: str):
        self._pool = pg_pool.ThreadedConnectionPool(1, 5, database_url)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_sessions (
                        token TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        expires_at DOUBLE PRECISION NOT NULL
                    )
                """)
        finally:
            self._pool.putconn(conn)

    def register(self, email: str, password: str) -> User:
        email = email.strip().lower()
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM op_users WHERE email = %s", (email,))
                if cur.fetchone():
                    raise EmailAlreadyRegisteredError(f"{email} is already registered")
                user_id = str(uuid.uuid4())
                salt = secrets.token_hex(16)
                password_hash = _hash_password(password, salt)
                cur.execute(
                    "INSERT INTO op_users (id, email, password_hash, salt) VALUES (%s, %s, %s, %s)",
                    (user_id, email, password_hash, salt),
                )
            return User(id=user_id, email=email)
        finally:
            self._pool.putconn(conn)

    def login(self, email: str, password: str) -> str:
        email = email.strip().lower()
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, password_hash, salt FROM op_users WHERE email = %s", (email,)
                )
                row = cur.fetchone()
                if row is None:
                    raise InvalidCredentialsError("invalid email or password")
                user_id, stored_hash, salt = row
                if _hash_password(password, salt) != stored_hash:
                    raise InvalidCredentialsError("invalid email or password")

                token = secrets.token_urlsafe(32)
                cur.execute(
                    "INSERT INTO op_sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                    (token, user_id, time.time() + SESSION_TTL_SECONDS),
                )
            return token
        finally:
            self._pool.putconn(conn)

    def get_user_from_session(self, session_token: str) -> User | None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT op_sessions.user_id, op_users.email, op_sessions.expires_at
                    FROM op_sessions JOIN op_users ON op_sessions.user_id = op_users.id
                    WHERE op_sessions.token = %s
                """, (session_token,))
                row = cur.fetchone()
        finally:
            self._pool.putconn(conn)
        if row is None:
            return None
        user_id, email, expires_at = row
        if expires_at < time.time():
            return None
        return User(id=user_id, email=email)

    def logout(self, session_token: str) -> None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("DELETE FROM op_sessions WHERE token = %s", (session_token,))
        finally:
            self._pool.putconn(conn)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
