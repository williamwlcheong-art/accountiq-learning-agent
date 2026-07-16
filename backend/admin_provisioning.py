"""Offline administrator provisioning for existing AccountIQ users."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def provision_admin(database_path: Path, email: str) -> None:
    database_path = database_path.expanduser().resolve()
    email = email.strip().lower()
    if not database_path.is_file():
        raise RuntimeError(f"Database does not exist: {database_path}")
    if not email or "@" not in email:
        raise RuntimeError("A valid existing user email is required")

    with sqlite3.connect(database_path) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = db.execute(
                "SELECT id, is_admin FROM users WHERE email=?",
                (email,),
            ).fetchall()
            if len(rows) != 1:
                raise RuntimeError(f"Expected exactly one existing user for {email}; found {len(rows)}")
            if rows[0]["is_admin"]:
                raise RuntimeError(f"User is already an admin: {email}")
            db.execute("UPDATE users SET is_admin=1 WHERE id=?", (rows[0]["id"],))
            db.commit()
        except Exception:
            db.rollback()
            raise
