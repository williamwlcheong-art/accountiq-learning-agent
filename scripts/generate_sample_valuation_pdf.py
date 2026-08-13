"""Generate the shareable AccountIQ sample valuation PDF.

This script intentionally uses the same PDF renderer and deterministic demo
report content as the app's no-key/demo path. It gives us a reproducible sample
artifact for reviewing the current valuation-report output without requiring a
live OpenAI key.
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

from main import _REPORT_SECTION_TITLES, _e2e_report_content  # noqa: E402
from report_prompts import SECTION_SCHEMAS  # noqa: E402
from report_quality import audit_valuation_report_content, audit_valuation_report_pdf  # noqa: E402
from report_rendering import write_report_pdf  # noqa: E402


DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "accountiq-demo-sample-indicative-valuation.pdf"
DEFAULT_COMPANY_NAME = "AccountIQ Sample Limited"
DEFAULT_PREPARED_AT = "2026-07-04 09:30:00"
DEFAULT_PURPOSE = "Understand what the business may be worth"
DEFAULT_INTAKE_ANSWERS = {
    "valuation_purpose": "understand_value",
    "owner_dependency": "shared",
    "customer_concentration": "10_to_25",
    "revenue_quality": "mixed",
    "revenue_outlook": "not_sure",
}


def _raise_if_audit_failed(audit: object) -> None:
    if not audit.passed:
        raise RuntimeError(json.dumps(audit.as_dict(), indent=2))


def sample_report_content(*, demo_mode: bool = True, run_audit: bool = True) -> dict:
    """Return deterministic sample report content, optionally audited before rendering."""
    sections = _e2e_report_content("valuation_advisory", demo_mode=demo_mode)
    if run_audit:
        _raise_if_audit_failed(audit_valuation_report_content(sections))
    return sections


def audit_generated_pdf(path: Path, *, demo_mode: bool) -> object:
    """Audit a generated sample PDF and raise if it misses report markers."""
    audit = audit_valuation_report_pdf(path, demo_mode=demo_mode)
    _raise_if_audit_failed(audit)
    return audit


def generate_sample_pdf(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    company_name: str = DEFAULT_COMPANY_NAME,
    prepared_at: str = DEFAULT_PREPARED_AT,
    valuation_purpose: str = DEFAULT_PURPOSE,
    report_id: int = 9001,
    demo_mode: bool = True,
    run_audit: bool = True,
) -> Path:
    """Generate the deterministic sample valuation PDF and return its path."""
    output_path = output_path.expanduser().resolve()
    sections = sample_report_content(demo_mode=demo_mode, run_audit=run_audit)
    write_report_pdf(
        output_path,
        company_name=company_name,
        report_label=(
            "Demo Indicative Valuation Report"
            if demo_mode
            else "Indicative Valuation Report"
        ),
        report_type="valuation_advisory",
        valuation_purpose=valuation_purpose,
        intake_answers=DEFAULT_INTAKE_ANSWERS,
        sections=sections,
        section_order=SECTION_SCHEMAS["valuation_advisory"],
        section_titles=_REPORT_SECTION_TITLES,
        report_id=report_id,
        generated_at=prepared_at,
        demo_mode=demo_mode,
    )
    if run_audit:
        audit_generated_pdf(output_path, demo_mode=demo_mode)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the AccountIQ sample indicative valuation PDF.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output PDF path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument("--company-name", default=DEFAULT_COMPANY_NAME)
    parser.add_argument("--prepared-at", default=DEFAULT_PREPARED_AT)
    parser.add_argument("--valuation-purpose", default=DEFAULT_PURPOSE)
    parser.add_argument("--report-id", type=int, default=9001)
    parser.add_argument(
        "--live-label",
        action="store_true",
        help="Use non-demo labelling while still using deterministic sample content.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = generate_sample_pdf(
        args.output,
        company_name=args.company_name,
        prepared_at=args.prepared_at,
        valuation_purpose=args.valuation_purpose,
        report_id=args.report_id,
        demo_mode=not args.live_label,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
