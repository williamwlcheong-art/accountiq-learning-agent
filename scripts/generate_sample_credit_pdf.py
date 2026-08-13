"""Generate the reproducible AccountIQ sample bank credit-paper PDF."""
from __future__ import annotations

import argparse
from pathlib import Path

from sample_credit_report import (  # noqa: E402
    DEFAULT_PDF_NAME,
    ROOT,
    generate_sample_pdf,
)


DEFAULT_OUTPUT = ROOT / "output" / "pdf" / DEFAULT_PDF_NAME


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the AccountIQ sample bank credit-paper PDF.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-id", type=int, default=9002)
    args = parser.parse_args()
    output_path = generate_sample_pdf(args.output, report_id=args.report_id)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
