"""Professional PDF rendering for approved AccountIQ reports."""
from __future__ import annotations

import html
import os
import re
import tempfile
from pathlib import Path


BRAND_NAVY = "#1B1464"
DISCLAIMER = "Indicative Only - Not Financial Advice"


def report_pdf_path(export_dir: Path, report_id: int) -> Path:
    return export_dir / f"report-{report_id}.pdf"


def _narrative_html(narrative: str) -> str:
    chunks: list[str] = []
    bullets: list[str] = []

    def inline(value: str) -> str:
        escaped = html.escape(value)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    def flush_bullets() -> None:
        if bullets:
            chunks.append("<ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    for line in narrative.split("\n"):
        value = line.strip()
        if not value:
            flush_bullets()
        elif value.startswith("## "):
            flush_bullets()
            chunks.append(f"<h3>{inline(value[3:].strip())}</h3>")
        elif value.startswith(("- ", "* ")):
            bullets.append(inline(value[2:].strip()))
        else:
            flush_bullets()
            chunks.append(f"<p>{inline(value)}</p>")
    flush_bullets()
    return "".join(chunks)


def _section_html(key: str, content) -> str:
    heading = html.escape(key.replace("_", " ").title())
    if isinstance(content, dict):
        narrative = str(content.get("narrative", "") or "")
        table_data = content.get("table") if isinstance(content.get("table"), dict) else None
    else:
        narrative = str(content or "")
        table_data = None

    paragraphs = _narrative_html(narrative)

    table_html = ""
    if table_data:
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        if isinstance(headers, list) and isinstance(rows, list):
            header_html = "".join(f"<th>{html.escape(str(cell))}</th>" for cell in headers)
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
                for row in rows
                if isinstance(row, list)
            )
            if header_html or rows_html:
                table_html = (
                    "<table><thead><tr>"
                    + header_html
                    + "</tr></thead><tbody>"
                    + rows_html
                    + "</tbody></table>"
                )

    section_class = " class=\"disclaimer\"" if key == "disclaimer" else ""
    return f"<section{section_class}><h2>{heading}</h2>{paragraphs}{table_html}</section>"


def render_report_html(
    company_name: str,
    report_type: str,
    sections: dict,
    generated_at: str | None,
    section_order: list[str] | None = None,
) -> str:
    title = html.escape(report_type.replace("_", " ").title())
    company = html.escape(company_name)
    generated = html.escape(generated_at or "")
    keys = section_order or list(sections.keys())
    report_sections = "".join(_section_html(key, sections.get(key, "")) for key in keys)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} - {company}</title>
<style>
  @page {{
    size: A4;
    margin: 22mm 18mm 24mm;
    @bottom-center {{
      content: "AccountIQ | {DISCLAIMER} | Page " counter(page) " of " counter(pages);
      color: #666;
      font-family: Arial, sans-serif;
      font-size: 8pt;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ color: #1d2433; font-family: Arial, sans-serif; font-size: 10.5pt; line-height: 1.55; }}
  .brand {{ color: {BRAND_NAVY}; font-size: 13pt; font-weight: 700; letter-spacing: 0.04em; }}
  .cover {{ border-top: 8px solid {BRAND_NAVY}; padding-top: 24mm; page-break-after: always; }}
  .cover h1 {{ color: {BRAND_NAVY}; font-size: 28pt; line-height: 1.15; margin: 12mm 0 5mm; }}
  .company {{ font-size: 17pt; margin: 0 0 4mm; }}
  .meta {{ color: #5d6472; }}
  .notice {{ background: #f1f0f8; border-left: 4px solid {BRAND_NAVY}; margin-top: 22mm; padding: 5mm; }}
  h2 {{ color: {BRAND_NAVY}; font-size: 16pt; margin: 10mm 0 3mm; page-break-after: avoid; }}
  h3 {{ color: #34304f; font-size: 12pt; margin: 5mm 0 2mm; page-break-after: avoid; }}
  p {{ margin: 0 0 3.5mm; orphans: 3; widows: 3; }}
  ul {{ margin: 0 0 4mm; padding-left: 6mm; }}
  li {{ margin-bottom: 1.5mm; }}
  section {{ page-break-inside: auto; }}
  table {{ border-collapse: collapse; margin: 4mm 0 7mm; width: 100%; page-break-inside: avoid; }}
  th {{ background: {BRAND_NAVY}; color: white; font-weight: 700; padding: 2.5mm; text-align: left; }}
  td {{ border-bottom: 1px solid #d9dce5; padding: 2.5mm; vertical-align: top; }}
  tbody tr:nth-child(even) {{ background: #f7f7fa; }}
  .disclaimer {{ background: #f7f7fa; border: 1px solid #d9dce5; margin-top: 10mm; padding: 5mm; }}
  .disclaimer h2 {{ margin-top: 0; }}
</style>
</head>
<body>
  <section class="cover">
    <div class="brand">AccountIQ</div>
    <h1>{title}</h1>
    <p class="company">{company}</p>
    <p class="meta">Generated {generated}</p>
    <div class="notice"><strong>{DISCLAIMER}</strong><br>This report should be read with its assumptions, limitations, and disclaimer.</div>
  </section>
  {report_sections}
</body>
</html>"""


def write_pdf(html_text: str, output_path: Path) -> None:
    """Render a PDF atomically so concurrent downloads cannot expose a partial file."""
    from weasyprint import HTML

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}-",
        suffix=".pdf",
        dir=output_path.parent,
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        HTML(string=html_text).write_pdf(str(temporary_path))
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
