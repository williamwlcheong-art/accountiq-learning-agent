"""Checks for the October 2026 code review fixes (startup, auth, uploads, retries, webhooks)."""
import aiosqlite
import pytest

import auth
import db as db_module
import main as main_module
from db import DB_PATH
from test_payments import _register_and_upload, _valuation_answers


def test_startup_refuses_unsafe_secret_keys():
    for key in ["", auth.SECRET_KEY_PLACEHOLDER, "short-key"]:
        with pytest.raises(RuntimeError):
            main_module.check_startup_config(key, False, "")
    main_module.check_startup_config("x" * 64, False, "")


def test_startup_refuses_e2e_mode_with_live_stripe_key():
    with pytest.raises(RuntimeError):
        main_module.check_startup_config("x" * 64, True, "sk_live_abc")
    main_module.check_startup_config("x" * 64, True, "sk_test_abc")
    main_module.check_startup_config("x" * 64, False, "sk_live_abc")


async def _paid_report(client, monkeypatch, email):
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    async def no_generation(_report_id):
        return None

    monkeypatch.setattr(main_module, "_generate_report", no_generation)
    company_id = await _register_and_upload(client, email=email)
    created = await client.post("/wizard/report/checkout", json={
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": _valuation_answers(),
        "idempotency_key": f"review-fixes-{email}",
    })
    assert created.status_code == 201, created.text
    return created.json()["report_id"]


@pytest.mark.asyncio
async def test_restart_fails_interrupted_reports_so_they_can_be_retried(client, fresh_all_db, monkeypatch):
    report_id = await _paid_report(client, monkeypatch, "interrupted@example.com")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reports SET status='generating' WHERE id=?", (report_id,))
        await db.commit()

    assert db_module.fail_interrupted_reports() == 1

    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT status, error_message FROM reports WHERE id=?", (report_id,)
        )).fetchone()
    assert row == ("failed", db_module.INTERRUPTED_REPORT_MESSAGE)
    retry = await client.post(f"/wizard/report/{report_id}/retry")
    assert retry.status_code == 200, retry.text


@pytest.mark.asyncio
async def test_retry_stops_after_three_attempts(client, fresh_all_db, monkeypatch):
    report_id = await _paid_report(client, monkeypatch, "retries@example.com")
    for attempt in range(main_module.MAX_REPORT_RETRIES + 1):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE reports SET status='failed' WHERE id=?", (report_id,))
            await db.commit()
        response = await client.post(f"/wizard/report/{report_id}/retry")
        expected = 200 if attempt < main_module.MAX_REPORT_RETRIES else 429
        assert response.status_code == expected, (attempt, response.text)


@pytest.mark.asyncio
async def test_login_locks_after_repeated_failures(client, fresh_db):
    auth._login_failures.clear()
    await client.post("/auth/register", data={"email": "lock@example.com", "password": "password123"})
    client.cookies.clear()
    for _ in range(auth.LOGIN_MAX_FAILURES):
        bad = await client.post("/auth/login", data={"email": "lock@example.com", "password": "wrong-password"})
        assert bad.status_code == 401
    locked = await client.post("/auth/login", data={"email": "lock@example.com", "password": "password123"})
    assert locked.status_code == 429
    auth._login_failures.clear()
    ok = await client.post("/auth/login", data={"email": "lock@example.com", "password": "password123"})
    assert ok.status_code == 200


def test_session_cookie_is_secure_unless_turned_off(monkeypatch):
    import importlib

    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    try:
        assert importlib.reload(auth).COOKIE_SECURE is True
        monkeypatch.setenv("COOKIE_SECURE", "false")
        assert importlib.reload(auth).COOKIE_SECURE is False
    finally:
        monkeypatch.setenv("COOKIE_SECURE", "false")
        importlib.reload(auth)


@pytest.mark.asyncio
async def test_upload_over_the_cap_is_refused_and_not_kept(client, fresh_all_db, monkeypatch):
    monkeypatch.setattr(main_module, "MAX_UPLOAD_BYTES", 1024)
    await client.post("/auth/register", data={"email": "big@example.com", "password": "password123"})
    response = await client.post(
        "/wizard/upload",
        data={"business_name": "Big File Ltd"},
        files={"file": ("big.pdf", b"%PDF" + b"0" * 4096, "application/pdf")},
    )
    assert response.status_code == 413, response.text
    async with aiosqlite.connect(DB_PATH) as db:
        count = (await (await db.execute("SELECT COUNT(*) FROM documents")).fetchone())[0]
    assert count == 0


@pytest.mark.asyncio
async def test_refund_for_unknown_purchase_is_acknowledged(client, fresh_all_db, monkeypatch):
    event = {
        "type": "charge.refunded",
        "data": {"object": {
            "payment_intent": "pi_not_ours",
            "amount": 120000,
            "amount_refunded": 120000,
            "refunded": True,
        }},
    }
    monkeypatch.setattr(main_module, "construct_webhook_event", lambda *_args: event)
    response = await client.post(
        "/payments/stripe/webhook", content=b"refund", headers={"stripe-signature": "sig"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["ignored"] is True
