import asyncio
import copy

import aiosqlite
import pytest

from db import DB_PATH, init_db
from payments import CheckoutSession, checkout_config, stripe_enabled
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
        "fcff_assumptions": {
            "forecast": {
                "horizon_years": 3,
                "revenue_growth_rate": 0.08,
                "terminal_growth_rate": 0.03,
                "confirmed": True,
            },
            "depreciation": {
                "rate": 0.028, "confirmed": True, "rationale": "Matches accounts.",
                "confirmation_method": "calculated", "confirmation_source": "financial_statements",
                "source_period": "2025",
            },
            "capex": {
                "rate": 0.04, "confirmed": True, "rationale": "Confirmed plan.",
                "confirmation_method": "manual", "confirmation_source": "customer",
            },
            "operating_nwc": {
                "rate": 0.124, "confirmed": True, "rationale": "Matches accounts.",
                "confirmation_method": "calculated", "confirmation_source": "financial_statements",
                "source_period": "2025",
            },
        },
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO wacc_assumption_sets
                (name, version, status, active, risk_free_rate, equity_risk_premium,
                 beta, beta_type, cost_of_debt, target_debt_weight,
                 target_equity_weight, additional_premium, scenario_spread,
                 source_references, publisher, as_of_date, rationale, approved_at,
                 approved_by_user_id)
            VALUES ('Synthetic payment test', 1, 'approved', 1, '4', '5.5',
                    '1', 'synthetic_test', '6', '30', '70', '2', '1',
                    'Deterministic payment fixture', 'Test suite', '2026-07-01',
                    'Automated checkout tests only', '2026-07-01 00:00:00',
                    (SELECT id FROM users WHERE email=?))
            """,
            (email,),
        )
        await db.commit()
    upload = await client.post(
        "/wizard/upload",
        data={"business_name": "Paid Valuation Ltd"},
        files={"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    return upload.json()["company_id"]


@pytest.mark.asyncio
async def test_checkout_invalid_valuation_inputs_fail_before_persistence_or_stripe(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    monkeypatch.setattr(main_module, "stripe_enabled", lambda: True)
    stripe_calls = []
    monkeypatch.setattr(
        main_module,
        "create_checkout_session",
        lambda **kwargs: stripe_calls.append(kwargs),
    )
    company_id = await _register_and_upload(client, email="clarification@example.com")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE financial_rows SET currency='AUD' WHERE company_id=? AND row_key='cash_and_bank'",
            (company_id,),
        )
        await db.commit()

    response = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
            "idempotency_key": "clarification-checkout-key",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "state": "needs_clarification",
        "code": "needs_clarification",
        "reason_code": "mixed_currency",
        "message": "All valuation inputs must use one valid three-letter currency code.",
        "details": {"currencies": ["AUD", "NZD"]},
    }
    assert stripe_calls == []
    async with aiosqlite.connect(DB_PATH) as db:
        assert (await (await db.execute("SELECT COUNT(*) FROM reports")).fetchone())[0] == 0
        assert (await (await db.execute("SELECT COUNT(*) FROM purchases")).fetchone())[0] == 0
        assert (await (await db.execute("SELECT COUNT(*) FROM report_input_snapshots")).fetchone())[0] == 0


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
            "idempotency_key": "e2e-checkout-primary",
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
        async with db.execute(
            "SELECT id, canonical_digest FROM report_input_snapshots WHERE report_id=?",
            (body["report_id"],),
        ) as cur:
            snapshot = await cur.fetchone()
        async with db.execute(
            "SELECT COUNT(*) AS n FROM report_snapshot_rows WHERE snapshot_id=?",
            (snapshot["id"],),
        ) as cur:
            snapshot_rows = (await cur.fetchone())["n"]
    assert purchase["status"] == "paid"
    assert purchase["paid_at"] is not None
    assert len(snapshot["canonical_digest"]) == 64
    assert snapshot_rows > 0


@pytest.mark.asyncio
async def test_checkout_accepts_frontend_precision_for_non_terminating_calculated_ratios(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="ratio-checkout@example.com")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE financial_rows SET value=30 WHERE company_id=? AND row_key='revenue'",
            (company_id,),
        )
        await db.execute(
            "UPDATE financial_rows SET value=-1 WHERE company_id=? AND row_key='depreciation'",
            (company_id,),
        )
        await db.execute(
            "UPDATE financial_rows SET value=2 WHERE company_id=? AND row_key='trade_debtors'",
            (company_id,),
        )
        await db.execute(
            "UPDATE financial_rows SET value=0 WHERE company_id=? AND row_key IN ('inventory', 'trade_creditors')",
            (company_id,),
        )
        await db.commit()
    answers = _valuation_answers()
    answers["fcff_assumptions"]["depreciation"]["rate"] = 0.0333333333
    answers["fcff_assumptions"]["operating_nwc"]["rate"] = 0.0666666667

    response = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": answers,
            "idempotency_key": "non-terminating-ratio-checkout",
        },
    )

    assert response.status_code == 201, response.text
    async with aiosqlite.connect(DB_PATH) as db:
        frozen_json = (
            await (
                await db.execute(
                    "SELECT frozen_inputs FROM report_input_snapshots WHERE report_id=?",
                    (response.json()["report_id"],),
                )
            ).fetchone()
        )[0]
    assert '"rate":0.0333333333' in frozen_json
    assert '"rate":0.0666666667' in frozen_json


@pytest.mark.asyncio
async def test_checkout_idempotency_key_reuses_order(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="idempotent@example.com")
    payload = {
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": _valuation_answers(),
        "idempotency_key": "checkout-attempt-12345678",
    }

    first = await client.post("/wizard/report/checkout", json=payload)
    second = await client.post("/wizard/report/checkout", json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["report_id"] == first.json()["report_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        assert (await (await db.execute("SELECT COUNT(*) FROM purchases")).fetchone())[0] == 1
        assert (await (await db.execute("SELECT COUNT(*) FROM report_input_snapshots")).fetchone())[0] == 1


@pytest.mark.asyncio
async def test_generation_calculates_complete_fcff_before_research_or_claude(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="fcff-generation@example.com")
    created = await client.post("/wizard/report/checkout", json={
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": _valuation_answers(),
        "idempotency_key": "fcff-generation-order",
    })
    assert created.status_code == 201, created.text
    report_id = created.json()["report_id"]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reports SET status='queued', content='partial' WHERE id=?",
            (report_id,),
        )
        await db.commit()

    original_builder = main_module.build_valuation_inputs
    build_calls = []

    def require_complete_fcff(*args, **kwargs):
        build_calls.append(kwargs)
        return original_builder(*args, **kwargs)

    def fail_calculation(_inputs):
        raise ValueError("deterministic calculation failed")

    async def forbidden(*_args, **_kwargs):
        pytest.fail("Deterministic failure must stop before research or Claude")

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "build_valuation_inputs", require_complete_fcff)
    monkeypatch.setattr(main_module, "calculate_fcff", fail_calculation)
    monkeypatch.setattr(main_module, "run_valuation_research", forbidden)
    monkeypatch.setattr(main_module, "_call_claude_for_report", forbidden)

    await main_module._generate_report(report_id)

    assert build_calls == [{"require_fcff": True}]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, content, error_message FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            report = dict(await cur.fetchone())
    assert report == {
        "status": "failed",
        "content": None,
        "error_message": (
            "We couldn't generate a complete report. Please retry, or contact support "
            "if the problem continues."
        ),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("schema_version", "engine_version"),
    [
        ("1", "typed-inputs-v2"),
        ("1", "fcff-assumptions-v1"),
        ("2", "fcff-assumptions-v1"),
    ],
)
async def test_checkout_legacy_pending_snapshot_requires_restart_without_stripe_or_mutation(
    client, fresh_all_db, monkeypatch, schema_version, engine_version
):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="legacy-checkout@example.com")
    payload = {
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": _valuation_answers(),
        "idempotency_key": "legacy-snapshot-checkout-key",
    }
    created = await client.post("/wizard/report/checkout", json=payload)
    assert created.status_code == 201, created.text
    report_id = created.json()["report_id"]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reports SET status='pending_payment' WHERE id=?", (report_id,)
        )
        await db.execute(
            "UPDATE purchases SET status='pending', paid_at=NULL WHERE report_id=?", (report_id,)
        )
        await db.execute(
            """
            UPDATE report_input_snapshots
            SET schema_version=?, valuation_engine_version=?
            WHERE report_id=?
            """,
            (schema_version, engine_version, report_id),
        )
        await db.commit()
        before = await (
            await db.execute(
                """
                SELECT r.status, p.status, p.stripe_checkout_session_id, p.stripe_checkout_url,
                       ris.schema_version, ris.valuation_engine_version, ris.canonical_digest
                FROM reports r
                JOIN purchases p ON p.report_id=r.id
                JOIN report_input_snapshots ris ON ris.report_id=r.id
                WHERE r.id=?
                """,
                (report_id,),
            )
        ).fetchone()

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "stripe_enabled", lambda: True)
    stripe_calls = []
    monkeypatch.setattr(
        main_module, "create_checkout_session", lambda **kwargs: stripe_calls.append(kwargs)
    )

    response = await client.post("/wizard/report/checkout", json=payload)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "legacy_snapshot_restart_required"
    assert stripe_calls == []
    async with aiosqlite.connect(DB_PATH) as db:
        after = await (
            await db.execute(
                """
                SELECT r.status, p.status, p.stripe_checkout_session_id, p.stripe_checkout_url,
                       ris.schema_version, ris.valuation_engine_version, ris.canonical_digest
                FROM reports r
                JOIN purchases p ON p.report_id=r.id
                JOIN report_input_snapshots ris ON ris.report_id=r.id
                WHERE r.id=?
                """,
                (report_id,),
            )
        ).fetchone()
    assert after == before


@pytest.mark.asyncio
async def test_checkout_idempotency_key_rejects_changed_nested_capex_before_external_call(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="changed-idempotency@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "stripe_enabled", lambda: True)
    external_calls = 0

    def create_session(**_kwargs):
        nonlocal external_calls
        external_calls += 1
        return CheckoutSession("cs_original", "https://checkout.stripe.test/original")

    monkeypatch.setattr(main_module, "create_checkout_session", create_session)
    payload = {
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": _valuation_answers(),
        "idempotency_key": "changed-capex-checkout-key",
    }
    first = await client.post("/wizard/report/checkout", json=payload)
    changed = copy.deepcopy(payload)
    changed["intake_answers"]["fcff_assumptions"]["capex"]["rate"] = 0.09
    second = await client.post("/wizard/report/checkout", json=changed)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json()["detail"]["code"] == "idempotency_key_reused"
    assert external_calls == 1


@pytest.mark.asyncio
async def test_checkout_recovers_session_after_local_persistence_failure(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="stripe-recovery@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "stripe_enabled", lambda: True)
    calls = 0

    def create_session(**_kwargs):
        nonlocal calls
        calls += 1
        return CheckoutSession("cs_recoverable", "https://checkout.stripe.test/recoverable")

    monkeypatch.setattr(main_module, "create_checkout_session", create_session)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TRIGGER fail_checkout_session_write
            BEFORE UPDATE OF stripe_checkout_session_id ON purchases
            BEGIN
                SELECT RAISE(FAIL, 'simulated local write failure');
            END
        """)
        await db.commit()

    payload = {
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": _valuation_answers(),
        "idempotency_key": "stripe-recovery-checkout",
    }
    with pytest.raises(aiosqlite.IntegrityError, match="simulated"):
        await client.post("/wizard/report/checkout", json=payload)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DROP TRIGGER fail_checkout_session_write")
        await db.commit()

    retry = await client.post("/wizard/report/checkout", json=payload)

    assert retry.status_code == 201, retry.text
    assert retry.json()["checkout_url"] == "https://checkout.stripe.test/recoverable"
    assert calls == 2
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT stripe_checkout_session_id, stripe_checkout_url FROM purchases"
        )).fetchone()
    assert row == ("cs_recoverable", "https://checkout.stripe.test/recoverable")


@pytest.mark.asyncio
async def test_concurrent_checkout_key_reuses_one_order(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="concurrent-key@example.com")
    payload = {
        "company_id": company_id,
        "report_type": "valuation_advisory",
        "intake_answers": _valuation_answers(),
        "idempotency_key": "concurrent-checkout-key",
    }

    first, second = await asyncio.gather(
        client.post("/wizard/report/checkout", json=payload),
        client.post("/wizard/report/checkout", json=payload),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["report_id"] == second.json()["report_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        assert (await (await db.execute("SELECT COUNT(*) FROM reports")).fetchone())[0] == 1
        assert (await (await db.execute("SELECT COUNT(*) FROM purchases")).fetchone())[0] == 1
        assert (await (await db.execute("SELECT COUNT(*) FROM report_input_snapshots")).fetchone())[0] == 1


@pytest.mark.asyncio
async def test_duplicate_webhook_schedules_generation_once(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="webhook-once@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "stripe_enabled", lambda: True)
    monkeypatch.setattr(
        main_module,
        "create_checkout_session",
        lambda **_kwargs: CheckoutSession(
            "cs_webhook_once", "https://checkout.stripe.test/webhook-once"
        ),
    )
    checkout = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
            "idempotency_key": "webhook-once-checkout",
        },
    )
    assert checkout.status_code == 201, checkout.text
    generated = []

    async def record_generation(report_id, *_args, **_kwargs):
        generated.append(report_id)

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_webhook_once",
            "payment_intent": "pi_once",
            "payment_status": "paid",
        }},
    }
    monkeypatch.setattr(main_module, "construct_webhook_event", lambda *_args: event)
    monkeypatch.setattr(main_module, "_generate_report", record_generation)

    first = await client.post(
        "/payments/stripe/webhook", content=b"event", headers={"stripe-signature": "sig"}
    )
    second = await client.post(
        "/payments/stripe/webhook", content=b"event", headers={"stripe-signature": "sig"}
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert generated == [checkout.json()["report_id"]]


@pytest.mark.asyncio
async def test_unpaid_checkout_completion_does_not_queue_report(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="unpaid-checkout@example.com")
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "stripe_enabled", lambda: True)
    monkeypatch.setattr(
        main_module,
        "create_checkout_session",
        lambda **_kwargs: CheckoutSession("cs_unpaid", "https://checkout.stripe.test/unpaid"),
    )
    checkout = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
            "idempotency_key": "unpaid-checkout-key",
        },
    )
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_unpaid",
            "payment_intent": "pi_unpaid",
            "payment_status": "unpaid",
        }},
    }
    monkeypatch.setattr(main_module, "construct_webhook_event", lambda *_args: event)

    response = await client.post(
        "/payments/stripe/webhook", content=b"event", headers={"stripe-signature": "sig"}
    )

    assert response.json() == {"received": True, "ignored": True}
    async with aiosqlite.connect(DB_PATH) as db:
        purchase = await (await db.execute("SELECT status FROM purchases")).fetchone()
        report = await (await db.execute("SELECT status FROM reports")).fetchone()
    assert purchase[0] == "pending"
    assert report[0] == "pending_payment"
    assert checkout.status_code == 201


@pytest.mark.asyncio
async def test_paid_webhook_reconciles_missing_local_session_mapping(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="reconcile-checkout@example.com")
    checkout = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
            "idempotency_key": "reconcile-checkout-key",
        },
    )
    report_id = checkout.json()["report_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        purchase_id = (await (await db.execute(
            "SELECT id FROM purchases WHERE report_id=?", (report_id,)
        )).fetchone())[0]
        await db.execute(
            "UPDATE purchases SET status='pending', paid_at=NULL, stripe_checkout_session_id=NULL WHERE id=?",
            (purchase_id,),
        )
        await db.execute("UPDATE reports SET status='pending_payment' WHERE id=?", (report_id,))
        await db.commit()
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    event = {
        "type": "checkout.session.async_payment_succeeded",
        "data": {"object": {
            "id": "cs_reconciled",
            "payment_intent": "pi_reconciled",
            "payment_status": "paid",
            "metadata": {"purchase_id": str(purchase_id)},
        }},
    }
    async def record_generation(_report_id):
        return None

    monkeypatch.setattr(main_module, "_generate_report", record_generation)
    monkeypatch.setattr(main_module, "construct_webhook_event", lambda *_args: event)

    response = await client.post(
        "/payments/stripe/webhook", content=b"event", headers={"stripe-signature": "sig"}
    )

    assert response.status_code == 200, response.text
    async with aiosqlite.connect(DB_PATH) as db:
        purchase = await (await db.execute(
            "SELECT status, stripe_checkout_session_id FROM purchases WHERE id=?", (purchase_id,)
        )).fetchone()
        report = await (await db.execute(
            "SELECT status FROM reports WHERE id=?", (report_id,)
        )).fetchone()
    assert purchase == ("paid", "cs_reconciled")
    assert report[0] in {"queued", "generating", "awaiting_review"}


@pytest.mark.asyncio
async def test_checkout_schema_has_unique_user_idempotency_key(fresh_all_db):
    init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(purchases)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
        async with db.execute("PRAGMA index_list(purchases)") as cur:
            indexes = {row[1] for row in await cur.fetchall()}
    assert "checkout_idempotency_key" in columns
    assert "idx_purchases_user_checkout_key" in indexes


@pytest.mark.asyncio
async def test_wizard_readiness_reports_authoritative_sources(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="ready-buyer@example.com")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM documents WHERE company_id=? ORDER BY id DESC LIMIT 1",
            (company_id,),
        ) as cur:
            document_id = (await cur.fetchone())["id"]

    response = await client.get(
        f"/wizard/company/{company_id}/readiness?document_id={document_id}"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "ready"
    assert body["source_periods"]
    assert body["source_periods"][0]["filename"] == "sample.pdf"
    assert body["profile"] == {
        "name": "Paid Valuation Ltd",
        "sector": None,
        "description": None,
        "country": "NZ",
        "exchange": "Private",
        "management_team_count": 0,
        "ebitda_adjustment_count": 0,
    }
    assert body["checkout"] == {
        "report_type": "valuation_advisory",
        "amount_cents": 49500,
        "currency": "nzd",
    }


@pytest.mark.asyncio
async def test_wizard_readiness_is_owner_scoped(client, fresh_all_db, monkeypatch):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="owner@example.com")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM documents WHERE company_id=? ORDER BY id DESC LIMIT 1",
            (company_id,),
        ) as cur:
            document_id = (await cur.fetchone())[0]

    await client.post("/auth/logout")
    await client.post("/auth/register", data={"email": "other@example.com", "password": "password123"})
    response = await client.get(
        f"/wizard/company/{company_id}/readiness?document_id={document_id}"
    )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_checkout_revalidates_readiness_and_returns_structured_conflict(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="readiness-race@example.com")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE documents SET extraction_status='failed' WHERE company_id=?",
            (company_id,),
        )
        await db.commit()

    response = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
            "idempotency_key": "readiness-race-checkout",
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "state": "failed",
        "code": "extraction_failed",
        "message": "We could not extract this document. Upload a clearer financial statement to continue.",
    }
    async with aiosqlite.connect(DB_PATH) as db:
        assert (await (await db.execute("SELECT COUNT(*) FROM reports")).fetchone())[0] == 0
        assert (await (await db.execute("SELECT COUNT(*) FROM purchases")).fetchone())[0] == 0


@pytest.mark.asyncio
async def test_snapshot_missing_retained_file_returns_serviceability_conflict(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="missing-file@example.com")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE documents SET file_hash=NULL, filepath='/tmp/accountiq-missing-retained-file.pdf' WHERE company_id=?",
            (company_id,),
        )
        await db.commit()

    response = await client.post(
        "/wizard/report/checkout",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": _valuation_answers(),
            "idempotency_key": "missing-file-checkout",
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "source_file_unavailable"
    assert "retained file is missing" in response.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_non_valuation_generate_does_not_require_retained_file(
    client, fresh_all_db, monkeypatch
):
    monkeypatch.setenv("ACCOUNTIQ_E2E_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    company_id = await _register_and_upload(client, email="internal-report@example.com")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE documents SET file_hash=NULL, filepath='/tmp/accountiq-missing-internal-file.pdf' WHERE company_id=?",
            (company_id,),
        )
        await db.commit()

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "report_type": "financial_forecast",
            "intake_answers": {},
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"


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
