import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _e2e_report_content


def test_e2e_report_content_has_required_valuation_disclaimer():
    content = _e2e_report_content("valuation_advisory")
    text = str(content["disclaimer"]).lower()
    assert "indicative" in text
    assert "financial advice" in text
    assert "fmca" in text
    assert "should not be relied" in text


def test_e2e_report_content_escapes_test_payload_at_view_layer():
    content = _e2e_report_content("valuation_advisory")
    assert "<script>escaped text</script>" in str(content)
