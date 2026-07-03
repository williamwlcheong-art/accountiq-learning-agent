import aiosqlite
import pytest

from db import DB_PATH, init_db
from payments import checkout_config, stripe_enabled
import main as main_module


@pytest.mark.asyncio
async def test_payment_tables_exist(fresh_all_db):
    init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(purchases)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
        async with db.execute("PRAGMA index_list(purchases)") as cur:
            indexes = {row[1] for row in await cur.fetchall()}

    assert {
        "id",
        "report_id",
        "user_id",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "amount_cents",
        "currency",
        "status",
        "paid_at",
        "created_at",
    }.issubset(columns)
    assert {
        "idx_purchases_user",
        "idx_purchases_report",
        "idx_purchases_status",
    }.issubset(indexes)


def test_checkout_config_defaults(monkeypatch):
    for key in [
        "ACCOUNTIQ_VALUATION_PRICE_CENTS",
        "ACCOUNTIQ_CURRENCY",
        "ACCOUNTIQ_PAYMENT_SUCCESS_URL",
        "ACCOUNTIQ_PAYMENT_CANCEL_URL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = checkout_config()

    assert config.price_cents == 49500
    assert config.currency == "nzd"
    assert config.success_url == "http://localhost:3000/wizard?payment=success"
    assert config.cancel_url == "http://localhost:3000/wizard?payment=cancelled"


def test_stripe_enabled_requires_secret_key(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert stripe_enabled() is False

    monkeypatch.setenv("STRIPE_SECRET_KEY", "  ")
    assert stripe_enabled() is False

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    assert stripe_enabled() is True


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


async def _register_and_upload(client, email="buyer@example.com"):
    await client.post("/auth/register", data={"email": email, "password": "password123"})
    upload = await client.post(
        "/wizard/upload",
        data={"business_name": "Paid Valuation Ltd"},
        files={"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    return upload.json()["company_id"]


@pytest.mark.asyncio
async def test_e2e_checkout_creates_queued_report(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    company_id = await _register_and_upload(client)
    res = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
        },
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "queued"
    assert body["checkout_url"] is None

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, paid_at FROM purchases WHERE report_id=?",
            (body["report_id"],),
        ) as cur:
            purchase = await cur.fetchone()
    assert purchase["status"] == "paid"
    assert purchase["paid_at"] is not None


@pytest.mark.asyncio
async def test_checkout_only_accepts_valuation(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    company_id = await _register_and_upload(client, email="forecast-buyer@example.com")
    res = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "financial_forecast",
            "intake_answers": {},
        },
    )

    assert res.status_code == 400, res.text
    assert "valuation_advisory" in res.text


@pytest.mark.asyncio
async def test_valuation_generate_requires_checkout(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    company_id = await _register_and_upload(client, email="direct-buyer@example.com")
    res = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
        },
    )

    assert res.status_code == 409, res.text
    assert "checkout" in res.text.lower()
