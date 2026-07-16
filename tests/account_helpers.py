"""Shared test-only account helpers."""
import asyncio

from admin_provisioning import provision_admin
from db import DB_PATH


async def provision_test_admin(email: str) -> None:
    await asyncio.to_thread(provision_admin, DB_PATH, email)


async def register_test_admin(
    client,
    email: str,
    password: str = "correcthorse",
):
    response = await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )
    assert response.status_code in (200, 201), response.text
    await provision_test_admin(email)
    return response
