"""Shared SQLite connection for the local Saathi demo."""

import os
import sqlite3


def database_path() -> str:
    """Return the configured SQLite database file path."""
    return os.getenv("DB_PATH", ".data/saathi.sqlite3")


def get_connection(path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with dictionary-style rows enabled.

    Callers should close the connection, or use ``Store.connect()`` when a
    commit/rollback transaction boundary is needed.
    """
    connection = sqlite3.connect(path or database_path(), timeout=30)
    connection.row_factory = sqlite3.Row
    return connection
