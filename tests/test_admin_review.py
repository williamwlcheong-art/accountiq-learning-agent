import json

import aiosqlite
import pytest

from db import DB_PATH
import main as main_module


async def _register(client, email: str, password: str = "password123"):
    res = await client.post("/auth/register", data={"email": email, "password": password})
    assert res.status_code == 201, res.text
    me = await client.get("/auth/me")
    assert me.status_code == 200, me.text
    return me.json()


async def _register_admin(client, email: str = "reviewer@example.com", password: str = "password123"):
    """Register and explicitly provision an admin test user."""
    r = await client.post(
        "/auth/register",
        data={"email": email, "password": password},
    )
    from account_helpers import provision_test_admin
    await provision_test_admin(email)
    me = await client.get("/auth/me")
    assert me.status_code == 200, me.text
    return me.json()

async def _login(client, email: str, password: str = "password123"):
    res = await client.post("/auth/login", data={"email": email, "password": password})
    assert res.status_code == 200, res.text


def _valuation_answers():
    return {
        "forecast_horizon": 3,
        "revenue_growth_cagr": 8,
        "terminal_growth_rate": 3,
        "rq_revenue_quality": 3,
        "rq_owner_dependency": 3,
        "rq_ebitda_growth": 3,
        "rq_customer_concentration": 3,
        "rq_gross_margin": 3,
        "rq_competitive_barriers": 3,
        "rq_growth_outlook": 3,
        "rq_management_depth": 3,
    }


async def _create_paid_valuation(client, company_name: str = "Review Queue Ltd"):
    upload = await client.post(
        "/wizard/upload",
        data={"business_name": company_name},
        files={"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text

    checkout = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": upload.json()["company_id"],
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
        },
    )
    assert checkout.status_code == 201, checkout.text
    return checkout.json()["report_id"]


async def _insert_awaiting_review_report(
    user_id: int,
    *,
    purchase_status: str | None = "paid",
    paid_at: bool = True,
):
    content = {
        "valuation_summary": {
            "narrative": "Draft valuation summary ready for review.",
            "table": {"headers": ["Metric", "Value"], "rows": [["Revenue", "$1,250,000"]]},
        },
        "disclaimer": "This report is indicative only and is not financial advice under the FMCA. It should not be relied on without independent professional advice.",
    }
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES (?, 'Private', ?)",
            ("Approval Target Ltd", user_id),
        ) as cur:
            company_id = cur.lastrowid
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status, content)
            VALUES (?, ?, 'valuation_advisory', 'awaiting_review', ?)
            """,
            (company_id, user_id, json.dumps(content)),
        ) as cur:
            report_id = cur.lastrowid
        if purchase_status is not None:
            await db.execute(
                """
                INSERT INTO purchases (report_id, user_id, amount_cents, currency, status, paid_at)
                VALUES (?, ?, 49500, 'nzd', ?, CASE WHEN ? THEN datetime('now') ELSE NULL END)
                """,
                (report_id, user_id, purchase_status, paid_at),
            )
        await db.commit()
    return report_id


async def _report_status(report_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT company_id, status, completed_at FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            return await cur.fetchone()


async def _review_record(report_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT reviewer_user_id, status, approved_at
            FROM reviews
            WHERE report_id=?
            """,
            (report_id,),
        ) as cur:
            return await cur.fetchone()


@pytest.mark.asyncio
async def test_review_schema_supports_approval_audit(fresh_all_db):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(reviews)") as cur:
            columns = {row[1] for row in await cur.fetchall()}

    assert {
        "report_id",
        "reviewer_user_id",
        "status",
        "internal_notes",
        "customer_message",
        "created_at",
        "updated_at",
        "approved_at",
    } <= columns


@pytest.mark.asyncio
async def test_completed_paid_valuation_enters_awaiting_review_with_audit_record(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setenv("ACCOUNTIQ_REQUIRE_ADMIN_REVIEW", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    await _register(client, "buyer@example.com")
    report_id = await _create_paid_valuation(client)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, content, completed_at FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            report = await cur.fetchone()

    assert report["status"] == "awaiting_review"
    assert report["content"]
    assert report["completed_at"] is None
    review = await _review_record(report_id)
    assert review is not None
    assert review["status"] == "awaiting_review"
    assert review["reviewer_user_id"] is None
    assert review["approved_at"] is None


@pytest.mark.asyncio
async def test_admin_can_approve_report_and_user_can_view(client, fresh_all_db):
    buyer = await _register(client, "approval-buyer@example.com")
    report_id = await _insert_awaiting_review_report(buyer["id"])

    reviewer = await _register_admin(client)
    pending = await client.get("/admin/reports/pending")
    assert pending.status_code == 200, pending.text
    assert any(row["id"] == report_id for row in pending.json())

    approve = await client.post(f"/admin/reports/{report_id}/approve")
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "done"
    review = await _review_record(report_id)
    assert review is not None
    assert review["status"] == "approved"
    assert review["reviewer_user_id"] == reviewer["id"]
    assert review["approved_at"] is not None

    await _login(client, "approval-buyer@example.com")
    view = await client.get(f"/wizard/report/{report_id}/view")
    assert view.status_code == 200, view.text
    assert "Approval Target Ltd" in view.text


@pytest.mark.asyncio
async def test_user_cannot_view_report_awaiting_review(client, fresh_all_db):
    buyer = await _register(client, "draft-buyer@example.com")
    report_id = await _insert_awaiting_review_report(buyer["id"])

    view = await client.get(f"/wizard/report/{report_id}/view")

    assert view.status_code == 400, view.text
    assert "awaiting_review" in view.text


@pytest.mark.asyncio
async def test_regular_user_cannot_approve_report(client, fresh_all_db):
    buyer = await _register(client, "regular-reviewer@example.com")
    report_id = await _insert_awaiting_review_report(buyer["id"])

    res = await client.post(f"/admin/reports/{report_id}/approve")

    assert res.status_code == 403, res.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("purchase_status", "paid_at"),
    [
        (None, False),
        ("pending", False),
    ],
)
async def test_admin_cannot_approve_unpaid_report(client, fresh_all_db, purchase_status, paid_at):
    buyer = await _register(client, "unpaid-buyer@example.com")
    report_id = await _insert_awaiting_review_report(
        buyer["id"],
        purchase_status=purchase_status,
        paid_at=paid_at,
    )

    await _register_admin(client)
    res = await client.post(f"/admin/reports/{report_id}/approve")
    report = await _report_status(report_id)

    assert res.status_code == 409, res.text
    assert report["status"] == "awaiting_review"
    assert report["completed_at"] is None


@pytest.mark.asyncio
async def test_duplicate_approval_does_not_release_twice(client, fresh_all_db):
    buyer = await _register(client, "duplicate-approval-buyer@example.com")
    report_id = await _insert_awaiting_review_report(buyer["id"])

    await _register_admin(client)
    first = await client.post(f"/admin/reports/{report_id}/approve")
    second = await client.post(f"/admin/reports/{report_id}/approve")

    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_late_generation_task_does_not_regress_approved_report(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setenv("ACCOUNTIQ_REQUIRE_ADMIN_REVIEW", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    buyer = await _register(client, "late-generation-buyer@example.com")
    report_id = await _insert_awaiting_review_report(buyer["id"])

    await _register_admin(client)
    approve = await client.post(f"/admin/reports/{report_id}/approve")
    assert approve.status_code == 200, approve.text

    before = await _report_status(report_id)
    await main_module._generate_report(
        report_id,
        before["company_id"],
        buyer["id"],
        "valuation_advisory",
        _valuation_answers(),
    )
    after = await _report_status(report_id)

    assert after["status"] == "done"
    assert after["completed_at"] == before["completed_at"]
