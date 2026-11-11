"""Professional PDF rendering for approved AccountIQ reports."""
from __future__ import annotations

import html
import math
import os
import re
import tempfile
from pathlib import Path


BRAND_NAVY = "#1B1464"
DISCLAIMER = "Indicative Only - Not Financial Advice"
MARKET_CHART_CSS = """
  .market-line-chart { margin: 1.4rem 0 1.6rem; page-break-inside: avoid; }
  .market-line-chart figcaption strong, .market-line-chart figcaption span { display: block; }
  .market-line-chart figcaption span, .market-line-chart .chart-source { color: #5d6472; font-size: .86em; }
  .market-line-chart svg { display: block; width: 100%; max-width: 560px; height: auto; margin: .5rem 0; }
  .market-line-chart .chart-legend { margin: .4rem 0 0; font-size: .86em; }
  .market-line-chart .chart-legend span { margin-right: 1.2em; white-space: nowrap; }
  .market-line-chart .chart-legend i { display: inline-block; width: 14px; height: 3px; margin-right: 6px; vertical-align: middle; }
"""


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


_MARKET_SOURCE_LABELS = {
    "stats_nz_cpi": "Stats NZ",
    "stats_nz_gdp": "Stats NZ",
    "stats_nz_migration": "Stats NZ",
    "stats_nz_bfd": "Stats NZ Business Financial Data",
    "rbnz_ocr": "Reserve Bank of New Zealand",
}


def _table_html(table_data: dict | None) -> str:
    if not table_data:
        return ""
    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])
    if not isinstance(headers, list) or not isinstance(rows, list):
        return ""
    header_html = "".join(f"<th>{html.escape(str(cell))}</th>" for cell in headers)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
        if isinstance(row, list)
    )
    if not header_html and not rows_html:
        return ""
    return (
        "<table><thead><tr>"
        + header_html
        + "</tr></thead><tbody>"
        + rows_html
        + "</tbody></table>"
    )


_CHART_COLOURS = ("#1B1464", "#c2410c", "#0f766e", "#6b7280")


def _nice_ticks(low: float, high: float, count: int = 4) -> list[float]:
    """Round axis ticks (steps of 1, 2 or 5 times a power of ten) covering low to high."""
    raw = ((high - low) or 1) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw)
    first = math.floor(low / step)
    last = math.ceil(high / step)
    return [index * step for index in range(first, last + 1)]


def _chart_series(chart: dict) -> list[tuple[str, list[tuple[str, float]]]]:
    series_list = []
    for series in chart.get("series", []) or []:
        if not isinstance(series, dict):
            continue
        points = []
        for point in series.get("values", []) or []:
            if not isinstance(point, dict):
                continue
            try:
                points.append((str(point.get("period")), float(point.get("value"))))
            except (TypeError, ValueError):
                continue
        series_list.append((str(series.get("name") or "Series"), points))
    return series_list


def _chart_svg(series_list: list[tuple[str, list[tuple[str, float]]]], label: str) -> str:
    values = [value for _, points in series_list for _, value in points]
    longest = max((points for _, points in series_list), key=len, default=[])
    if len(longest) < 2:
        return ""
    width, height, left, right, top, bottom = 440, 220, 48, 52, 14, 28
    ticks = _nice_ticks(min(0.0, *values), max(0.0, *values))
    low, high = ticks[0], ticks[-1]
    plot_w, plot_h = width - left - right, height - top - bottom

    def x_at(index: int) -> float:
        return left + plot_w * index / (len(longest) - 1)

    def y_at(value: float) -> float:
        return top + plot_h * (high - value) / (high - low)

    parts = []
    for tick in ticks:
        y = y_at(tick)
        colour = "#9aa3b2" if tick == 0 else "#e0e4ea"
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="{colour}"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{tick:,.10g}</text>')
    every = math.ceil(len(longest) / 6)
    for index, (period, _) in enumerate(longest):
        if (len(longest) - 1 - index) % every == 0:
            parts.append(
                f'<text x="{x_at(index):.1f}" y="{height - 8}" text-anchor="middle">{html.escape(period)}</text>'
            )
    for number, (_, points) in enumerate(series_list):
        if not points:
            continue
        colour = _CHART_COLOURS[number % len(_CHART_COLOURS)]
        dash = ' stroke-dasharray="6 4"' if number % 2 else ""
        line = " ".join(f"{x_at(i):.1f},{y_at(value):.1f}" for i, (_, value) in enumerate(points))
        parts.append(f'<polyline points="{line}" fill="none" stroke="{colour}" stroke-width="2"{dash}/>')
        end_x, end_y = x_at(len(points) - 1), y_at(points[-1][1])
        parts.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="3" fill="{colour}"/>')
        parts.append(
            f'<text x="{end_x + 7:.1f}" y="{end_y + 4:.1f}" fill="{colour}" font-weight="700">'
            f"{points[-1][1]:,.10g}</text>"
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{label}" '
        'font-family="Arial, sans-serif" font-size="12" fill="#5d6472">' + "".join(parts) + "</svg>"
    )


def market_chart_html(chart: dict) -> str:
    """One market chart as a figure: title, subtitle, legend, line chart and source line."""
    title = html.escape(str(chart.get("title") or "Market trend"))
    subtitle = html.escape(str(chart.get("subtitle") or ""))
    unit = html.escape(str(chart.get("unit") or ""))
    note = html.escape(str(chart.get("note") or ""))
    source_labels = list(
        dict.fromkeys(
            _MARKET_SOURCE_LABELS.get(str(source_id), str(source_id))
            for source_id in chart.get("source_ids", [])
        )
    )
    source_text = html.escape(", ".join(source_labels))
    series_list = _chart_series(chart)
    # The same figures the chart draws, read out for anyone who cannot see it.
    spoken = html.escape(
        "; ".join(
            f"{name}: " + ", ".join(f"{period} {value:,.10g}" for period, value in points)
            for name, points in series_list
        ),
        quote=True,
    )
    legend = "".join(
        f'<span><i style="background:{_CHART_COLOURS[number % len(_CHART_COLOURS)]}"></i>{html.escape(name)}</span>'
        for number, (name, _) in enumerate(series_list)
    )
    return (
        '<figure class="market-line-chart">'
        f"<figcaption><strong>{title}</strong><span>{subtitle}</span></figcaption>"
        f'<p class="chart-legend">{legend}</p>'
        f"{_chart_svg(series_list, f'{title}. {spoken}')}"
        f'<p class="chart-source">Source: {source_text}. Unit: {unit}. {note}</p>'
        "</figure>"
    )


def _market_payload_html(content: dict) -> str:
    chunks = []
    if isinstance(content.get("sector_scale_table"), dict):
        chunks.append("<h3>Sector scale and boundary</h3>")
        chunks.append(_table_html(content["sector_scale_table"]))
    charts = content.get("market_charts")
    if isinstance(charts, list):
        chunks.extend(market_chart_html(chart) for chart in charts if isinstance(chart, dict))
    if isinstance(content.get("market_sources_table"), dict):
        chunks.append("<h3>Market data sources</h3>")
        chunks.append(_table_html(content["market_sources_table"]))
    snapshot = content.get("market_snapshot")
    if isinstance(snapshot, dict) and snapshot.get("usage_boundary"):
        chunks.append(
            f"<p><strong>Market evidence boundary:</strong> "
            f"{html.escape(str(snapshot.get('usage_boundary')))}</p>"
        )
    return "".join(chunks)


_HEADING_ACRONYMS = {
    "wacc": "WACC",
    "dcf": "DCF",
    "ebitda": "EBITDA",
    "ebit": "EBIT",
    "fcff": "FCFF",
    "nwc": "NWC",
    "nz": "NZ",
    "pe": "P/E",
    "ev": "EV",
}


def section_heading(key: str) -> str:
    """Human heading for a section key: title case with finance acronyms kept upper case."""
    words = []
    for word in str(key).replace("_", " ").split():
        lowered = word.lower()
        words.append(_HEADING_ACRONYMS.get(lowered, word.capitalize()))
    return " ".join(words)


def _section_html(key: str, content) -> str:
    heading = html.escape(section_heading(key))
    if isinstance(content, dict):
        narrative = str(content.get("narrative", "") or "")
        table_data = content.get("table") if isinstance(content.get("table"), dict) else None
    else:
        narrative = str(content or "")
        table_data = None

    paragraphs = _narrative_html(narrative)

    table_html = _table_html(table_data)
    market_html = _market_payload_html(content) if isinstance(content, dict) else ""

    section_class = " class=\"disclaimer\"" if key == "disclaimer" else ""
    return f"<section{section_class}><h2>{heading}</h2>{paragraphs}{table_html}{market_html}</section>"


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
  {MARKET_CHART_CSS}
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
