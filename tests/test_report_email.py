from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from report_email import _report_link


def test_report_link_uses_next_proxy_for_frontend_origin():
    assert (
        _report_link("http://localhost:3000", 42)
        == "http://localhost:3000/api/backend/wizard/report/42/view"
    )


def test_report_link_uses_direct_viewer_for_fastapi_origin():
    assert (
        _report_link("http://localhost:8765", 42)
        == "http://localhost:8765/wizard/report/42/view"
    )
