"""Unit tests for build_prompt() valuation_advisory branch (Phase 05.1)."""
import sys
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from report_prompts import build_prompt, TABLE_SECTIONS_VALUATION, SECTION_SCHEMAS


def _sample_valuation_result():
    return {
        "research_brief": {
            "company_summary": "Acme Ltd is a NZ digital agency...",
            "sector_summary": "The NZ agency sector...",
            "comparable_transactions": "Recent NZ deals: ...",
            "risk_free_rate": 4.65, "erp": 5.94, "industry_beta": 1.08,
            "industry_category": "Software (System & Application)",
            "inflation_rate": 2.5,
            "sources": ["https://rbnz.govt.nz/...", "https://pages.stern.nyu.edu/~adamodar/.../totalbeta.html"],
        },
        "deterministic_fcff": {
            "engine_version": "fcff-decimal-v1",
            "calculation_digest": "abc123",
            "instruction": "Copy these deterministic numeric strings without recalculation.",
            "currency": "NZD",
            "forecast": [{"year": 1, "fcff": "111344"}],
            "terminal_forecast": {"year": 6, "fcff": "149827.735668096"},
            "wacc": {
                "risk_free_rate": "0.04", "equity_risk_premium": "0.055",
                "beta": "1.1", "cost_of_equity": "0.1205", "mid": "0.1",
                "high": "0.11", "low": "0.09",
            },
            "scenarios": [
                {
                    "name": "high_wacc_low_value", "enterprise_value": "4000000",
                    "net_debt": "200000", "approved_surplus_assets": "0",
                    "pre_dlom_equity_value": "3800000", "dlom_rate": "0.1",
                    "dlom_amount": "380000", "equity_value": "3420000",
                }
            ],
        },
        "normalised_ebitda": 850000,
        "normalisations": [
            {"label": "Owner salary", "amount": 50000, "rationale": "above market"},
        ],
        "revenues": 5200000,
        "net_debt": 200000,
        "cash": 150000,
    }


def test_build_prompt_valuation_includes_table_instruction():
    sys_p, usr = build_prompt(
        report_type="valuation_advisory",
        company_name="Acme Ltd", industry="Digital Agency", description="A NZ agency.",
        financial_rows=[],
        intake_answers={
            "normalisations": [{"label": "Owner salary", "amount": 50000, "rationale": "above market"}],
            "forecast_horizon": "5",
            "revenue_growth_cagr": 8.0,
            "terminal_growth_rate": 2.5,
        },
        management_team=[], ebitda_adjustments=[],
        valuation_result=_sample_valuation_result(),
    )
    for s in TABLE_SECTIONS_VALUATION:
        assert s in sys_p, f"system prompt missing table section name: {s}"
    assert "table" in sys_p and "narrative" in sys_p
    assert "Acme Ltd" in usr
    assert "Research Brief" in usr
    assert "Deterministic Decimal FCFF" in usr
    assert "fcff-decimal-v1" in usr
    assert "abc123" in usr
    assert "149827.735668096" in usr
    assert "Research WACC inputs are narrative context only" in usr
    assert "Owner salary" in usr


def test_build_prompt_valuation_requires_valuation_result():
    with pytest.raises(ValueError, match="valuation_result is required"):
        build_prompt(
            report_type="valuation_advisory", company_name="A", industry="", description="",
            financial_rows=[], intake_answers={}, management_team=[], ebitda_adjustments=[],
            valuation_result=None,
        )


def test_build_prompt_other_report_types_unchanged_format():
    with pytest.raises(ValueError, match="bank_credit_figures is required"):
        build_prompt(
            report_type="bank_credit_paper", company_name="A", industry="", description="",
            financial_rows=[], intake_answers={}, management_team=[], ebitda_adjustments=[],
            bank_credit_figures=None,
        )
    sys_p, _ = build_prompt(
        report_type="financial_forecast", company_name="A", industry="", description="",
        financial_rows=[],
        intake_answers={"forecast_horizon": "3 years", "revenue_growth_rate": 0.05},
        management_team=[], ebitda_adjustments=[],
    )
    assert "non-empty string" in sys_p
    assert "financial_performance" not in sys_p


def test_valuation_table_sections_match_structured_prompt_contract():
    assert len(TABLE_SECTIONS_VALUATION) == 6
    assert "multiples_crosscheck" in TABLE_SECTIONS_VALUATION
    assert set(TABLE_SECTIONS_VALUATION).issubset(set(SECTION_SCHEMAS["valuation_advisory"]))
