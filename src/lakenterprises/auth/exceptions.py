"""Custom exceptions for the authentication and authorization module."""

from __future__ import annotations


class AuthException(Exception):
    """Base exception for all authentication and authorization errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(AuthException):
    """Raised when supplied credentials (username/email + password) are wrong."""

    def __init__(self, identifier: str, message: str = "Invalid credentials") -> None:
        self.identifier = identifier
        self.message = message
        super().__init__(self.message)


class TokenExpiredError(AuthException):
    """Raised when a presented token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        self.message = message
        super().__init__(self.message)


class TokenRevokedError(AuthException):
    """Raised when a presented token has been revoked."""

    def __init__(self, message: str = "Token has been revoked") -> None:
        self.message = message
        super().__init__(self.message)


class InsufficientPermissionsError(AuthException):
    """Raised when the user lacks the required permission or role."""

    def __init__(self, message: str, user_id: str | None = None) -> None:
        self.message = message
        self.user_id = user_id
        self.permission_name = message  # convenience attribute
        super().__init__(self.message)


class SessionExpiredError(AuthException):
    """Raised when the user's session has expired."""

    def __init__(self, message: str = "Session has expired") -> None:
        self.message = message
        super().__init__(self.message)
