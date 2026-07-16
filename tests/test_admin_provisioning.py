import sqlite3
from pathlib import Path

import pytest

from admin_provisioning import provision_admin


def _database(path: Path, *, email: str = "admin@example.com", is_admin: int = 0) -> Path:
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, hashed_pw TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0)"
        )
        db.execute(
            "INSERT INTO users (email, hashed_pw, is_admin) VALUES (?, 'hash', ?)",
            (email, is_admin),
        )
        db.commit()
    return path


def test_provisions_existing_user(tmp_path):
    database = _database(tmp_path / "accountiq.db")

    provision_admin(database, " Admin@Example.com ")

    with sqlite3.connect(database) as db:
        assert db.execute(
            "SELECT is_admin FROM users WHERE email='admin@example.com'"
        ).fetchone()[0] == 1


def test_refuses_missing_database(tmp_path):
    with pytest.raises(RuntimeError, match="does not exist"):
        provision_admin(tmp_path / "missing.db", "admin@example.com")


def test_refuses_missing_user(tmp_path):
    database = _database(tmp_path / "accountiq.db")

    with pytest.raises(RuntimeError, match="found 0"):
        provision_admin(database, "missing@example.com")


def test_refuses_already_admin_without_changing_state(tmp_path):
    database = _database(tmp_path / "accountiq.db", is_admin=1)

    with pytest.raises(RuntimeError, match="already an admin"):
        provision_admin(database, "admin@example.com")

    with sqlite3.connect(database) as db:
        assert db.execute("SELECT is_admin FROM users").fetchone()[0] == 1
