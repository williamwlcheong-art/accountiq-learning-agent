"""Generate the shareable AccountIQ sample valuation browser report HTML.

This script intentionally uses the same deterministic demo report content and
the same lower-level HTML renderers as the app's report viewer. It gives us a
reproducible browser artifact for reviewing the current valuation-report output
without requiring a live OpenAI key or a running dev server.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _e2e_report_content  # noqa: E402
from main import (  # noqa: E402
    _render_cover_report_brief_html,
    _render_cover_report_basis_html,
    _render_cover_valuation_snapshot_html,
    _render_report_contents_html,
    _render_report_sections_html,
    _render_valuation_basis_html,
)
from report_prompts import SECTION_SCHEMAS  # noqa: E402
from report_quality import audit_valuation_report_content, audit_valuation_report_html  # noqa: E402


DEFAULT_OUTPUT = ROOT / "output" / "html" / "accountiq-demo-sample-indicative-valuation.html"
DEFAULT_COMPANY_NAME = "AccountIQ Sample Limited"
DEFAULT_PREPARED_AT = "2026-07-04 09:30:00"
DEFAULT_PURPOSE = "Understand what the business may be worth"
DEFAULT_PDF_HREF = "./pdf"
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


def _viewer_styles() -> str:
    """Return compact standalone styles for the generated browser artifact."""
    return """
    :root { --navy:#082b4c; --blue:#1769aa; --ink:#172033; --muted:#667085; --line:#d7dee8; }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body {
      margin:0;
      background:#edf1f5;
      color:var(--ink);
      font-family:"Aptos","Segoe UI",Arial,sans-serif;
      line-height:1.58;
    }
    .viewer-toolbar {
      position:sticky;
      top:0;
      z-index:10;
      display:flex;
      justify-content:space-between;
      align-items:center;
      min-height:52px;
      padding:8px max(20px, calc((100vw - 900px)/2));
      background:rgba(8,43,76,.96);
      color:white;
      box-shadow:0 2px 10px rgba(8,43,76,.18);
    }
    .viewer-toolbar a { color:white; text-decoration:none; font-size:.875rem; font-weight:700; }
    .viewer-toolbar span { font-size:.78rem; opacity:.82; }
    .viewer-toolbar-actions { display:flex; align-items:center; gap:14px; }
    .viewer-download {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:34px;
      padding:7px 12px;
      border:1px solid rgba(255,255,255,.56);
      border-radius:999px;
      background:rgba(255,255,255,.12);
    }
    .report { width:min(900px, calc(100% - 32px)); margin:28px auto 64px; }
    .demo-banner {
      margin:0 0 18px;
      padding:14px 18px;
      border:1px solid #e3ad55;
      border-radius:8px;
      background:#fff8e8;
      color:#70450a;
      font-size:.88rem;
    }
    .demo-banner strong { display:block; margin-bottom:2px; }
    .report-page {
      min-height:1120px;
      margin:0 0 22px;
      padding:78px 74px;
      background:white;
      box-shadow:0 12px 30px rgba(15,23,42,.10);
    }
    .cover {
      position:relative;
      display:flex;
      flex-direction:column;
      justify-content:flex-end;
      overflow:hidden;
      min-height:1120px;
      margin:0 0 22px;
      padding:84px 76px;
      background:linear-gradient(150deg, #f8fbff 0 52%, #dceafb 52% 64%, #082b4c 64%);
      color:white;
    }
    .cover::before { content:""; position:absolute; top:72px; left:76px; width:86px; height:7px; background:#2f80c5; }
    .brand { position:absolute; top:98px; left:76px; color:var(--navy); font-size:1.05rem; font-weight:900; letter-spacing:.04em; }
    .cover-copy {
      position:relative;
      max-width:760px;
      padding:28px 32px 30px;
      border:1px solid rgba(207,226,243,.28);
      border-radius:22px;
      background:rgba(8,43,76,.92);
      box-shadow:0 20px 42px rgba(8,43,76,.24);
    }
    .cover-snapshot {
      position:relative;
      width:100%;
      margin:0 0 78px;
      padding:20px 24px 18px;
      border:1px solid #c8d6e5;
      border-radius:18px;
      background:white;
      color:var(--ink);
      box-shadow:0 16px 35px rgba(8,43,76,.12);
    }
    .cover-snapshot span {
      display:block;
      margin:-20px -24px 16px;
      padding:10px 24px;
      border-radius:18px 18px 0 0;
      background:var(--blue);
      color:white;
      font-size:.82rem;
      font-weight:850;
      letter-spacing:.06em;
      text-transform:uppercase;
    }
    .cover-snapshot table, .report-table { width:100%; border-collapse:collapse; }
    .cover-snapshot th, .cover-snapshot td, .report-table th, .report-table td {
      padding:10px 0;
      border-bottom:1px solid var(--line);
      vertical-align:top;
      text-align:left;
    }
    .cover-snapshot th:not(:first-child), .cover-snapshot td:not(:first-child) { text-align:right; }
    .cover-snapshot tbody td:not(:first-child) { font-weight:800; font-variant-numeric:tabular-nums; }
    .cover-snapshot p { margin:10px 0 0; color:var(--muted); font-size:.76rem; }
    .cover-report-basis {
      position:relative;
      width:100%;
      margin:58px 0 34px;
      padding:18px 22px;
      border:1px solid var(--line);
      border-radius:18px;
      background:rgba(255,255,255,.92);
      color:var(--ink);
      box-shadow:0 12px 28px rgba(8,43,76,.10);
    }
    .cover-report-basis span {
      display:block;
      margin:0 0 13px;
      color:var(--blue);
      font-size:.72rem;
      font-weight:850;
      letter-spacing:.08em;
      text-transform:uppercase;
    }
    .cover-report-basis dl { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:0; margin:0; }
    .cover-report-basis div { min-width:0; padding:0 18px; border-left:1px solid var(--line); }
    .cover-report-basis div:first-child { padding-left:0; border-left:0; }
    .cover-report-basis dt { margin:0 0 5px; color:var(--navy); font-size:.78rem; font-weight:850; }
    .cover-report-basis dd { margin:0; color:var(--muted); font-size:.7rem; line-height:1.35; }
    .cover-kicker {
      display:block;
      margin-bottom:12px;
      color:#b9d8f2;
      font-size:.78rem;
      font-weight:800;
      letter-spacing:.14em;
      text-transform:uppercase;
    }
    .cover h1 { max-width:650px; margin:0 0 18px; font-size:3.3rem; line-height:1.05; letter-spacing:-.035em; }
    .cover .company { margin:0; font-size:1.45rem; font-weight:600; }
    .cover-brief { margin:30px 0 0; padding:18px 20px; border:1px solid rgba(207,226,243,.36); border-radius:14px; background:rgba(255,255,255,.08); }
    .cover-brief dl { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:14px 20px; margin:0; }
    .cover-brief dt { color:#cfe2f3; font-size:.72rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
    .cover-brief dd { margin:3px 0 0; color:white; font-weight:650; }
    .contents h2, .basis-page h2, .report-section h2 { margin-top:0; color:var(--navy); font-size:2rem; letter-spacing:-.02em; }
    .contents-frontmatter, .contents ol { display:grid; gap:9px; padding:0; list-style:none; }
    .contents a {
      display:grid;
      grid-template-columns:86px 1fr;
      gap:18px;
      padding:11px 0;
      border-bottom:1px solid var(--line);
      color:var(--ink);
      text-decoration:none;
    }
    .contents-number, .contents-frontmatter span, .section-kicker {
      color:var(--blue);
      font-size:.75rem;
      font-weight:850;
      letter-spacing:.08em;
      text-transform:uppercase;
    }
    .section-kicker { display:block; margin-bottom:10px; }
    .report-section h3, .basis-page h3 { margin-top:28px; color:var(--navy); }
    .basis-report-letter { margin:0 0 24px; padding:18px 20px; border:1px solid #dbeafe; border-radius:14px; background:linear-gradient(135deg, #f8fbff, #ffffff); }
    .basis-report-letter h3 { margin-top:0; }
    .report a { overflow-wrap:anywhere; }
    .report-table { margin:18px 0 26px; font-size:.9rem; }
    .report-table caption {
      caption-side:top;
      margin:0 0 8px;
      color:var(--muted);
      font-size:.72rem;
      font-weight:850;
      letter-spacing:.08em;
      text-align:left;
      text-transform:uppercase;
    }
    .report-table th { color:var(--navy); font-size:.75rem; letter-spacing:.06em; text-transform:uppercase; }
    .section-sources .report-table td,
    .section-comparable-evidence .report-table td { overflow-wrap:anywhere; word-break:break-word; }
    .report-card, .callout, .info-card {
      margin:18px 0;
      padding:16px 18px;
      border:1px solid var(--line);
      border-radius:14px;
      background:#f8fbff;
    }
    @media print {
      body { background:white; }
      .viewer-toolbar { display:none; }
      .report { width:100%; margin:0; }
      .cover, .report-page { box-shadow:none; page-break-after:always; }
    }
    """


def _demo_banner_html(*, demo_mode: bool) -> str:
    if not demo_mode:
        return ""
    return """
    <aside class="demo-banner" role="note">
      <strong>Demo data - not for reliance.</strong>
      Research, financial figures and valuation conclusions in this report are simulated
      to demonstrate the AccountIQ experience.
    </aside>
    """


def render_sample_html(
    *,
    company_name: str = DEFAULT_COMPANY_NAME,
    prepared_at: str = DEFAULT_PREPARED_AT,
    valuation_purpose: str = DEFAULT_PURPOSE,
    report_id: int = 9001,
    demo_mode: bool = True,
    pdf_href: str = DEFAULT_PDF_HREF,
    run_content_audit: bool = True,
) -> str:
    """Render the deterministic sample valuation browser report HTML."""
    sections = sample_report_content(demo_mode=demo_mode, run_audit=run_content_audit)
    section_order = SECTION_SCHEMAS["valuation_advisory"]
    report_label = (
        "Demo Indicative Valuation Report"
        if demo_mode
        else "Indicative Valuation Report"
    )
    cover_kicker = (
        "Demo data - not for reliance"
        if demo_mode
        else "Confidential - indicative only"
    )

    contents_html = _render_report_contents_html(sections, section_order)
    basis_html = _render_valuation_basis_html(
        company_name=company_name,
        report_label=report_label,
        report_id=report_id,
        demo_mode=demo_mode,
        valuation_purpose=valuation_purpose,
        generated_at=prepared_at,
        intake_answers=DEFAULT_INTAKE_ANSWERS,
    )
    section_html = _render_report_sections_html(sections, section_order)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_lib.escape(report_label)} - {html_lib.escape(company_name)}</title>
<style>
{_viewer_styles()}
</style>
</head>
<body>
  <nav class="viewer-toolbar" aria-label="Report actions">
    <a href="/wizard">← Back to wizard</a>
    <span>{html_lib.escape(report_label)} · {html_lib.escape(company_name)}</span>
    <div class="viewer-toolbar-actions">
      <a class="viewer-download" href="{html_lib.escape(pdf_href, quote=True)}">Download PDF</a>
    </div>
  </nav>
  <main class="report">
    {_demo_banner_html(demo_mode=demo_mode)}
    <section class="cover">
      <div class="brand">AccountIQ</div>
      {_render_cover_report_basis_html()}
      {_render_cover_valuation_snapshot_html(sections)}
      <div class="cover-copy">
        <span class="cover-kicker">{html_lib.escape(cover_kicker)}</span>
        <h1>{html_lib.escape(report_label)}</h1>
        <p class="company">{html_lib.escape(company_name)}</p>
        {_render_cover_report_brief_html(
            company_name=company_name,
            report_label=report_label,
            report_id=report_id,
            generated_at=prepared_at,
            valuation_purpose=valuation_purpose,
            demo_mode=demo_mode,
        )}
      </div>
    </section>
    <section class="report-page contents">
      <h2>Contents</h2>
      <div class="contents-frontmatter">
        <a href="#basis-of-preparation"><span>Front matter</span>Report letter and basis of preparation</a>
      </div>
      <ol>
        {contents_html}
      </ol>
    </section>
    {basis_html}
    {section_html}
  </main>
</body>
</html>
"""


def audit_generated_html(path: Path, *, demo_mode: bool) -> object:
    """Audit a generated sample HTML file and raise if it misses report markers."""
    audit = audit_valuation_report_html(path.read_text(encoding="utf-8"), demo_mode=demo_mode)
    _raise_if_audit_failed(audit)
    return audit


def generate_sample_html(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    company_name: str = DEFAULT_COMPANY_NAME,
    prepared_at: str = DEFAULT_PREPARED_AT,
    valuation_purpose: str = DEFAULT_PURPOSE,
    report_id: int = 9001,
    demo_mode: bool = True,
    pdf_href: str = DEFAULT_PDF_HREF,
    run_audit: bool = True,
) -> Path:
    """Generate the deterministic sample valuation browser HTML and return its path."""
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_sample_html(
            company_name=company_name,
            prepared_at=prepared_at,
            valuation_purpose=valuation_purpose,
            report_id=report_id,
            demo_mode=demo_mode,
            pdf_href=pdf_href,
            run_content_audit=run_audit,
        ),
        encoding="utf-8",
    )
    if run_audit:
        audit_generated_html(output_path, demo_mode=demo_mode)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the AccountIQ sample indicative valuation browser HTML.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output HTML path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument("--company-name", default=DEFAULT_COMPANY_NAME)
    parser.add_argument("--prepared-at", default=DEFAULT_PREPARED_AT)
    parser.add_argument("--valuation-purpose", default=DEFAULT_PURPOSE)
    parser.add_argument("--report-id", type=int, default=9001)
    parser.add_argument("--pdf-href", default=DEFAULT_PDF_HREF)
    parser.add_argument(
        "--live-label",
        action="store_true",
        help="Use non-demo labelling while still using deterministic sample content.",
    )
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="Write the HTML without running the professional-pack HTML audit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    demo_mode = not args.live_label
    output_path = generate_sample_html(
        args.output,
        company_name=args.company_name,
        prepared_at=args.prepared_at,
        valuation_purpose=args.valuation_purpose,
        report_id=args.report_id,
        demo_mode=demo_mode,
        pdf_href=args.pdf_href,
        run_audit=not args.skip_audit,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
