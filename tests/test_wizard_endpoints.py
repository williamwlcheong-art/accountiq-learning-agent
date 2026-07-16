"""Unit tests for wizard-scoped endpoints (Phase 05.1)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as main_module
from main import app


def test_wizard_ebitda_endpoint_exists():
    """Route is registered (no 404 on the path itself)."""
    routes = {
        (r.path, tuple(sorted(r.methods or [])))
        for r in app.routes
        if hasattr(r, "path") and hasattr(r, "methods")
    }
    assert ("/wizard/company/{company_id}/ebitda-adjustments", ("GET",)) in routes, \
        f"Wizard ebitda-adjustments route missing. Found wizard routes: " \
        f"{[(path, methods) for path, methods in routes if '/wizard/' in path]}"


def test_wizard_ebitda_endpoint_requires_auth():
    """Unauthenticated request → 401."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/wizard/company/1/ebitda-adjustments")
    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


def test_wizard_ebitda_endpoint_does_not_require_admin():
    """The route must NOT use Depends(require_admin). Static check."""
    import inspect
    from main import wizard_get_ebitda_adjustments
    sig = inspect.signature(wizard_get_ebitda_adjustments)
    deps = []
    for p in sig.parameters.values():
        if p.default and hasattr(p.default, "dependency"):
            deps.append(getattr(p.default.dependency, "__name__", str(p.default.dependency)))
    assert "require_admin" not in deps, \
        f"wizard_get_ebitda_adjustments must NOT depend on require_admin. Found: {deps}"
    assert any("get_current_user" in d for d in deps), \
        f"wizard_get_ebitda_adjustments must depend on get_current_user. Found: {deps}"


@pytest.mark.asyncio
async def test_wizard_ebitda_endpoint_returns_regular_user_candidate_adjustments(client, fresh_all_db):
    """Regular wizard users receive their candidate earnings adjustments for review."""
    company_id = await _register_and_create_company(client, email="candidate-owner@example.com")
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        await db.executemany(
            """
            INSERT INTO ebitda_adjustments (company_id, label, amount, rationale)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    company_id,
                    "One-off relocation costs",
                    12_000,
                    "Non-recurring relocation setup cost.",
                ),
                (
                    company_id,
                    "Owner salary normalisation",
                    50_000,
                    "Above-market salary adjustment.",
                ),
            ],
        )
        await db.commit()

    response = await client.get(f"/wizard/company/{company_id}/ebitda-adjustments")

    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["label"] for row in rows] == [
        "One-off relocation costs",
        "Owner salary normalisation",
    ]
    assert rows[0]["amount"] == 12_000
    assert rows[0]["rationale"] == "Non-recurring relocation setup cost."
    assert rows[1]["amount"] == 50_000
    assert rows[1]["rationale"] == "Above-market salary adjustment."


@pytest.mark.asyncio
async def test_wizard_ebitda_endpoint_blocks_other_regular_users_candidate_adjustments(client, fresh_all_db):
    """Candidate adjustment pre-fill must not leak between regular customers."""
    company_id = await _register_and_create_company(client, email="candidate-owner-private@example.com")
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO ebitda_adjustments (company_id, label, amount, rationale)
            VALUES (?, 'Owner-only adjustment', 999999, 'Private adjustment rationale')
            """,
            (company_id,),
        )
        await db.commit()

    await client.post(
        "/auth/register",
        data={"email": "candidate-other-user@example.com", "password": "password123"},
    )
    response = await client.get(f"/wizard/company/{company_id}/ebitda-adjustments")

    assert response.status_code == 403
    assert "Owner-only adjustment" not in response.text
    assert "Private adjustment rationale" not in response.text


async def _register_and_create_company(client, email: str = "valuation-intake@example.com") -> int:
    response = await client.post(
        "/auth/register",
        data={"email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE email=?", (email,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES (?, 'Private', ?)",
            ("Short Intake Limited", user_id),
        ) as cur:
            company_id = cur.lastrowid
        await db.commit()
    return company_id


async def _seed_source_document(
    company_id: int,
    *,
    email: str = "valuation-intake@example.com",
    status: str = "done",
    label: str | None = None,
) -> int:
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE email=?", (email,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            """
            INSERT INTO documents
                (company_id, filename, filepath, extraction_status, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                company_id,
                f"{label or status}-financials.pdf",
                f"/tmp/{email}-{label or status}-financials.pdf",
                status,
                user_id,
            ),
        ) as cur:
            document_id = cur.lastrowid
        await db.commit()
    return document_id


async def _seed_financial_rows(
    company_id: int,
    document_id: int,
    rows: list[tuple[str, str, str, str, float]],
) -> None:
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        for statement, row_key, row_label, period, value in rows:
            await db.execute(
                """
                INSERT INTO financial_rows
                    (document_id, company_id, statement, row_key, row_label, period, value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (document_id, company_id, statement, row_key, row_label, period, value),
            )
        await db.commit()


@pytest.mark.asyncio
async def test_wizard_upload_accepts_multiple_financial_files(client, fresh_all_db, monkeypatch):
    async def fake_run_ingestion(document_id, *_args, **_kwargs):
        async with aiosqlite.connect(main_module.DB_PATH) as db:
            await db.execute(
                "UPDATE documents SET extraction_status='done' WHERE id=?",
                (document_id,),
            )
            await db.commit()

    monkeypatch.setattr(main_module, "_run_ingestion", fake_run_ingestion)
    await client.post(
        "/auth/register",
        data={"email": "multi-upload@example.com", "password": "password123"},
    )

    response = await client.post(
        "/wizard/upload",
        data={"business_name": "Multi Upload Ltd"},
        files=[
            ("files", ("p-and-l-2026.pdf", b"%PDF-1.4\n% test", "application/pdf")),
            ("files", ("balance-sheet-2026.pdf", b"%PDF-1.4\n% test", "application/pdf")),
        ],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["document_ids"]) == 2
    assert body["document_id"] == body["document_ids"][-1]
    assert body["filenames"] == ["p-and-l-2026.pdf", "balance-sheet-2026.pdf"]

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT filename FROM documents ORDER BY id"
        ) as cur:
            filenames = [row[0] for row in await cur.fetchall()]
    assert filenames == ["p-and-l-2026.pdf", "balance-sheet-2026.pdf"]


@pytest.mark.asyncio
async def test_report_generation_accepts_multiple_source_document_ids(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client, email="multi-report@example.com")
    first_document_id = await _seed_source_document(
        company_id,
        email="multi-report@example.com",
        label="pnl-2026",
    )
    second_document_id = await _seed_source_document(
        company_id,
        email="multi-report@example.com",
        label="bs-2026",
    )
    captured: dict[str, object] = {}

    async def fake_generate_report(
        queued_report_id,
        queued_company_id,
        queued_user_id,
        queued_report_type,
        queued_intake_answers,
        queued_source_document_id=None,
    ):
        captured.update(
            {
                "report_id": queued_report_id,
                "company_id": queued_company_id,
                "user_id": queued_user_id,
                "report_type": queued_report_type,
                "source_document_id": queued_source_document_id,
                "intake_answers": queued_intake_answers,
            }
        )

    monkeypatch.setattr(main_module, "_generate_report", fake_generate_report)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setenv("ACCOUNTIQ_DEMO_MODE", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_ids": [first_document_id, second_document_id],
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 201, response.text
    assert captured["source_document_id"] == [first_document_id, second_document_id]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT source_document_id, source_document_ids FROM report_intake"
        ) as cur:
            source_document_id, source_document_ids_json = await cur.fetchone()
    assert source_document_id == second_document_id
    assert json.loads(source_document_ids_json) == [first_document_id, second_document_id]


@pytest.mark.asyncio
async def test_wizard_financial_review_flags_conflicting_duplicate_years_and_accepts_a_selection(
    client,
    fresh_all_db,
):
    email = "financial-review@example.com"
    company_id = await _register_and_create_company(client, email=email)
    draft_document_id = await _seed_source_document(
        company_id,
        email=email,
        label="draft-fy25",
    )
    final_document_id = await _seed_source_document(
        company_id,
        email=email,
        label="final-fy25",
    )
    await _seed_financial_rows(
        company_id,
        draft_document_id,
        [("pnl", "revenue", "Revenue", "FY25", 1_250_000)],
    )
    await _seed_financial_rows(
        company_id,
        final_document_id,
        [("pnl", "revenue", "Revenue", "31 March 2025", 1_100_000)],
    )

    review = await client.post(
        "/wizard/financial-review",
        json={
            "company_id": company_id,
            "source_document_ids": [draft_document_id, final_document_id],
        },
    )

    assert review.status_code == 200, review.text
    body = review.json()
    assert body["status"] == "needs_review"
    assert body["unresolved_conflict_ids"] == ["pnl:revenue:FY2025"]
    assert body["conflicts"][0]["sources"] == [
        {
            "document_id": draft_document_id,
            "filename": "draft-fy25-financials.pdf",
            "value": 1_250_000,
            "currency": "NZD",
            "confidence": None,
        },
        {
            "document_id": final_document_id,
            "filename": "final-fy25-financials.pdf",
            "value": 1_100_000,
            "currency": "NZD",
            "confidence": None,
        },
    ]

    resolved_review = await client.post(
        "/wizard/financial-review",
        json={
            "company_id": company_id,
            "source_document_ids": [draft_document_id, final_document_id],
            "financial_reconciliation_overrides": {
                "pnl:revenue:FY2025": final_document_id,
            },
        },
    )

    assert resolved_review.status_code == 200, resolved_review.text
    resolved = resolved_review.json()
    assert resolved["status"] == "ready"
    assert resolved["unresolved_conflict_ids"] == []
    assert resolved["rows"] == [
        {
            "document_id": final_document_id,
            "source_filename": "final-fy25-financials.pdf",
            "statement": "pnl",
            "row_key": "revenue",
            "row_label": "Revenue",
            "period": "FY2025",
            "value": 1_100_000,
            "currency": "NZD",
            "confidence": None,
        }
    ]


@pytest.mark.asyncio
async def test_report_generation_requires_resolution_of_conflicting_duplicate_years(
    client,
    fresh_all_db,
    monkeypatch,
):
    email = "financial-conflict-gate@example.com"
    company_id = await _register_and_create_company(client, email=email)
    first_document_id = await _seed_source_document(company_id, email=email, label="first")
    second_document_id = await _seed_source_document(company_id, email=email, label="second")
    await _seed_financial_rows(
        company_id,
        first_document_id,
        [("pnl", "revenue", "Revenue", "2025", 1_000_000), ("pnl", "ebitda", "EBITDA", "2025", 100_000)],
    )
    await _seed_financial_rows(
        company_id,
        second_document_id,
        [("pnl", "revenue", "Revenue", "FY2025", 900_000), ("pnl", "ebitda", "EBITDA", "FY2025", 100_000)],
    )
    monkeypatch.setenv("ACCOUNTIQ_DEMO_MODE", "true")
    monkeypatch.setattr(main_module, "E2E_MODE", False)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_ids": [first_document_id, second_document_id],
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 409
    assert "different values for the same financial year" in response.json()["detail"]


def _complete_valuation_intake() -> dict:
    return {
        "valuation_purpose": "understand_value",
        "owner_dependency": "shared",
        "customer_concentration": "10_to_25",
        "revenue_quality": "mixed",
        "revenue_outlook": "not_sure",
        "normalisations": [],
    }


async def _seed_failed_valuation_report(
    company_id: int,
    document_id: int,
    *,
    error_message: str = "temporary generation failure",
    intake_answers: dict | None = None,
) -> int:
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status, error_message)
            VALUES (?, ?, 'valuation_advisory', 'failed', ?)
            """,
            (company_id, user_id, error_message),
        ) as cur:
            report_id = cur.lastrowid
        await db.execute(
            """
            INSERT INTO report_intake (report_id, source_document_id, answers)
            VALUES (?, ?, ?)
            """,
            (report_id, document_id, json.dumps(intake_answers or _complete_valuation_intake())),
        )
        await db.commit()
    return report_id


@pytest.mark.asyncio
async def test_valuation_generate_rejects_missing_short_intake_answer(client, fresh_all_db):
    company_id = await _register_and_create_company(client)
    intake = _complete_valuation_intake()
    del intake["customer_concentration"]

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "five required valuation answers" in response.json()["detail"]
    assert "Largest customer" in response.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_generate_rejects_invalid_option(client, fresh_all_db):
    company_id = await _register_and_create_company(client)
    intake = _complete_valuation_intake()
    intake["owner_dependency"] = "made_up_value"

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "Owner or key-person dependency" in response.json()["detail"]


@pytest.mark.parametrize(
    ("field", "value", "expected_detail"),
    [
        (
            "debt_override",
            "not a number",
            "Interest-bearing debt at valuation date must be a number",
        ),
        (
            "surplus_assets",
            -1,
            "Surplus or non-operating assets must be zero or greater",
        ),
        (
            "custom_growth_rate",
            125,
            "supported revenue-growth view must be between -50 and 100",
        ),
    ],
)
@pytest.mark.asyncio
async def test_valuation_generate_uses_friendly_optional_override_errors(
    client,
    fresh_all_db,
    monkeypatch,
    field,
    value,
    expected_detail,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake[field] = value

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_generate_rejects_owner_supplied_technical_dcf_assumptions(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake.update(
        {
            "forecast_horizon": "7",
            "forecast_years_selected": "5",
            "terminal_growth_rate": "4.5",
            "terminal_growth_pct": "4.0",
            "terminal_growth_assumption": "3.5",
            "wacc": "12.0",
            "selected_wacc_case": "mid",
            "discount_rate_pct": "12.5",
            "valuation_discount_rate": "13.0",
            "cost_of_equity_pct": "14.0",
            "risk_free_rate": "4.2",
            "riskfree_rate_assumption": "4.0",
            "industry_beta": "1.2",
            "total_beta_assumption": "1.1",
            "equity_risk_premium": "6.0",
            "equity_risk_premium_pct": "6.2",
            "illiquidity_discount": "10.0",
            "revenue_growth_rate": "7.5",
        }
    )

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "derives technical valuation assumptions" in response.json()["detail"]
    assert "forecast horizon" in response.json()["detail"]
    assert "forecast period" in response.json()["detail"]
    assert "terminal growth rate" in response.json()["detail"]
    assert "WACC" in response.json()["detail"]
    assert "discount rate" in response.json()["detail"]
    assert "cost of equity" in response.json()["detail"]
    assert "risk-free rate" in response.json()["detail"]
    assert "industry beta" in response.json()["detail"]
    assert "equity risk premium" in response.json()["detail"]
    assert "illiquidity discount" in response.json()["detail"]
    assert "revenue growth rate" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_valuation_generate_rejects_legacy_scoring_questionnaire_fields(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake.update(
        {
            "rq_revenue_quality": "3",
            "rq_owner_dependency": "4",
        }
    )

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "five private valuation answers" in response.json()["detail"]
    assert "older detailed scoring fields are not used in this short valuation intake" in response.json()["detail"]
    assert "owner flow" not in response.json()["detail"]
    assert "rq_owner_dependency" in response.json()["detail"]
    assert "rq_revenue_quality" in response.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_generate_rejects_unsupported_long_questionnaire_fields(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake.update(
        {
            "legacy_free_text": "Please provide a longer risk questionnaire.",
            "market_risk_score": 4,
        }
    )

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "short valuation intake" in response.json()["detail"]
    assert "legacy_free_text" in response.json()["detail"]
    assert "market_risk_score" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_wizard_generate_rejects_report_types_not_enabled_for_self_serve(client, fresh_all_db):
    company_id = await _register_and_create_company(client)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "report_type": "financial_forecast",
            "intake_answers": {
                "forecast_horizon": "3 years",
                "revenue_growth_rate": 0.05,
            },
        },
    )

    assert response.status_code == 422
    assert "Only Valuation Advisory and Bank Credit Paper" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            report_count = (await cur.fetchone())[0]
    assert report_count == 0


@pytest.mark.asyncio
async def test_bank_credit_generate_accepts_focused_credit_intake(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "bank_credit_paper",
            "intake_answers": {
                "loan_purpose": "Refinance existing debt and fund fleet expansion",
                "amount_requested": 250_000,
                "proposed_term_years": 5,
                "conservative_funding_cost_pct": 8.5,
                "lvr_percent": 60,
                "security_package": "fleet_and_property",
                "security_value": 450_000,
                "repayment_profile": "principal_and_interest",
                "company_website": "https://example.co.nz",
                "company_location": "Auckland",
                "covenant_package_level": "more_control",
                "selected_covenants": [
                    "min_dscr",
                    "max_senior_leverage",
                    "information_reporting",
                    "collateral_reporting",
                ],
                "covenant_package_notes": "Use a tighter package until collateral values are confirmed.",
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["demo_mode"] is True


@pytest.mark.asyncio
async def test_bank_credit_generate_rejects_unknown_covenant_choice(
    client,
    fresh_all_db,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "bank_credit_paper",
            "intake_answers": {
                "loan_purpose": "Refinance existing debt and fund fleet expansion",
                "amount_requested": 250_000,
                "proposed_term_years": 5,
                "conservative_funding_cost_pct": 8.5,
                "lvr_percent": 60,
                "security_package": "fleet_and_property",
                "repayment_profile": "principal_and_interest",
                "covenant_package_level": "balanced",
                "selected_covenants": ["min_dscr", "invented_covenant"],
            },
        },
    )

    assert response.status_code == 422
    assert "Unknown covenant selection" in response.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_generate_accepts_exact_five_answers_and_not_sure(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_valuation_generate_accepts_collapsed_expert_growth_override(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["custom_growth_rate"] = "6.5"

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_valuation_generate_normalises_optional_public_source_hints(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake.update(
        {
            "company_website": "source-hints.example",
            "company_location": "  Auckland,   New Zealand  ",
            "private_context": "  A key contract\n\nrenews next year.  ",
            "public_source_urls": (
                "companies-register.companiesoffice.govt.nz/source-hints\n"
                "https://www.linkedin.com/company/source-hints\n"
                "https://www.linkedin.com/company/source-hints"
            ),
        }
    )

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 201, response.text
    report_id = response.json()["report_id"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT answers, source_document_id FROM report_intake WHERE report_id=?",
            (report_id,),
        ) as cur:
            intake_row = await cur.fetchone()
            stored = json.loads(intake_row[0])
            stored_source_document_id = intake_row[1]
    assert stored["company_website"] == "https://source-hints.example"
    assert stored["company_location"] == "Auckland, New Zealand"
    assert stored["private_context"] == "A key contract renews next year."
    assert stored["public_source_urls"] == [
        "https://companies-register.companiesoffice.govt.nz/source-hints",
        "https://www.linkedin.com/company/source-hints",
    ]
    assert stored_source_document_id == document_id


@pytest.mark.asyncio
async def test_valuation_generate_normalises_earnings_review_adjustments(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["normalisations"] = [
        {
            "label": "  Owner salary\nabove market  ",
            "amount": "35000",
            "rationale": "  Above market\nsalary adjustment.  ",
            "ignored": "not stored",
        }
    ]

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 201, response.text
    report_id = response.json()["report_id"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT answers FROM report_intake WHERE report_id=?",
            (report_id,),
        ) as cur:
            stored = json.loads((await cur.fetchone())[0])
    assert stored["normalisations"] == [
        {
            "label": "Owner salary above market",
            "amount": 35000.0,
            "rationale": "Above market salary adjustment.",
        }
    ]


@pytest.mark.asyncio
async def test_valuation_generate_ignores_blank_earnings_review_adjustment_rows(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["normalisations"] = [
        {"label": "  ", "amount": "", "rationale": "\n\n"},
        {
            "label": "One-off legal costs",
            "amount": "12000",
            "rationale": "Non-recurring legal cost.",
        },
        {"label": "", "amount": None, "rationale": ""},
    ]

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 201, response.text
    report_id = response.json()["report_id"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT answers FROM report_intake WHERE report_id=?",
            (report_id,),
        ) as cur:
            stored = json.loads((await cur.fetchone())[0])
    assert stored["normalisations"] == [
        {
            "label": "One-off legal costs",
            "amount": 12000.0,
            "rationale": "Non-recurring legal cost.",
        }
    ]


@pytest.mark.asyncio
async def test_valuation_generate_rejects_incomplete_earnings_review_adjustments(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    intake = _complete_valuation_intake()
    intake["normalisations"] = [
        {
            "label": "Owner salary above market",
            "amount": "35000",
            "rationale": "",
        }
    ]
    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "Adjustment 1 rationale is required" in response.json()["detail"]

    intake = _complete_valuation_intake()
    intake["normalisations"] = [
        {
            "label": "Owner salary above market",
            "amount": "0",
            "rationale": "Owner salary normalisation.",
        }
    ]
    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "Adjustment 1 needs a non-zero amount" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.parametrize(
    ("normalisations", "expected_detail"),
    [
        ("not a list", "Earnings adjustments must be sent as a list"),
        ([{"label": "x", "amount": 1, "rationale": "x"}] * 51, "earnings review can include up to 50 adjustments"),
        (["not an object"], "Adjustment 1 must include a label, amount and rationale"),
    ],
)
@pytest.mark.asyncio
async def test_valuation_generate_uses_friendly_earnings_review_payload_errors(
    client,
    fresh_all_db,
    monkeypatch,
    normalisations,
    expected_detail,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["normalisations"] = normalisations

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]


def test_replacement_manager_cost_becomes_visible_earnings_deduction():
    normalisations = main_module._valuation_earnings_review_normalisations(
        {
            "normalisations": [
                {
                    "label": "Owner salary above market",
                    "amount": 35_000,
                    "rationale": "Above market salary adjustment.",
                }
            ],
            "replacement_manager_cost": 75_000,
        },
        [
            {
                "label": "Legacy adjustment",
                "amount": 999_999,
                "rationale": "Should not be used when wizard review is present.",
            }
        ],
    )

    assert normalisations == [
        {
            "label": "Owner salary above market",
            "amount": 35_000,
            "rationale": "Above market salary adjustment.",
        },
        {
            "label": "Replacement manager cost",
            "amount": -75_000,
            "rationale": (
                "Management-supplied replacement manager cost deducted to reflect "
                "maintainable earnings after replacing owner involvement."
            ),
        },
    ]
    assert sum(row["amount"] for row in normalisations) == -40_000


@pytest.mark.asyncio
async def test_valuation_generate_rejects_invalid_public_source_hint(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["public_source_urls"] = "not a valid url"

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "public source URL" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "expected_label"),
    [
        ("company_website", "localhost:3000", "company website"),
        ("public_source_urls", "http://127.0.0.1/internal-source", "public source URL 1"),
        ("public_source_urls", "http://192.168.1.10/internal-source", "public source URL 1"),
    ],
)
async def test_valuation_generate_rejects_non_public_source_hints(
    client,
    fresh_all_db,
    monkeypatch,
    field,
    value,
    expected_label,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake[field] = value

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert expected_label in response.json()["detail"]
    assert "public http or https URL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_generate_rejects_too_many_public_source_hints(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["public_source_urls"] = [
        f"https://source-{index}.example.nz"
        for index in range(11)
    ]

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "public source URLs cannot contain more than 10 links" in response.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_generate_rejects_too_long_normalisation_text(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["normalisations"] = [
        {
            "label": "A" * 121,
            "amount": 10_000,
            "rationale": "One-off cost.",
        }
    ]

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "Adjustment 1 label is too long" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_valuation_generate_rejects_invalid_normalisation_text_characters(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["normalisations"] = [
        {
            "label": "One-off cost",
            "amount": 10_000,
            "rationale": "Contains a null byte\x00",
        }
    ]

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "Adjustment 1 rationale contains invalid characters" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_valuation_generate_rejects_too_long_company_location(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["company_location"] = "Auckland " * 30

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "company location is too long" in response.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_generate_rejects_too_long_private_context(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["private_context"] = "A" * 1201

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "private context is too long" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_valuation_generate_rejects_invalid_private_context_characters(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)
    intake = _complete_valuation_intake()
    intake["private_context"] = "Pipeline looks good.\x00"

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": intake,
        },
    )

    assert response.status_code == 422
    assert "private context contains invalid characters" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_report_generation_fails_before_queue_when_ai_connection_missing(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_report_generation_treats_placeholder_ai_key_as_missing(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-YOUR_KEY_HERE")

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_live_valuation_rejects_done_upload_without_core_financial_rows(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-live-looking-test-key")

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 422
    assert "key valuation figures" in response.json()["detail"]
    assert "revenue and EBITDA or profit" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_live_valuation_readiness_uses_selected_upload_not_stale_company_rows(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    stale_document_id = await _seed_source_document(company_id, label="stale")
    selected_document_id = await _seed_source_document(company_id, label="selected")
    await _seed_financial_rows(
        company_id,
        stale_document_id,
        [
            ("pnl", "revenue", "Revenue", "2025", 1_000_000),
            ("pnl", "net_profit", "Net profit", "2025", 120_000),
        ],
    )
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-live-looking-test-key")

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": selected_document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 422
    assert "key valuation figures" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_live_valuation_preflights_research_connection_before_queueing(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, label="preflight-fail")
    await _seed_financial_rows(
        company_id,
        document_id,
        [
            ("pnl", "revenue", "Revenue", "2025", 1_000_000),
            ("pnl", "ebitda", "EBITDA", "2025", 180_000),
        ],
    )
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-live-preflight-fail")
    main_module._live_research_preflight_cache.clear()

    def fail_preflight(_api_key, _model):
        raise RuntimeError("invalid provider setup")

    monkeypatch.setattr(
        main_module,
        "_anthropic_live_research_preflight_sync",
        fail_preflight,
    )

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_live_valuation_queues_after_research_preflight_passes(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, label="preflight-pass")
    await _seed_financial_rows(
        company_id,
        document_id,
        [
            ("pnl", "revenue", "Revenue", "2025", 1_000_000),
            ("pnl", "ebitda", "EBITDA", "2025", 180_000),
        ],
    )
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-live-preflight-pass")
    main_module._live_research_preflight_cache.clear()

    preflight_calls: list[tuple[str, str]] = []

    def pass_preflight(api_key, model):
        preflight_calls.append((api_key, model))

    captured: dict[str, object] = {}

    async def fake_generate_report(
        queued_report_id,
        queued_company_id,
        queued_user_id,
        queued_report_type,
        queued_intake_answers,
        queued_source_document_id=None,
    ):
        captured.update(
            {
                "report_id": queued_report_id,
                "company_id": queued_company_id,
                "report_type": queued_report_type,
                "source_document_id": queued_source_document_id,
                "intake_answers": queued_intake_answers,
            }
        )

    monkeypatch.setattr(
        main_module,
        "_anthropic_live_research_preflight_sync",
        pass_preflight,
    )
    monkeypatch.setattr(main_module, "_generate_report", fake_generate_report)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"
    assert preflight_calls == [
        ("sk-ant-live-preflight-pass", "claude-sonnet-4-6")
    ]
    assert captured["company_id"] == company_id
    assert captured["report_type"] == "valuation_advisory"
    assert captured["source_document_id"] == document_id
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_report_generation_can_continue_in_explicit_demo_mode_without_ai_key(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setenv("ACCOUNTIQ_DEMO_MODE", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"
    assert response.json()["demo_mode"] is True
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 1
        async with db.execute("SELECT demo_mode FROM reports") as cur:
            assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_background_report_generation_uses_stored_demo_mode(
    client,
    fresh_all_db,
    monkeypatch,
):
    email = "stored-demo-generation@example.com"
    company_id = await _register_and_create_company(client, email=email)
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status, demo_mode)
            VALUES (?, ?, 'valuation_advisory', 'queued', 1)
            """,
            (company_id, user_id),
        ) as cur:
            report_id = cur.lastrowid
        await db.commit()

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    await main_module._generate_report(
        report_id,
        company_id,
        user_id,
        "valuation_advisory",
        _complete_valuation_intake(),
        None,
    )

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, content, demo_mode FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, content, demo_mode = await cur.fetchone()

    assert status == "done"
    assert demo_mode == 1
    assert "Demo figures and simulated research" in content


@pytest.mark.asyncio
async def test_report_status_returns_persisted_demo_mode_independent_of_current_environment(
    client,
    fresh_all_db,
    monkeypatch,
):
    email = "stored-demo-status@example.com"
    company_id = await _register_and_create_company(client, email=email)
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status, content, completed_at, demo_mode)
            VALUES (?, ?, 'valuation_advisory', 'done', ?, datetime('now'), 1)
            """,
            (
                company_id,
                user_id,
                json.dumps({"executive_summary": {"narrative": "Demo figures and simulated research."}}),
            ),
        ) as cur:
            demo_report_id = cur.lastrowid
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status, content, completed_at, demo_mode)
            VALUES (?, ?, 'valuation_advisory', 'done', ?, datetime('now'), 0)
            """,
            (
                company_id,
                user_id,
                json.dumps({"executive_summary": {"narrative": "Live valuation report content."}}),
            ),
        ) as cur:
            live_report_id = cur.lastrowid
        await db.commit()

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    demo_status = await client.get(f"/wizard/report/{demo_report_id}/status")

    assert demo_status.status_code == 200, demo_status.text
    assert demo_status.json()["demo_mode"] is True
    assert "content" not in demo_status.json()

    monkeypatch.setattr(main_module, "E2E_MODE", True)
    monkeypatch.setenv("ACCOUNTIQ_DEMO_MODE", "true")
    live_status = await client.get(f"/wizard/report/{live_report_id}/status")

    assert live_status.status_code == 200, live_status.text
    assert live_status.json()["demo_mode"] is False
    assert "content" not in live_status.json()


@pytest.mark.asyncio
async def test_wizard_document_status_is_available_to_owning_regular_user(client, fresh_all_db):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, status="processing")

    response = await client.get(f"/wizard/document/{document_id}/status")

    assert response.status_code == 200, response.text
    assert response.json()["extraction_status"] == "processing"
    assert "reading the financial statements" in response.json()["message"].lower()
    assert isinstance(response.json()["demo_mode"], bool)


@pytest.mark.asyncio
async def test_report_generation_waits_for_financial_extraction(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, status="processing")
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    response = await client.post(
        "/wizard/report/generate",
        json={
            "company_id": company_id,
            "source_document_id": document_id,
            "report_type": "valuation_advisory",
            "intake_answers": _complete_valuation_intake(),
        },
    )

    assert response.status_code == 409
    assert "still being processed" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reports") as cur:
            assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_report_retry_fails_before_requeue_when_ai_connection_missing(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, label="retry-no-key")
    report_id = await _seed_failed_valuation_report(company_id, document_id)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = await client.post(f"/wizard/report/{report_id}/retry")

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, error_message FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, error_message = await cur.fetchone()
    assert status == "failed"
    assert error_message == "temporary generation failure"


@pytest.mark.asyncio
async def test_report_retry_waits_for_selected_upload_extraction(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, status="processing", label="retry-processing")
    report_id = await _seed_failed_valuation_report(company_id, document_id)
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    response = await client.post(f"/wizard/report/{report_id}/retry")

    assert response.status_code == 409
    assert "still being processed" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, error_message FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, error_message = await cur.fetchone()
    assert status == "failed"
    assert error_message == "temporary generation failure"


@pytest.mark.asyncio
async def test_live_valuation_retry_rejects_done_upload_without_core_financial_rows(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, label="retry-thin")
    report_id = await _seed_failed_valuation_report(company_id, document_id)
    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-live-looking-test-key")

    response = await client.post(f"/wizard/report/{report_id}/retry")

    assert response.status_code == 422
    assert "key valuation figures" in response.json()["detail"]
    assert "revenue and EBITDA or profit" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, error_message FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, error_message = await cur.fetchone()
    assert status == "failed"
    assert error_message == "temporary generation failure"


@pytest.mark.asyncio
async def test_report_retry_reuses_original_selected_upload_context(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, label="retry-source")

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status, error_message)
            VALUES (?, ?, 'valuation_advisory', 'failed', 'temporary generation failure')
            """,
            (company_id, user_id),
        ) as cur:
            report_id = cur.lastrowid
        await db.execute(
            """
            INSERT INTO report_intake (report_id, source_document_id, answers)
            VALUES (?, ?, ?)
            """,
            (report_id, document_id, json.dumps(_complete_valuation_intake())),
        )
        await db.commit()

    captured: dict[str, object] = {}

    async def fake_generate_report(
        queued_report_id,
        queued_company_id,
        queued_user_id,
        queued_report_type,
        queued_intake_answers,
        queued_source_document_id=None,
    ):
        captured.update(
            {
                "report_id": queued_report_id,
                "company_id": queued_company_id,
                "user_id": queued_user_id,
                "report_type": queued_report_type,
                "intake_answers": queued_intake_answers,
                "source_document_id": queued_source_document_id,
            }
        )

    monkeypatch.setattr(main_module, "_generate_report", fake_generate_report)
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    response = await client.post(f"/wizard/report/{report_id}/retry")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
    assert captured["report_id"] == report_id
    assert captured["company_id"] == company_id
    assert captured["user_id"] == user_id
    assert captured["report_type"] == "valuation_advisory"
    assert captured["intake_answers"]["valuation_purpose"] == "understand_value"
    assert captured["source_document_id"] == document_id
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, error_message, completed_at FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, error_message, completed_at = await cur.fetchone()
    assert status == "queued"
    assert error_message is None
    assert completed_at is None


@pytest.mark.asyncio
async def test_report_retry_revalidates_stored_short_valuation_intake(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, label="retry-legacy-intake")
    intake = _complete_valuation_intake()
    intake.update(
        {
            "rq_owner_dependency": "4",
            "terminal_growth_rate": "3.5",
            "discount_rate_pct": "12.0",
            "risk_free_rate": "4.2",
            "legacy_free_text": "Please complete a longer valuation questionnaire.",
        }
    )
    report_id = await _seed_failed_valuation_report(
        company_id,
        document_id,
        intake_answers=intake,
    )
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    response = await client.post(f"/wizard/report/{report_id}/retry")

    assert response.status_code == 422
    assert "older detailed scoring fields are not used in this short valuation intake" in response.json()["detail"]
    assert "owner flow" not in response.json()["detail"]
    assert "rq_owner_dependency" in response.json()["detail"]
    assert "discount rate" not in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, error_message FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, error_message = await cur.fetchone()
    assert status == "failed"
    assert error_message == "temporary generation failure"


@pytest.mark.asyncio
async def test_report_retry_rejects_stored_owner_supplied_technical_assumptions(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    document_id = await _seed_source_document(company_id, label="retry-technical-assumptions")
    intake = _complete_valuation_intake()
    intake.update(
        {
            "discount_rate_pct": "12.0",
            "valuation_discount_rate": "13.0",
            "terminal_growth_pct": "3.0",
            "selected_wacc_case": "mid",
            "risk_free_rate": "4.2",
            "riskfree_rate_assumption": "4.0",
            "industry_beta": "1.2",
            "total_beta_assumption": "1.1",
        }
    )
    report_id = await _seed_failed_valuation_report(
        company_id,
        document_id,
        intake_answers=intake,
    )
    monkeypatch.setattr(main_module, "E2E_MODE", True)

    response = await client.post(f"/wizard/report/{report_id}/retry")

    assert response.status_code == 422
    assert "derives technical valuation assumptions" in response.json()["detail"]
    assert "discount rate" in response.json()["detail"]
    assert "terminal growth" in response.json()["detail"]
    assert "WACC" in response.json()["detail"]
    assert "risk-free rate" in response.json()["detail"]
    assert "industry beta" in response.json()["detail"]
    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, error_message FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, error_message = await cur.fetchone()
    assert status == "failed"
    assert error_message == "temporary generation failure"


@pytest.mark.asyncio
async def test_background_report_generation_uses_selected_upload_financial_rows(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(client)
    stale_document_id = await _seed_source_document(company_id, label="stale")
    selected_document_id = await _seed_source_document(company_id, label="selected")
    await _seed_financial_rows(
        company_id,
        stale_document_id,
        [
            ("pnl", "revenue", "Revenue", "2025", 9_999_999),
            ("pnl", "ebitda", "EBITDA", "2025", 8_888_888),
            ("pnl", "net_profit", "Net profit", "2025", 7_777_777),
        ],
    )
    await _seed_financial_rows(
        company_id,
        selected_document_id,
        [
            ("pnl", "revenue", "Revenue", "2024", 110_000),
            ("pnl", "revenue", "Revenue", "2025", 123_456),
            ("pnl", "ebitda", "EBITDA", "2025", 32_000),
            ("pnl", "net_profit", "Net profit", "2025", 21_000),
            ("pnl", "depreciation_amortisation", "Depreciation", "2025", 4_000),
            ("bs", "cash_and_bank", "Cash and bank", "2025", 12_000),
            ("bs", "trade_debtors", "Trade debtors", "2025", 18_000),
            ("bs", "inventory", "Inventory", "2025", 6_000),
            ("bs", "trade_creditors", "Trade creditors", "2025", 9_000),
            ("bs", "short_term_debt", "Short-term debt", "2025", 5_000),
            ("bs", "long_term_debt", "Long-term debt", "2025", 10_000),
        ],
    )

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)) as cur:
            user_id = (await cur.fetchone())[0]
        await db.execute(
            """
            INSERT INTO ebitda_adjustments (company_id, label, amount, rationale)
            VALUES (?, 'Stale owner salary adjustment', 999999, 'Old company-level adjustment')
            """,
            (company_id,),
        )
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status)
            VALUES (?, ?, 'valuation_advisory', 'queued')
            """,
            (company_id, user_id),
        ) as cur:
            report_id = cur.lastrowid
        await db.commit()

    class FakeBrief(SimpleNamespace):
        def model_dump(self):
            return {
                "company_summary": "Selected upload scoped research summary.",
                "sector_summary": "Selected upload scoped sector summary.",
                "industry_category": "Business services",
                "risk_free_rate": self.risk_free_rate,
                "industry_beta": self.industry_beta,
                "erp": self.erp,
                "inflation_rate": self.inflation_rate,
                "ev_ebitda_low": self.ev_ebitda_low,
                "ev_ebitda_high": self.ev_ebitda_high,
                "comparable_transactions": [],
                "sources": ["https://www.rbnz.govt.nz/statistics"],
            }

    async def fake_research(**kwargs):
        captured["research_kwargs"] = kwargs
        return FakeBrief(
            risk_free_rate=4.0,
            industry_beta=1.0,
            erp=5.0,
            inflation_rate=2.5,
            ev_ebitda_low=3.5,
            ev_ebitda_high=5.0,
        )

    captured: dict[str, object] = {}

    def fake_build_prompt(**kwargs):
        captured["financial_rows"] = kwargs["financial_rows"]
        captured["valuation_result"] = kwargs["valuation_result"]
        return "system", "user"

    async def fake_call_claude(*_args, **_kwargs):
        return main_module._e2e_report_content("valuation_advisory")

    async def fake_send_report_ready_email(*_args, **_kwargs):
        return None

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setattr(main_module, "run_valuation_research", fake_research)
    monkeypatch.setattr(main_module, "build_prompt", fake_build_prompt)
    monkeypatch.setattr(main_module, "_call_claude_for_report", fake_call_claude)
    monkeypatch.setattr(main_module, "_validate_generated_report_content", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_validate_valuation_report_figures", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "send_report_ready_email", fake_send_report_ready_email)

    intake = _complete_valuation_intake()
    intake.update(
        {
            "company_website": "https://selected.example.co.nz",
            "public_source_urls": [
                "https://www.linkedin.com/company/selected-example",
                "https://www.rbnz.govt.nz/statistics",
            ],
            "debt_override": "15000",
            "revenue_growth_cagr": "99",
        }
    )

    await main_module._generate_report(
        report_id,
        company_id,
        user_id,
        "valuation_advisory",
        intake,
        selected_document_id,
    )

    grouped_rows = json.dumps(captured["financial_rows"])
    assert "123456" in grouped_rows
    assert "9999999" not in grouped_rows
    assert "8888888" not in grouped_rows
    assert captured["valuation_result"]["normalised_ebitda"] == 32_000
    assert captured["valuation_result"]["revenue_growth_pct"] == 12.0
    assert captured["valuation_result"]["growth_assumption_source"] == "historical_revenue_cagr_capped"
    assert captured["valuation_result"]["normalisation_schedule"]["rows"][0][0] == "No adjustments confirmed"
    assert captured["valuation_result"]["normalisation_schedule"]["rows"][1][1] == "$32,000"
    executive_rows = captured["valuation_result"]["executive_summary_table"]["rows"]
    wacc_rows = captured["valuation_result"]["wacc_assumptions_table"]["rows"]
    dcf_rows = captured["valuation_result"]["dcf_analysis_table"]["rows"]
    performance_rows = captured["valuation_result"]["financial_performance_table"]["rows"]
    ratio_rows = captured["valuation_result"]["financial_ratio_table"]["rows"]
    balance_rows = captured["valuation_result"]["balance_sheet_summary_table"]["rows"]
    valuation_rows = captured["valuation_result"]["valuation_summary_table"]["rows"]
    multiples_rows = captured["valuation_result"]["multiples_crosscheck_table"]["rows"]
    comparable_rows = captured["valuation_result"]["comparable_evidence_table"]["rows"]
    source_rows = captured["valuation_result"]["sources_table"]["rows"]
    sensitivity_rows = captured["valuation_result"]["sensitivity_table"]["rows"]
    assert any(row[0] == "Less: net debt" and "($3,000)" in row for row in executive_rows)
    assert any(row[0] == "Private-company WACC" and "8.0%" in row and "10.0%" in row for row in wacc_rows)
    assert any(row[0] == "Base revenue" and "$123,456" in row for row in dcf_rows)
    assert any(row[0] == "Normalised EBITDA" and "$32,000" in row for row in dcf_rows)
    assert any(row[0] == "Revenue" and "$123,456" in row for row in performance_rows)
    assert any(row[0] == "EBITDA" and "$32,000" in row for row in performance_rows)
    assert all("9999999" not in json.dumps(row) for row in performance_rows)
    assert any(row[0] == "EBITDA margin" and "25.9%" in row for row in ratio_rows)
    assert any(row[0] == "Operating working capital" and "$15,000" in row for row in balance_rows)
    assert any(row[0] == "Cash and bank" and "$12,000" in row for row in balance_rows)
    assert any(row[0] == "Interest-bearing debt" and "$15,000" in row for row in balance_rows)
    assert any(
        row[0] == "Interest-bearing debt"
        and "$15,000" in row
        and "Management-supplied debt override." in row
        for row in balance_rows
    )
    assert any(row[0] == "Net debt" and "$3,000" in row for row in balance_rows)
    assumption_source_rows = captured["valuation_result"]["assumption_source_trail"]["rows"]
    assumption_source_text = json.dumps(assumption_source_rows)
    assert "Debt: management-supplied debt override" in assumption_source_text
    assert "Debt: uploaded balance sheet borrowings where extracted" not in assumption_source_text
    assert "debt_override" not in assumption_source_text
    assert any(
        row[0] == "Multiples - low" and "$112,000" in row and "$109,000" in row
        for row in valuation_rows
    )
    assert any(row[0] == "Normalised EBITDA" and "$32,000" in row for row in multiples_rows)
    assert any(row[0] == "Indicated enterprise value" and "$112,000" in row for row in multiples_rows)
    assert any("https://www.rbnz.govt.nz/statistics" in json.dumps(row) for row in comparable_rows)
    assert any("https://www.rbnz.govt.nz/statistics" in json.dumps(row) for row in source_rows)
    assert any("https://selected.example.co.nz" in json.dumps(row) for row in source_rows)
    assert any("https://www.linkedin.com/company/selected-example" in json.dumps(row) for row in source_rows)
    assert any(
        "Management-supplied public source hint retained" in json.dumps(row)
        for row in source_rows
    )
    assert captured["research_kwargs"]["company_website"] == "https://selected.example.co.nz"
    assert captured["research_kwargs"]["public_source_urls"] == [
        "https://www.linkedin.com/company/selected-example",
        "https://www.rbnz.govt.nz/statistics",
    ]
    assert any(row[0] == "12.0% - base" for row in sensitivity_rows)


@pytest.mark.asyncio
async def test_background_valuation_failure_stores_customer_safe_message(
    client,
    fresh_all_db,
    monkeypatch,
):
    company_id = await _register_and_create_company(
        client,
        email="valuation-safe-error@example.com",
    )
    document_id = await _seed_source_document(
        company_id,
        email="valuation-safe-error@example.com",
        label="safe-error",
    )
    await _seed_financial_rows(
        company_id,
        document_id,
        [
            ("pnl", "revenue", "Revenue", "2025", 250_000),
            ("pnl", "ebitda", "EBITDA", "2025", 45_000),
            ("pnl", "net_profit", "Net profit", "2025", 32_000),
        ],
    )

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM companies WHERE id=?", (company_id,)) as cur:
            user_id = (await cur.fetchone())[0]
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status)
            VALUES (?, ?, 'valuation_advisory', 'queued')
            """,
            (company_id, user_id),
        ) as cur:
            report_id = cur.lastrowid
        await db.commit()

    async def fake_research(**_kwargs):
        raise RuntimeError(
            "Anthropic invalid_request_error: Claude returned an invalid JSON object "
            "after reading the system prompt for sk-ant-secret"
        )

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.delenv("ACCOUNTIQ_DEMO_MODE", raising=False)
    monkeypatch.setattr(main_module, "run_valuation_research", fake_research)

    await main_module._generate_report(
        report_id,
        company_id,
        user_id,
        "valuation_advisory",
        _complete_valuation_intake(),
        document_id,
    )

    async with aiosqlite.connect(main_module.DB_PATH) as db:
        async with db.execute(
            "SELECT status, error_message FROM reports WHERE id=?",
            (report_id,),
        ) as cur:
            status, error_message = await cur.fetchone()

    assert status == "failed"
    assert error_message == (
        "We could not complete the valuation report quality checks. Please retry. "
        "If this keeps happening, contact the AccountIQ administrator."
    )
    lowered = error_message.lower()
    for forbidden in (
        "anthropic",
        "claude",
        "json",
        "system prompt",
        "sk-ant",
        "invalid_request_error",
    ):
        assert forbidden not in lowered
