"""LakEnterprises – enterprise knowledge platform."""

from .config import Settings  # noqa: F401

__all__ = ["main", "Settings"]


def main() -> None:
    print("Hello from lakenterprises!")
