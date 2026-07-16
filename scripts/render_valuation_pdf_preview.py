"""Render key valuation PDF pages to PNGs for visual QA.

The full report can be long, so the default page set targets the pages most
likely to reveal professional-report issues: cover and valuation snapshot,
contents, basis of preparation, executive valuation conclusion, valuation
assumptions, DCF, valuation summary, multiples cross-check, sensitivity, risk
factors, comparable evidence, sources and closing reference sections.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "output" / "pdf" / "accountiq-demo-sample-indicative-valuation.pdf"
DEFAULT_OUTPUT_DIR = ROOT / "tmp" / "pdfs" / "valuation-preview"
FALLBACK_PAGES = (1, 2, 3, 4, 6, 10, 11, 13, 14, 15, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28)
DEFAULT_PAGE_TARGETS = (
    ("Cover valuation snapshot", ("VALUATION SNAPSHOT", "Enterprise value", "Indicative equity value")),
    ("Contents", ("REPORT NAVIGATION", "Contents")),
    ("Basis of preparation", ("BASIS OF PREPARATION", "Basis of preparation")),
    ("Evidence and model basis", ("BASIS OF PREPARATION", "Evidence and model basis")),
    (
        "Executive valuation conclusion",
        ("ACCOUNTIQ INDICATIVE VALUATION", "02 Executive Summary", "Valuation conclusion at a glance"),
    ),
    ("Valuation methodology", ("ACCOUNTIQ INDICATIVE VALUATION", "06 Valuation Methodology Adopted")),
    ("Financial performance", ("ACCOUNTIQ INDICATIVE VALUATION", "07 Financial Performance")),
    ("Normalisations", ("ACCOUNTIQ INDICATIVE VALUATION", "09 Normalisations")),
    ("Balance sheet summary", ("ACCOUNTIQ INDICATIVE VALUATION", "10 Balance Sheet Summary")),
    ("Valuation assumptions", ("ACCOUNTIQ INDICATIVE VALUATION", "11 Valuation Approach and Assumptions")),
    ("DCF analysis", ("ACCOUNTIQ INDICATIVE VALUATION", "13 Discounted Cash Flow Analysis")),
    ("Indicative valuation summary", ("ACCOUNTIQ INDICATIVE VALUATION", "14 Indicative Valuation Summary")),
    ("Multiples cross-check", ("ACCOUNTIQ INDICATIVE VALUATION", "15 Multiples Cross-check")),
    ("Sensitivity", ("ACCOUNTIQ INDICATIVE VALUATION", "16 Sensitivity and Specific Risks")),
    (
        "Specific risk factors",
        ("Specific risk factors", "Specific risk factor", "Management input", "Valuation relevance", "Report treatment"),
    ),
    ("Comparable evidence", ("ACCOUNTIQ INDICATIVE VALUATION", "17 Comparable Evidence Appendix")),
    ("Sources", ("ACCOUNTIQ INDICATIVE VALUATION", "18 Sources and References")),
    ("Disclaimer", ("ACCOUNTIQ INDICATIVE VALUATION", "19 Disclaimer")),
    ("General principles", ("ACCOUNTIQ INDICATIVE VALUATION", "20 General Principles")),
    ("Glossary", ("ACCOUNTIQ INDICATIVE VALUATION", "21 Glossary")),
)


def _parse_pages(value: str) -> list[int] | None:
    if value.strip().lower() == "auto":
        return None

    pages: list[int] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start <= 0 or end < start:
                raise ValueError(f"Invalid page range: {part}")
            pages.extend(range(start, end + 1))
        else:
            page = int(part)
            if page <= 0:
                raise ValueError(f"Invalid page number: {part}")
            pages.append(page)
    return sorted(set(pages))


def _extract_pdf_page_text(pdf_path: Path) -> list[str]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is required for automatic preview page selection. "
            "Install project dependencies or pass --pages explicitly."
        ) from exc

    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def _default_preview_page_hits(pdf_path: Path) -> tuple[list[int], list[dict]]:
    """Select visual-QA pages and record which report target each page proves."""
    try:
        page_texts = _extract_pdf_page_text(pdf_path)
    except Exception:
        return list(FALLBACK_PAGES), []

    selected_pages = {1}
    target_hits: list[dict] = []
    for label, markers in DEFAULT_PAGE_TARGETS:
        matched_page = None
        for index, page_text in enumerate(page_texts, start=1):
            if all(marker in page_text for marker in markers):
                matched_page = index
                selected_pages.add(index)
                break
        target_hits.append(
            {
                "label": label,
                "page": matched_page,
                "markers": list(markers),
            }
        )

    if len(selected_pages) <= 1:
        return list(FALLBACK_PAGES), target_hits
    return sorted(selected_pages), target_hits


def _default_preview_pages(pdf_path: Path) -> list[int]:
    """Select visual-QA pages from the actual report structure, with a static fallback."""
    pages, _target_hits = _default_preview_page_hits(pdf_path)
    return pages


def _pdftoppm_binary() -> str:
    binary = shutil.which("pdftoppm")
    if not binary:
        raise RuntimeError("pdftoppm is required. Install Poppler or use the bundled Codex runtime.")
    return binary


def render_pdf_preview(
    pdf_path: Path,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    pages: list[int] | tuple[int, ...] | None = None,
    resolution: int = 110,
) -> dict:
    """Render selected one-indexed PDF pages and return a manifest dict."""
    pdf_path = pdf_path.expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")
    if not pdf_path.read_bytes().startswith(b"%PDF-"):
        raise ValueError(f"File does not look like a PDF: {pdf_path}")

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    font_cache = output_dir / ".font-cache"
    font_cache.mkdir(parents=True, exist_ok=True)

    selection_mode = "auto" if pages is None else "manual"
    target_hits: list[dict] = []
    if pages is None:
        pages, target_hits = _default_preview_page_hits(pdf_path)

    binary = _pdftoppm_binary()
    env = os.environ.copy()
    env["XDG_CACHE_HOME"] = str(font_cache)

    rendered = []
    for page in pages:
        prefix = output_dir / f"{pdf_path.stem}-page-{page:02d}"
        result = subprocess.run(
            [
                binary,
                "-png",
                "-r",
                str(int(resolution)),
                "-f",
                str(int(page)),
                "-l",
                str(int(page)),
                str(pdf_path),
                str(prefix),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pdftoppm failed for page {page}: {result.stderr.strip() or result.stdout.strip()}"
            )
        output_file = output_dir / f"{prefix.name}-{page:02d}.png"
        if not output_file.exists():
            # Poppler's suffix can vary when -f/-l are used; fall back to the
            # first file matching this prefix.
            matches = sorted(output_dir.glob(f"{prefix.name}-*.png"))
            if not matches:
                raise RuntimeError(f"pdftoppm did not create a PNG for page {page}")
            output_file = matches[0]
        rendered.append({"page": int(page), "path": str(output_file)})

    manifest = {
        "pdf": str(pdf_path),
        "output_dir": str(output_dir),
        "resolution": int(resolution),
        "selection_mode": selection_mode,
        "pages": rendered,
        "page_targets": target_hits,
    }
    manifest_path = output_dir / f"{pdf_path.stem}-preview-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render key AccountIQ valuation PDF pages for visual QA.",
    )
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--pages",
        default="auto",
        help="Use 'auto' to select key report pages, or pass comma-separated pages/ranges, e.g. 1,2,3,14,16,19-22.",
    )
    parser.add_argument("--resolution", type=int, default=110)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = render_pdf_preview(
            args.pdf,
            output_dir=args.output_dir,
            pages=_parse_pages(args.pages),
            resolution=args.resolution,
        )
    except Exception as exc:
        print(f"PDF preview rendering failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
