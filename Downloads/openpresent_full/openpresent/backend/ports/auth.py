"""
Auth Port — Codebase Handbook Section 3: "simple email/session-based
auth at launch, designed as its own port so OAuth or a managed auth
provider can be added later without restructuring anything else."
"""

from typing import Protocol
from dataclasses import dataclass


@dataclass
class User:
    id: str
    email: str


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthPort(Protocol):
    def register(self, email: str, password: str) -> User:
        ...

    def login(self, email: str, password: str) -> str:
        """Returns a session token."""
        ...

    def get_user_from_session(self, session_token: str) -> User | None:
        """Returns None for an invalid/expired token — never raises,
        callers treat None as 'not authenticated'."""
        ...

    def logout(self, session_token: str) -> None:
        ...
