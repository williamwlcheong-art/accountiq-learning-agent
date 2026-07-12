import aiosqlite
import pytest

from db import DB_PATH


async def _register(client, email: str) -> dict:
    response = await client.post(
        "/auth/register",
        data={"email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    me = await client.get("/auth/me")
    assert me.status_code == 200, me.text
    return me.json()


async def _insert_purchase(
    user_id: int,
    company_name: str,
    *,
    report_status: str,
    purchase_status: str,
    created_at: str,
) -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES (?, 'Private', ?)",
            (company_name, user_id),
        ) as cursor:
            company_id = cursor.lastrowid
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status, created_at)
            VALUES (?, ?, 'valuation_advisory', ?, ?)
            """,
            (company_id, user_id, report_status, created_at),
        ) as cursor:
            report_id = cursor.lastrowid
        async with db.execute(
            """
            INSERT INTO purchases (
                report_id,
                user_id,
                amount_cents,
                currency,
                status,
                paid_at,
                created_at
            )
            VALUES (?, ?, 49500, 'nzd', ?, ?, ?)
            """,
            (
                report_id,
                user_id,
                purchase_status,
                created_at if purchase_status == "paid" else None,
                created_at,
            ),
        ) as cursor:
            purchase_id = cursor.lastrowid
        await db.commit()
    return report_id, purchase_id


@pytest.mark.asyncio
async def test_purchase_history_returns_newest_first(client, fresh_all_db):
    owner = await _register(client, "history-owner@example.com")
    older_report_id, older_purchase_id = await _insert_purchase(
        owner["id"],
        "Older Holdings Ltd",
        report_status="done",
        purchase_status="paid",
        created_at="2026-07-11 09:00:00",
    )
    newer_report_id, newer_purchase_id = await _insert_purchase(
        owner["id"],
        "Newer Holdings Ltd",
        report_status="awaiting_review",
        purchase_status="paid",
        created_at="2026-07-12 10:00:00",
    )

    response = await client.get("/account/purchases")

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "purchase_id": newer_purchase_id,
            "report_id": newer_report_id,
            "company_name": "Newer Holdings Ltd",
            "report_type": "valuation_advisory",
            "purchase_status": "paid",
            "report_status": "awaiting_review",
            "amount_cents": 49500,
            "currency": "nzd",
            "paid_at": "2026-07-12 10:00:00",
            "created_at": "2026-07-12 10:00:00",
        },
        {
            "purchase_id": older_purchase_id,
            "report_id": older_report_id,
            "company_name": "Older Holdings Ltd",
            "report_type": "valuation_advisory",
            "purchase_status": "paid",
            "report_status": "done",
            "amount_cents": 49500,
            "currency": "nzd",
            "paid_at": "2026-07-11 09:00:00",
            "created_at": "2026-07-11 09:00:00",
        },
    ]


@pytest.mark.asyncio
async def test_purchase_history_rejects_cross_user_report_links(client, fresh_all_db):
    owner = await _register(client, "history-isolation-owner@example.com")
    other_user = await _register(client, "history-isolation-other@example.com")
    _, other_purchase_id = await _insert_purchase(
        other_user["id"],
        "Private To Other User Ltd",
        report_status="done",
        purchase_status="paid",
        created_at="2026-07-12 11:00:00",
    )
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE purchases SET user_id=? WHERE id=?",
            (owner["id"], other_purchase_id),
        )
        await db.commit()

    await client.post(
        "/auth/login",
        data={"email": owner["email"], "password": "password123"},
    )
    response = await client.get("/account/purchases")

    assert response.status_code == 200, response.text
    assert response.json() == []
