"""Tests for the customer order workspace foundation."""
import json

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

import db as _db_module
import main as _main_module


async def _register(client, email="order-user@example.com", password="correcthorse"):
    response = await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _seed_order(
    *,
    user_id: int,
    business_name: str = "Seeded Order Co",
    document_status: str = "done",
    with_financial_row: bool = True,
) -> int:
    async with aiosqlite.connect(_db_module.DB_PATH) as conn:
        company_cur = await conn.execute(
            """
            INSERT INTO companies (name, exchange, sector, description, user_id)
            VALUES (?, 'Private', 'Professional Services', ?, ?)
            """,
            (
                business_name,
                "A professional services firm used for order workspace tests.",
                user_id,
            ),
        )
        company_id = company_cur.lastrowid
        document_cur = await conn.execute(
            """
            INSERT INTO documents (company_id, filename, filepath, user_id, extraction_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                company_id,
                f"{business_name.lower().replace(' ', '-')}.pdf",
                f"/tmp/{business_name.lower().replace(' ', '-')}.pdf",
                user_id,
                document_status,
            ),
        )
        document_id = document_cur.lastrowid
        if with_financial_row:
            await conn.execute(
                """
                INSERT INTO financial_rows
                    (document_id, company_id, statement, row_key, row_label, period, value)
                VALUES (?, ?, 'pnl', 'revenue', 'Revenue', '2025', 1250000)
                """,
                (document_id, company_id),
            )
        order_cur = await conn.execute(
            """
            INSERT INTO report_orders (
                user_id, company_id, document_id, product_key, report_type,
                price_cents, gst_cents, currency
            )
            VALUES (?, ?, ?, 'business_valuation', 'valuation_advisory', 225000, 33750, 'NZD')
            """,
            (user_id, company_id, document_id),
        )
        await conn.commit()
        return int(order_cur.lastrowid)


@pytest.mark.asyncio
async def test_products_catalog_lists_initial_products(client, fresh_all_db):
    await _register(client)

    response = await client.get("/wizard/products")

    assert response.status_code == 200, response.text
    products = response.json()
    by_key = {product["key"]: product for product in products}
    assert set(by_key) == {"business_valuation", "bank_credit_paper", "advisory_consultation"}
    assert by_key["business_valuation"]["enabled"] is True
    assert by_key["business_valuation"]["report_type"] == "valuation_advisory"
    assert by_key["business_valuation"]["price_cents"] == 225000
    assert by_key["business_valuation"]["gst_cents"] == 33750
    assert by_key["bank_credit_paper"]["enabled"] is False
    assert by_key["advisory_consultation"]["enabled"] is False


@pytest.mark.asyncio
async def test_upload_creates_customer_order_and_order_history(client, fresh_all_db, monkeypatch):
    monkeypatch.setattr(_main_module, "E2E_MODE", True, raising=False)
    await _register(client)

    upload = await client.post(
        "/wizard/upload",
        data={"business_name": "Order Upload Co", "product_key": "business_valuation"},
        files={"file": ("statements.pdf", b"%PDF-1.4 order fixture", "application/pdf")},
    )

    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["company_id"] > 0
    assert body["document_id"] > 0
    assert body["order_id"] > 0
    assert body["product_key"] == "business_valuation"
    assert body["price_cents"] == 225000
    assert body["gst_cents"] == 33750
    assert body["order_status"] == "validating"

    orders_response = await client.get("/wizard/orders")
    assert orders_response.status_code == 200, orders_response.text
    orders = orders_response.json()
    assert len(orders) == 1
    order = orders[0]
    assert order["order_id"] == body["order_id"]
    assert order["business_name"] == "Order Upload Co"
    assert order["document_status"] == "done"
    assert order["validation_status"] == "passed"
    assert order["status"] == "awaiting_payment"


@pytest.mark.asyncio
async def test_order_detail_is_isolated_between_users(client, fresh_all_db, monkeypatch):
    monkeypatch.setattr(_main_module, "E2E_MODE", True, raising=False)
    await _register(client, "alice-order@example.com")
    upload = await client.post(
        "/wizard/upload",
        data={"business_name": "Alice Order Co"},
        files={"file": ("alice.pdf", b"%PDF-1.4 alice fixture", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    order_id = upload.json()["order_id"]

    async with AsyncClient(
        transport=ASGITransport(app=_main_module.app),
        base_url="http://test",
    ) as other:
        await _register(other, "bob-order@example.com")
        detail = await other.get(f"/wizard/orders/{order_id}")
        orders = await other.get("/wizard/orders")

    assert detail.status_code == 404, detail.text
    assert orders.status_code == 200, orders.text
    assert orders.json() == []


@pytest.mark.asyncio
async def test_order_validation_syncs_from_document_rows(client, fresh_all_db):
    user = await _register(client)
    order_id = await _seed_order(
        user_id=user["id"],
        business_name="Clarification Co",
        document_status="done",
        with_financial_row=False,
    )

    needs_info = await client.get(f"/wizard/orders/{order_id}")
    assert needs_info.status_code == 200, needs_info.text
    assert needs_info.json()["validation_status"] == "needs_clarification"
    assert needs_info.json()["status"] == "needs_clarification"

    async with aiosqlite.connect(_db_module.DB_PATH) as conn:
        async with conn.execute(
            "SELECT company_id, document_id FROM report_orders WHERE id=?",
            (order_id,),
        ) as cur:
            row = await cur.fetchone()
        await conn.execute(
            """
            INSERT INTO financial_rows
                (document_id, company_id, statement, row_key, row_label, period, value)
            VALUES (?, ?, 'pnl', 'ebitda', 'EBITDA', '2025', 235000)
            """,
            (row[1], row[0]),
        )
        await conn.commit()

    passed = await client.get(f"/wizard/orders/{order_id}")
    assert passed.status_code == 200, passed.text
    assert passed.json()["validation_status"] == "passed"
    assert passed.json()["status"] == "awaiting_payment"


@pytest.mark.asyncio
async def test_demo_generation_is_blocked_without_e2e_or_admin(client, fresh_all_db, monkeypatch):
    monkeypatch.setattr(_main_module, "E2E_MODE", False, raising=False)
    user = await _register(client)
    order_id = await _seed_order(user_id=user["id"])

    response = await client.post(f"/wizard/orders/{order_id}/generate-demo-report")

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Payment integration required before generation"


@pytest.mark.asyncio
async def test_demo_generation_creates_draft_and_moves_order_to_review(client, fresh_all_db, monkeypatch):
    monkeypatch.setattr(_main_module, "E2E_MODE", True, raising=False)
    user = await _register(client)
    order_id = await _seed_order(user_id=user["id"], business_name="Demo Draft Co")

    response = await client.post(f"/wizard/orders/{order_id}/generate-demo-report")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["order_id"] == order_id
    assert body["report_id"] > 0

    detail = await client.get(f"/wizard/orders/{order_id}")
    assert detail.status_code == 200, detail.text
    order = detail.json()
    assert order["report_id"] == body["report_id"]
    assert order["payment_status"] == "demo"
    assert order["review_status"] == "awaiting_review"
    assert order["delivery_status"] == "not_ready"
    assert order["status"] == "awaiting_review"

    async with aiosqlite.connect(_db_module.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT status, content FROM reports WHERE id=?",
            (body["report_id"],),
        ) as cur:
            report = await cur.fetchone()

    assert report["status"] == "done"
    assert "Demo Draft Co" in json.loads(report["content"])["business_overview"]
