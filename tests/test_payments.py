import aiosqlite
import pytest

from db import DB_PATH, init_db
from payments import checkout_config, stripe_enabled


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
