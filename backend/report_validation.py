"""Shared fail-closed validation for generated report content."""
from __future__ import annotations

from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION


PLACEHOLDER_REPORT_PATTERNS = (
    "[section '",
    "[generation error",
    "not generated",
    "could not be parsed",
    "failed to parse",
    "please retry",
    "placeholder",
    "todo",
    "tbd",
    "lorem ipsum",
)


def section_narrative(section_content) -> str:
    if isinstance(section_content, str):
        return section_content.strip()
    if isinstance(section_content, dict):
        narrative = section_content.get("narrative")
        return narrative.strip() if isinstance(narrative, str) else ""
    return ""


def contains_report_placeholder(value) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(pattern in lowered for pattern in PLACEHOLDER_REPORT_PATTERNS)
    if isinstance(value, dict):
        return any(contains_report_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_report_placeholder(item) for item in value)
    return False


def validate_report_table(section_name: str, table) -> None:
    if not isinstance(table, dict):
        raise ValueError(f"invalid table in section '{section_name}'")

    headers = table.get("headers")
    rows = table.get("rows")
    if not isinstance(headers, list) or not headers:
        raise ValueError(f"invalid table headers in section '{section_name}'")
    if any(
        not isinstance(header, (str, int, float)) or not str(header).strip()
        for header in headers
    ):
        raise ValueError(f"invalid table headers in section '{section_name}'")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"invalid table rows in section '{section_name}'")

    width = len(headers)
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError(f"invalid table row shape in section '{section_name}'")
        if any(isinstance(cell, (dict, list)) or cell is None for cell in row):
            raise ValueError(f"invalid table cell in section '{section_name}'")


def validate_generated_report(content_json: dict, report_type: str) -> None:
    """Reject incomplete or malformed model output before review or release."""
    if not isinstance(content_json, dict):
        raise ValueError("generated report must be a JSON object")

    expected_sections = SECTION_SCHEMAS[report_type]
    missing = [section for section in expected_sections if section not in content_json]
    if missing:
        raise ValueError(f"missing required sections: {missing}")

    for section_name in expected_sections:
        section_content = content_json[section_name]
        if not section_narrative(section_content):
            raise ValueError(f"empty required section: {section_name}")
        if contains_report_placeholder(section_content):
            raise ValueError(f"placeholder content in section: {section_name}")

        if isinstance(section_content, dict):
            unexpected_keys = set(section_content) - {"narrative", "table"}
            if unexpected_keys:
                raise ValueError(f"invalid structured section shape: {section_name}")
            if "table" in section_content:
                validate_report_table(section_name, section_content["table"])
        elif not isinstance(section_content, str):
            raise ValueError(f"invalid section shape: {section_name}")

        if report_type == "valuation_advisory" and section_name in TABLE_SECTIONS_VALUATION:
            if not isinstance(section_content, dict) or "table" not in section_content:
                raise ValueError(f"invalid table in section '{section_name}'")

    if report_type == "valuation_advisory":
        disclaimer = section_narrative(content_json["disclaimer"]).lower()
        required_phrases = (
            ("indicative",),
            ("financial advice",),
            ("fmca", "financial markets conduct"),
            ("not relied", "should not be relied"),
        )
        if any(
            not any(phrase in disclaimer for phrase in alternatives)
            for alternatives in required_phrases
        ):
            raise ValueError("valuation disclaimer is incomplete")
