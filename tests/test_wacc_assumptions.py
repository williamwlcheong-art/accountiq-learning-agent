import asyncio

import aiosqlite
import pytest

from account_helpers import register_test_admin
from db import DB_PATH, init_db


VALID_SET = {
    "name": "NZ SME services",
    "risk_free_rate": 4.25,
    "equity_risk_premium": 5.5,
    "beta": 1.1,
    "beta_type": "industry_unlevered_relevered",
    "cost_of_debt": 6.75,
    "target_debt_weight": 30,
    "target_equity_weight": 70,
    "additional_premium": 2.0,
    "scenario_spread": 1.0,
    "source_references": "NZ Treasury curve; adviser research file WACC-2026-01",
    "publisher": "AccountIQ valuation team",
    "as_of_date": "2026-07-01",
    "rationale": "Approved private SME assumptions for the pilot.",
}


@pytest.mark.asyncio
async def test_wacc_schema_is_additive_and_idempotent(fresh_all_db):
    init_db()
    init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(wacc_assumption_sets)") as cur:
            columns = {row[1] for row in await cur.fetchall()}

    assert {
        "name", "version", "status", "active", "risk_free_rate",
        "equity_risk_premium", "beta", "beta_type", "cost_of_debt",
        "target_debt_weight", "target_equity_weight", "additional_premium",
        "scenario_spread", "source_references", "publisher", "as_of_date",
        "rationale", "approved_at", "approved_by_user_id",
    }.issubset(columns)


@pytest.mark.asyncio
async def test_admin_can_version_approve_and_activate_one_wacc_set(client, fresh_all_db):
    await register_test_admin(client, "wacc-admin@example.com")

    created = await client.post("/admin/wacc-assumption-sets", json=VALID_SET)
    assert created.status_code == 201, created.text
    first = created.json()
    assert first["version"] == 1
    assert first["status"] == "draft"
    assert first["active"] is False

    second_payload = {**VALID_SET, "risk_free_rate": 4.5}
    created = await client.post("/admin/wacc-assumption-sets", json=second_payload)
    assert created.status_code == 201, created.text
    second = created.json()
    assert second["version"] == 2

    approved = await client.post(f"/admin/wacc-assumption-sets/{second['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "wacc-admin@example.com"

    approved_again = await client.post(f"/admin/wacc-assumption-sets/{second['id']}/approve")
    assert approved_again.status_code == 409
    assert approved_again.json()["detail"] == "Only a draft WACC assumption set can be approved."

    activated = await client.post(f"/admin/wacc-assumption-sets/{second['id']}/activate")
    assert activated.status_code == 200, activated.text
    assert activated.json()["active"] is True

    cannot_activate_draft = await client.post(f"/admin/wacc-assumption-sets/{first['id']}/activate")
    assert cannot_activate_draft.status_code == 409

    listed = await client.get("/admin/wacc-assumption-sets")
    assert listed.status_code == 200
    assert [item["version"] for item in listed.json()] == [2, 1]
    assert sum(item["active"] for item in listed.json()) == 1


@pytest.mark.asyncio
async def test_customer_fcff_readiness_only_derives_safe_same_period_ratios(client, fresh_all_db):
    await client.post("/auth/register", data={"email": "fcff-owner@example.com", "password": "password123"})
    upload = await client.post(
        "/wizard/upload",
        data={"business_name": "FCFF Readiness Ltd"},
        files={"file": ("accounts.pdf", b"%PDF-1.4 fixture", "application/pdf")},
    )
    company_id = upload.json()["company_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        document = await db.execute("SELECT id FROM documents WHERE company_id=?", (company_id,))
        document_id = (await document.fetchone())[0]
        await db.execute("UPDATE documents SET extraction_status='done' WHERE id=?", (document_id,))
        await db.executemany(
            """
            INSERT INTO financial_rows
                (document_id, company_id, statement, row_key, row_label, period, value, currency, unit, source_text, confidence)
            VALUES (?, ?, ?, ?, ?, '2025', ?, 'NZD', 'whole', ?, 0.99)
            """,
            [
                (document_id, company_id, "pnl", "revenue", "Revenue", 1_250_000, "Revenue"),
                (document_id, company_id, "pnl", "ebitda", "EBITDA", 250_000, "EBITDA"),
                (document_id, company_id, "pnl", "depreciation", "D&A", -35_000, "D&A"),
                (document_id, company_id, "bs", "trade_debtors", "Trade debtors", 180_000, "Trade debtors"),
                (document_id, company_id, "bs", "inventory", "Inventory", 85_000, "Inventory"),
                (document_id, company_id, "bs", "trade_creditors", "Trade creditors", 110_000, "Trade creditors"),
            ],
        )
        await db.executemany(
            "INSERT INTO document_authority (company_id, statement, period, document_id) VALUES (?, ?, '2025', ?)",
            [(company_id, "pnl", document_id), (company_id, "bs", document_id)],
        )
        await db.commit()

    response = await client.get(f"/wizard/company/{company_id}/fcff-assumptions")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "ready"
    assert body["depreciation"]["status"] == "available"
    assert body["depreciation"]["rate"] == 0.028
    assert body["depreciation"]["provenance"] == "D&A"
    assert body["operating_nwc"]["status"] == "available"
    assert body["operating_nwc"]["rate"] == 0.124
    provenance = body["operating_nwc"]["provenance"]
    assert provenance["formula"] == "Trade debtors + Inventory - Trade creditors"
    assert [component["row_key"] for component in provenance["components"]] == [
        "trade_debtors", "inventory", "trade_creditors"
    ]
    assert [component["normalised_value"] for component in provenance["components"]] == [
        180_000, 85_000, 110_000
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE financial_rows SET unit='millions', value=value / 1000000 WHERE company_id=? AND row_key='revenue'",
            (company_id,),
        )
        await db.execute(
            "UPDATE financial_rows SET unit='thousands', value=value / 1000 WHERE company_id=? AND row_key IN ('depreciation', 'trade_debtors', 'trade_creditors')",
            (company_id,),
        )
        await db.commit()
    response = await client.get(f"/wizard/company/{company_id}/fcff-assumptions")
    body = response.json()
    assert body["depreciation"]["rate"] == 0.028
    assert body["operating_nwc"]["rate"] == 0.124
    assert body["operating_nwc"]["source_period"] == "2025"
    provenance = body["operating_nwc"]["provenance"]
    assert [component["original_unit"] for component in provenance["components"]] == [
        "thousands", "whole", "thousands"
    ]
    assert [component["normalised_value"] for component in provenance["components"]] == [
        180_000, 85_000, 110_000
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE financial_rows SET currency='AUD' WHERE company_id=? AND row_key='inventory'",
            (company_id,),
        )
        await db.commit()
    response = await client.get(f"/wizard/company/{company_id}/fcff-assumptions")
    body = response.json()
    assert body["state"] == "needs_adviser_assistance"
    assert body["depreciation"]["rate"] is None
    assert body["operating_nwc"]["rate"] is None

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE financial_rows SET currency='NZD' WHERE company_id=? AND row_key='inventory'",
            (company_id,),
        )
        await db.execute("DELETE FROM financial_rows WHERE company_id=? AND row_key='inventory'", (company_id,))
        await db.commit()
    response = await client.get(f"/wizard/company/{company_id}/fcff-assumptions")
    assert response.json()["state"] == "needs_adviser_assistance"
    assert response.json()["operating_nwc"]["status"] == "missing"
    assert response.json()["operating_nwc"]["rate"] is None


@pytest.mark.asyncio
async def test_wacc_update_and_approve_are_serialised_state_transitions(client, fresh_all_db):
    await register_test_admin(client, "wacc-race@example.com")
    created = await client.post("/admin/wacc-assumption-sets", json=VALID_SET)
    assumption_set_id = created.json()["id"]

    update_response, approve_response = await asyncio.gather(
        client.put(
            f"/admin/wacc-assumption-sets/{assumption_set_id}",
            json={**VALID_SET, "risk_free_rate": 4.75},
        ),
        client.post(f"/admin/wacc-assumption-sets/{assumption_set_id}/approve"),
    )

    assert sorted([update_response.status_code, approve_response.status_code]) in (
        [200, 200],
        [200, 409],
    )
    listed = await client.get("/admin/wacc-assumption-sets")
    item = next(row for row in listed.json() if row["id"] == assumption_set_id)
    assert item["status"] == "approved"
    if update_response.status_code == 200:
        assert item["risk_free_rate"] == 4.75
    else:
        assert update_response.json()["detail"] == (
            "Approved WACC assumption sets are immutable. Create a new version instead."
        )
        assert item["risk_free_rate"] == VALID_SET["risk_free_rate"]


@pytest.mark.asyncio
async def test_admin_can_edit_draft_wacc_set_without_changing_version(client, fresh_all_db):
    await register_test_admin(client, "wacc-editor@example.com")
    created = await client.post("/admin/wacc-assumption-sets", json=VALID_SET)
    assumption_set_id = created.json()["id"]

    updated = await client.put(
        f"/admin/wacc-assumption-sets/{assumption_set_id}",
        json={**VALID_SET, "risk_free_rate": 4.5, "target_debt_weight": 28, "target_equity_weight": 72},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 1
    assert updated.json()["risk_free_rate"] == 4.5
    assert updated.json()["target_debt_weight"] == 28
    assert updated.json()["target_equity_weight"] == 72

    await client.post(f"/admin/wacc-assumption-sets/{assumption_set_id}/approve")
    rejected = await client.put(
        f"/admin/wacc-assumption-sets/{assumption_set_id}", json=VALID_SET
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "Approved WACC assumption sets are immutable. Create a new version instead."
    await register_test_admin(client, "wacc-validation@example.com")

    bad_weights = await client.post(
        "/admin/wacc-assumption-sets",
        json={**VALID_SET, "target_debt_weight": 40},
    )
    assert bad_weights.status_code == 400
    assert bad_weights.json()["detail"] == "Target debt and equity weights must total 100%."

    missing_source = await client.post(
        "/admin/wacc-assumption-sets",
        json={**VALID_SET, "source_references": ""},
    )
    assert missing_source.status_code == 400
    assert missing_source.json()["detail"] == "WACC source references are required."
