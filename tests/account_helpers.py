"""Shared test-only account helpers."""
from admin_provisioning import provision_admin
from db import DB_PATH


async def provision_test_admin(email: str) -> None:
    provision_admin(DB_PATH, email)
