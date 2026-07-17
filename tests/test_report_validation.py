import aiosqlite
import pytest

from db import DB_PATH
import main as main_module
from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION
from report_validation import validate_generated_report


SAFE_GENERATION_ERROR = (
    "We couldn't generate a complete report. Please retry, or contact support if the problem continues."
)


def _valid_section(section: str):
    if section in TABLE_SECTIONS_VALUATION:
        return {
            "narrative": f"Complete analysis for {section} based on the supplied financial data.",
            "table": {
                "headers": ["Metric", "Value"],
                "rows": [["Revenue", "$1,250,000"]],
            },
        }
    if section == "disclaimer":
        return (
            "This report is indicative only and does not constitute financial advice under the "
            "Financial Markets Conduct Act (FMCA). It should not be relied on without independent "
            "professional advice."
        )
    return f"Complete analysis for {section} based on the supplied financial data."


def _valid_report(report_type: str = "valuation_advisory") -> dict:
    return {section: _valid_section(section) for section in SECTION_SCHEMAS[report_type]}


@pytest.mark.parametrize(
    "raw_text",
    [
        "not JSON",
        '{"introduction": "truncated"',
        "```json\nnot JSON\n```",
    ],
)
def test_report_parser_rejects_malformed_json(raw_text):
    with pytest.raises(ValueError, match="valid JSON object"):
        main_module._parse_json_from_response(raw_text)


@pytest.mark.parametrize(
    ("mutate", "error_match"),
    [
        (lambda report: report.pop("business_overview"), "missing required sections"),
        (lambda report: report.__setitem__("business_overview", "  "), "empty required section"),
        (
            lambda report: report.__setitem__(
                "business_overview", "[Section 'business_overview' not generated — please retry]"
            ),
            "placeholder content",
        ),
        (
            lambda report: report["financial_performance"]["table"]["rows"].__setitem__(
                0, ["Revenue", "[Generation error — please retry]"]
            ),
            "placeholder content",
        ),
        (
            lambda report: report["financial_performance"].__setitem__(
                "table", {"headers": ["Metric", "Value"], "rows": [["Revenue"]]}
            ),
            "invalid table",
        ),
        (
            lambda report: report.__setitem__(
                "disclaimer", "This report contains a preliminary valuation estimate."
            ),
            "disclaimer",
        ),
    ],
)
def test_generated_valuation_validation_fails_closed(mutate, error_match):
    report = _valid_report()
    mutate(report)

    with pytest.raises(ValueError, match=error_match):
        validate_generated_report(report, "valuation_advisory")


def test_generated_valuation_validation_accepts_complete_report():
    report = _valid_report()

    validate_generated_report(report, "valuation_advisory")


@pytest.mark.asyncio
async def test_invalid_generated_report_is_failed_with_safe_customer_error(
    fresh_all_db, monkeypatch
):
    report_type = "information_memorandum"
    invalid_content = _valid_report(report_type)
    invalid_content["operations"] = "TODO"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO users (email, hashed_pw) VALUES ('buyer@example.com', 'hash')"
        ) as cur:
            user_id = cur.lastrowid
        async with db.execute(
            "INSERT INTO companies (name, exchange, user_id) VALUES ('Validation Ltd', 'Private', ?)",
            (user_id,),
        ) as cur:
            company_id = cur.lastrowid
        async with db.execute(
            """
            INSERT INTO reports (company_id, user_id, report_type, status)
            VALUES (?, ?, ?, 'queued')
            """,
            (company_id, user_id, report_type),
        ) as cur:
            report_id = cur.lastrowid
        await db.commit()

    async def fake_report_call(*args, **kwargs):
        return invalid_content

    monkeypatch.setattr(main_module, "E2E_MODE", False)
    monkeypatch.setattr(main_module, "_call_claude_for_report", fake_report_call)

    await main_module._generate_report(report_id)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, content, error_message FROM reports WHERE id=?", (report_id,)
        ) as cur:
            report = await cur.fetchone()

    assert report["status"] == "failed"
    assert report["content"] is None
    assert report["error_message"] == SAFE_GENERATION_ERROR
    assert "TODO" not in report["error_message"]
