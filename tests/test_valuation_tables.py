from copy import deepcopy

import pytest

from fcff_engine import calculate_fcff
from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION
from test_valuation_inputs import complete_fcff_frozen, complete_fcff_rows
from valuation_inputs import build_valuation_inputs
from valuation_tables import (
    TABLES_ROUNDING_POLICY,
    TABLES_VERSION,
    attach_valuation_tables,
    build_valuation_tables,
    valuation_table_sections,
)


def _authority():
    rows = complete_fcff_rows()
    frozen = complete_fcff_frozen()
    inputs = build_valuation_inputs(rows, frozen, require_fcff=True)
    result = calculate_fcff(inputs)
    multiples = {
        "multiple_low": 3.5,
        "multiple_high": 5.0,
        "normalised_ebitda": 200000.0,
        "enterprise_value_low": 700000.0,
        "enterprise_value_high": 1000000.0,
    }
    return build_valuation_tables(rows, inputs, result, multiples)


def _narratives():
    return {
        section: f"Complete {section} narrative."
        for section in SECTION_SCHEMAS["valuation_advisory"]
    }


def test_builds_all_six_tables_with_explicit_display_policy_and_digest():
    authority = _authority()
    sections = valuation_table_sections(authority)

    assert authority["version"] == TABLES_VERSION
    assert authority["rounding_policy"] == TABLES_ROUNDING_POLICY
    assert len(authority["digest"]) == 64
    assert list(sections) == TABLE_SECTIONS_VALUATION
    assert sections["financial_performance"] == {
        "headers": ["Metric (NZD)", "2025"],
        "rows": [
            ["Revenue", "1,000,000.00"],
            ["EBITDA", "200,000.00"],
            ["Depreciation and amortisation", "-30,000.00"],
        ],
    }
    assert sections["balance_sheet_summary"]["rows"] == [
        ["Interest-bearing debt", "120,000.00"],
        ["Unrestricted cash", "50,000.00"],
        ["Net debt", "70,000.00"],
        ["Approved surplus assets", "0.00"],
    ]
    assert sections["wacc_assumptions"]["rows"][-1] == [
        "WACC", "11.07%", "10.07%", "9.07%",
    ]
    assert sections["valuation_summary"]["headers"] == [
        "Scenario", "WACC", "Enterprise Value (NZD)", "Net Debt (NZD)",
        "Pre-DLOM Equity (NZD)", "DLOM (Rate / NZD)", "Equity Value (NZD)",
    ]
    assert sections["multiples_crosscheck"]["rows"] == [
        ["Market multiple", "3.50x", "5.00x"],
        ["Normalised EBITDA", "200,000.00", "200,000.00"],
        ["Indicated enterprise value", "700,000.00", "1,000,000.00"],
    ]


def test_attachment_replaces_model_tables_and_preserves_narratives():
    authority = _authority()
    generated = _narratives()
    generated["valuation_summary"] = {
        "narrative": "Model narrative.",
        "table": {"headers": ["Unsafe"], "rows": [["999"]]},
    }

    assembled = attach_valuation_tables(generated, authority)

    assert assembled["valuation_summary"]["narrative"] == "Model narrative."
    assert assembled["valuation_summary"]["table"] == authority["sections"]["valuation_summary"]
    assert assembled["financial_performance"]["narrative"] == "Complete financial_performance narrative."
    assert generated["valuation_summary"]["table"]["headers"] == ["Unsafe"]


@pytest.mark.parametrize("field", ["version", "rounding_policy", "digest"])
def test_attachment_rejects_tampered_table_authority(field):
    authority = deepcopy(_authority())
    authority[field] = "tampered"

    with pytest.raises(ValueError, match="deterministic valuation table|unsupported"):
        attach_valuation_tables(_narratives(), authority)


def test_attachment_rejects_tampered_section_even_with_original_digest():
    authority = deepcopy(_authority())
    authority["sections"]["valuation_summary"]["rows"][0][-1] = "999.00"

    with pytest.raises(ValueError, match="digest verification"):
        attach_valuation_tables(_narratives(), authority)
