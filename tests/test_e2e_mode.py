import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _e2e_report_content
from report_prompts import SECTION_SCHEMAS, TABLE_SECTIONS_VALUATION


def test_e2e_report_content_has_required_valuation_disclaimer():
    content = _e2e_report_content("valuation_advisory")
    text = str(content["disclaimer"]).lower()
    assert "indicative" in text
    assert "financial advice" in text
    assert "fmca" in text
    assert "should not be relied" in text


def test_e2e_report_content_is_clean_for_demo_viewing():
    content = _e2e_report_content("valuation_advisory")
    assert "<script" not in str(content).lower()
    assert "Indicative equity value" in str(content)


def test_e2e_valuation_sample_has_formal_introduction_framing():
    content = _e2e_report_content("valuation_advisory")
    introduction = content["introduction"]

    assert "## Client and report purpose" in introduction
    assert "## Valuation date and basis of value" in introduction
    assert "## Sources of information" in introduction
    assert "## Liability, confidentiality and compliance" in introduction
    assert "uploaded financial information" in introduction
    assert "management-confirmed private inputs" in introduction
    assert "AccountIQ valuation calculations" in introduction
    assert "model-computed" not in introduction
    assert "Python-computed" not in introduction
    assert "public source urls are retained" in introduction.lower()
    assert "not an independent business valuation report" in introduction
    assert "does not constitute financial advice" in introduction


def test_e2e_valuation_sample_covers_full_report_schema_and_schedules():
    content = _e2e_report_content("valuation_advisory")
    assert list(content) == SECTION_SCHEMAS["valuation_advisory"]
    for section in TABLE_SECTIONS_VALUATION:
        assert isinstance(content[section], dict), section
        assert content[section]["narrative"], section
        assert content[section]["table"]["headers"], section
        assert content[section]["table"]["rows"], section
