"""Audit AccountIQ valuation report JSON/PDF artifacts.

Examples:
    python scripts/audit_valuation_report.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --demo-mode
    python scripts/audit_valuation_report.py --html output/html/accountiq-demo-sample-indicative-valuation.html --demo-mode
    python scripts/audit_valuation_report.py --json output/live-smoke/accountiq-live-valuation-smoke.json --pdf output/pdf/accountiq-live-valuation-smoke.pdf
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from report_quality import (  # noqa: E402
    ReportQualityAudit,
    audit_valuation_report_html,
    audit_valuation_report_content,
    audit_valuation_report_pdf,
)


def _load_report_content(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("content"), dict):
        return payload["content"]
    if isinstance(payload, dict):
        return payload
    raise ValueError("Report JSON must be an object or a live-smoke payload with a content object.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit AccountIQ valuation report artifacts for professional-pack readiness.",
    )
    parser.add_argument("--json", type=Path, help="Report JSON path, or live-smoke JSON payload path.")
    parser.add_argument("--html", type=Path, help="Rendered browser report HTML path.")
    parser.add_argument("--pdf", type=Path, help="Report PDF path.")
    parser.add_argument(
        "--demo-mode",
        action="store_true",
        help="Expect demo labelling in the PDF audit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.json is None and args.html is None and args.pdf is None:
        print("Provide --json, --html, --pdf, or a combination.", file=sys.stderr)
        return 2

    audits: list[ReportQualityAudit] = []
    if args.json is not None:
        audits.append(audit_valuation_report_content(_load_report_content(args.json)))
    if args.html is not None:
        audits.append(audit_valuation_report_html(args.html.read_text(encoding="utf-8"), demo_mode=args.demo_mode))
    if args.pdf is not None:
        audits.append(audit_valuation_report_pdf(args.pdf, demo_mode=args.demo_mode))

    result = {
        "passed": all(audit.passed for audit in audits),
        "audits": [audit.as_dict() for audit in audits],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
