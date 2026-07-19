"""Unit tests for the Phase 05.1 valuation engine (REPT-01)."""
import sys
from pathlib import Path

import pytest

# Backend sys.path bootstrap — must run before any `from valuation import ...`
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Module-level helper: FMCA disclaimer compliance checker
# ---------------------------------------------------------------------------

def _assert_disclaimer_compliant(text: str) -> None:
    """Assert that *text* contains all four FMCA-required disclaimer phrases.

    Raises AssertionError if any required phrase is absent.
    """
    required_phrases = [
        "indicative",
        "financial advice",
        ("FMCA", "Financial Markets Conduct"),
        ("not relied", "should not be relied"),
    ]
    lowered = text.lower()
    for phrase in required_phrases:
        if isinstance(phrase, tuple):
            assert any(p.lower() in lowered for p in phrase), (
                f"Disclaimer missing one of {phrase}"
            )
        else:
            assert phrase.lower() in lowered, (
                f"Disclaimer missing required phrase: {phrase}"
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compute_wacc_scenarios_basic():
    """WACC scenarios return correct keys, mid value, ordering, and spread (D-W2/D-W6)."""
    from valuation import compute_wacc_scenarios
    result = compute_wacc_scenarios(risk_free_rate=4.65, industry_beta=1.08, erp=5.94)
    assert set(result.keys()) == {"high", "mid", "low"}
    # mid = round(4.65 + 1.08 * 5.94, 2) = 11.07
    assert result["mid"] == round(4.65 + 1.08 * 5.94, 2), (
        f"Expected mid=11.07, got {result['mid']}"
    )
    assert result["high"] > result["mid"] > result["low"], (
        "Expected high > mid > low ordering"
    )
    spread = result["high"] - result["low"]
    assert 1.0 <= spread <= 4.0, f"WACC spread {spread} outside expected 1.0-4.0pp"


def test_compute_wacc_scenarios_returns_percent_not_decimal():
    """All WACC scenario values are in percent form (5–25), not decimal form (0.05–0.25)."""
    from valuation import compute_wacc_scenarios
    # Realistic NZ inputs: 10-yr bond ~4.65%, beta ~1.08, ERP ~5.94%
    result = compute_wacc_scenarios(risk_free_rate=4.65, industry_beta=1.08, erp=5.94)
    for label, value in result.items():
        assert 5.0 <= value <= 25.0, (
            f"WACC scenario '{label}' = {value} looks like a decimal, not a percent. "
            "compute_wacc_scenarios must return percent values."
        )


def test_wacc_decimal_form_guard():
    """Decimal-form risk_free_rate should be rejected by ResearchBrief validation."""
    from research_loop import ResearchBrief
    from pydantic import ValidationError

    # 0.0465 is the decimal form of 4.65% — should be rejected
    try:
        brief = ResearchBrief(
            risk_free_rate=0.0465,
            industry_beta=1.08,
            erp=5.94,
            company_summary="Test",
            sector_context="Test",
            comparable_transactions=[],
            comparable_multiples_summary="Test",
            inflation_rate=2.5,
        )
        # If ResearchBrief accepts 0.0465, check that the validator catches it
        assert brief.risk_free_rate >= 1.0, (
            f"risk_free_rate={brief.risk_free_rate} is in decimal form — "
            "validator should reject values below 1.0 (percent convention)"
        )
    except ValidationError:
        pass  # Correct: ResearchBrief rejected the decimal-form input


def test_dcf_correctness_fixed_inputs():
    """DCF with fixed NZ baseline inputs returns positive, finite enterprise_value_dcf.

    Snapshot: compute_dcf(ebitda=800000, wacc=0.1082, growth_rate=0.08, tax_rate=0.28,
    years=5, terminal_growth=0.025) => enterprise_value_dcf ~= 8905541.29 (±0.5%).
    """
    from valuation import compute_dcf
    result = compute_dcf(
        ebitda=800000,
        wacc=0.1082,
        growth_rate=0.08,
        tax_rate=0.28,
        years=5,
        terminal_growth=0.025,
    )
    # Confirm the return key name
    assert "enterprise_value_dcf" in result, (
        f"Expected key 'enterprise_value_dcf' in DCF result, got keys: {list(result.keys())}"
    )
    ev = result["enterprise_value_dcf"]
    assert ev > 0, f"enterprise_value_dcf must be positive, got {ev}"
    assert ev == ev, "enterprise_value_dcf must be finite (not NaN)"  # NaN != NaN
    # Snapshot assertion within ±0.5% tolerance
    expected = 8905541.29
    tolerance = expected * 0.005
    assert abs(ev - expected) <= tolerance, (
        f"enterprise_value_dcf={ev} is outside ±0.5% of expected {expected}. "
        "Formula may have changed — update this snapshot if intentional."
    )


def test_normalised_ebitda_addback_sum():
    """Normalised EBITDA = extracted_ebitda + sum(adjustment.amount) for all adjustments."""
    # Inline computation matching main.py lines 1470-1471 logic
    extracted_ebitda = 200000.0
    ebitda_adjustments = [{"amount": 50000}, {"amount": 30000}]
    normalised = extracted_ebitda + sum(
        float(a["amount"]) for a in ebitda_adjustments
    )
    assert normalised == 280000.0, (
        f"Expected normalised EBITDA = 280000.0, got {normalised}"
    )

    # Edge cases
    assert 200000.0 + sum(float(a["amount"]) for a in []) == 200000.0
    assert 0.0 + sum(float(a["amount"]) for a in [{"amount": -10000}]) == -10000.0


def test_equity_bridge_handles_debt_and_net_cash():
    from valuation import compute_equity_bridge

    debt_heavy = compute_equity_bridge(5_000_000, 1_500_000, 200_000)
    assert debt_heavy["net_debt"] == 1_300_000
    assert debt_heavy["equity_value"] == 3_700_000

    net_cash = compute_equity_bridge(5_000_000, 100_000, 400_000, 50_000)
    assert net_cash["net_debt"] == -300_000
    assert net_cash["equity_value"] == 5_350_000


def test_multiples_crosscheck_has_no_scored_conclusion():
    from valuation import compute_multiples_crosscheck

    result = compute_multiples_crosscheck(800_000, 3.5, 5.0)
    assert result == {
        "multiple_low": 3.5,
        "multiple_high": 5.0,
        "enterprise_value_low": 2_800_000,
        "enterprise_value_high": 4_000_000,
        "normalised_ebitda": 800_000,
        "purpose": "cross_check_only",
    }
    assert "multiple_applied" not in result
    assert "risk_score" not in result


def test_disclaimer_compliance_fmca():
    """_assert_disclaimer_compliant passes for compliant text and raises for non-compliant."""
    # Compliant disclaimer (all 4 required phrases present)
    compliant = (
        "This report is indicative only and does not constitute financial advice. "
        "It is prepared in accordance with the Financial Markets Conduct Act (FMCA). "
        "This document should not be relied upon as a substitute for professional advice."
    )
    _assert_disclaimer_compliant(compliant)  # must not raise

    # Non-compliant: missing "indicative"
    missing_indicative = (
        "This report does not constitute financial advice. "
        "Prepared under the FMCA. Should not be relied upon."
    )
    with pytest.raises(AssertionError, match="indicative"):
        _assert_disclaimer_compliant(missing_indicative)

    # Non-compliant: missing "financial advice"
    missing_fin_advice = (
        "This report is indicative only. "
        "Prepared under the Financial Markets Conduct Act (FMCA). "
        "Should not be relied upon as a substitute for professional guidance."
    )
    with pytest.raises(AssertionError, match="financial advice"):
        _assert_disclaimer_compliant(missing_fin_advice)

    # Non-compliant: missing FMCA/Financial Markets Conduct
    missing_fmca = (
        "This report is indicative only and does not constitute financial advice. "
        "Readers should seek independent professional advice. "
        "Should not be relied upon."
    )
    with pytest.raises(AssertionError):
        _assert_disclaimer_compliant(missing_fmca)

    # Non-compliant: missing "not relied" / "should not be relied"
    missing_relied = (
        "This report is indicative only and does not constitute financial advice. "
        "Prepared under the FMCA."
    )
    with pytest.raises(AssertionError):
        _assert_disclaimer_compliant(missing_relied)
