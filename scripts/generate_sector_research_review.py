"""Generate a readable local review page for the AccountIQ sector library."""

from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = ROOT / "sector_reports"
OUTPUT_PATH = ROOT / "output" / "html" / "sector-research-library-review.html"
QUARTERLY_DIR = LIBRARY_DIR / "quarterly"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def paragraph_text(value: object) -> str:
    return "".join(
        f"<p>{esc(paragraph.strip())}</p>"
        for paragraph in str(value or "").split("\n\n")
        if paragraph.strip()
    )


def bullet_list(values: object) -> str:
    items = values if isinstance(values, list) else []
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def labelled_list(title: str, values: object) -> str:
    return (
        f'<section class="detail-card"><h4>{esc(title)}</h4>'
        f"{bullet_list(values)}</section>"
    )


def display_measure(value: object, unit: object) -> str:
    number = float(value or 0)
    unit_text = str(unit or "")
    if unit_text == "%":
        return f"{number:.1f}%"
    if unit_text == "% q/q":
        return f"{number:+.1f}% q/q"
    if unit_text in {"people", "services", "children"}:
        return f"{number:,.0f} {unit_text}"
    return f"{number:,.1f} {unit_text}".strip()


def line_chart(chart: dict) -> str:
    series_list = [
        series for series in chart.get("series", [])
        if isinstance(series, dict) and len(series.get("values", [])) >= 2
    ]
    all_values = [
        float(point["value"])
        for series in series_list
        for point in series["values"]
    ]
    if not all_values:
        return ""
    width, height = 720, 260
    left, right, top, bottom = 66, 20, 18, 44
    low, high = min(all_values), max(all_values)
    all_nonnegative = low >= 0
    all_nonpositive = high <= 0
    if all_nonnegative:
        low = 0
    if all_nonpositive:
        high = 0
    padding = (high - low or 1) * .08
    if not all_nonnegative:
        low -= padding
    if not all_nonpositive:
        high += padding
    span = high - low
    colours = ("#287f78", "#b57420", "#245c9b", "#7c3aed")

    def xy(index: int, count: int, value: float) -> tuple[float, float]:
        return (
            left + (width - left - right) * index / max(count - 1, 1),
            top + (high - value) / span * (height - top - bottom),
        )

    grid = []
    for index in range(5):
        ratio = index / 4
        y_value = top + ratio * (height - top - bottom)
        label_value = high - ratio * span
        label = f"{label_value / 1000:,.0f}k" if abs(label_value) >= 1000 else f"{label_value:,.1f}"
        grid.append(
            f'<line x1="{left}" y1="{y_value:.1f}" x2="{width-right}" y2="{y_value:.1f}" stroke="#dfe5ec"/>'
            f'<text x="{left-8}" y="{y_value+4:.1f}" text-anchor="end">{esc(label)}</text>'
        )
    paths, legends = [], []
    periods = []
    for series_index, series in enumerate(series_list):
        values = series["values"]
        if not periods:
            periods = [str(point["period"]) for point in values]
        colour = colours[series_index % len(colours)]
        points = [xy(index, len(values), float(point["value"])) for index, point in enumerate(values)]
        paths.append(
            f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}" '
            f'fill="none" stroke="{colour}" stroke-width="3"/>'
            + "".join(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{colour}" stroke="white" stroke-width="1.5"/>'
                for x, y in points
            )
        )
        legends.append(
            f'<span><i style="background:{colour}"></i>{esc(series.get("name"))}</span>'
        )
    x_labels = []
    for index, period in enumerate(periods):
        if len(periods) > 8 and index not in {0, len(periods) - 1} and index % 2:
            continue
        x_value, _ = xy(index, len(periods), 0)
        x_labels.append(
            f'<text x="{x_value:.1f}" y="{height-bottom+22}" text-anchor="middle">{esc(period)}</text>'
        )
    source_labels = {
        "stats_nz_cpi": "Stats NZ",
        "stats_nz_gdp": "Stats NZ",
        "stats_nz_migration": "Stats NZ",
        "stats_nz_bfd": "Stats NZ Business Financial Data",
        "rbnz_ocr": "Reserve Bank of New Zealand",
    }
    sources = list(
        dict.fromkeys(
            source_labels.get(str(source_id), str(source_id))
            for source_id in chart.get("source_ids", [])
        )
    )
    source_text = f"Source: {', '.join(sources)}. " if sources else ""
    return f"""
      <figure class="review-chart">
        <figcaption><strong>{esc(chart.get("title"))}</strong><span>{esc(chart.get("subtitle"))}</span></figcaption>
        <div class="chart-legend">{"".join(legends)}</div>
        <svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(chart.get("title"))}">
          {"".join(grid)}{"".join(paths)}{"".join(x_labels)}
        </svg>
        <p>{esc(source_text)}Unit: {esc(chart.get("unit"))}. {esc(chart.get("note"))}</p>
      </figure>
    """


def quarterly_overview(snapshot: dict) -> str:
    indicators = "".join(
        f"""
        <article class="macro-card">
          <span>{esc(item.get("label"))}</span>
          <strong>{esc(display_measure(item.get("value"), item.get("unit")))}</strong>
          <small>{esc(item.get("period"))}</small>
          <p>{esc(item.get("commentary"))}</p>
        </article>
        """
        for item in snapshot.get("macro_indicators", [])
    )
    charts = "".join(line_chart(chart) for chart in snapshot.get("charts", []))
    economy = snapshot["economy_summary"]
    return f"""
    <section class="quarterly-overview">
      <div class="quarterly-heading">
        <span class="eyebrow">Quarterly intelligence · {esc(snapshot.get("quarter"))}</span>
        <h2>New Zealand economy and market dynamics</h2>
        <p>{esc(economy.get("headline"))}</p>
      </div>
      <div class="macro-grid">{indicators}</div>
      <div class="economy-grid">
        <article><h3>Current setting</h3>{paragraph_text(economy.get("narrative"))}</article>
        <article><h3>Valuation lens</h3>{paragraph_text(economy.get("valuation_implications"))}</article>
        <article><h3>Credit lens</h3>{paragraph_text(economy.get("credit_implications"))}</article>
      </div>
      <div class="chart-grid">{charts}</div>
      <div class="quarterly-boundary"><strong>Measure boundary:</strong> {esc(snapshot.get("usage_boundary"))}</div>
    </section>
    """


def sector_scale_section(report: dict, snapshot: dict) -> str:
    measure = snapshot["sector_scale"][report["sector_id"]]
    if measure.get("measure_kind") == "structural_scale":
        metric_cards = "".join(
            f'<article><span>{esc(metric.get("label"))}</span><strong>{esc(display_measure(metric.get("value"), metric.get("unit")))}</strong></article>'
            for metric in measure.get("metrics", [])
        )
        visual = f'<div class="scale-metrics">{metric_cards}</div>'
    else:
        annual_change = float(measure.get("annual_change_pct") or 0)
        visual = f"""
          <div class="scale-metrics">
            <article><span>Four-quarter nominal sales proxy</span><strong>NZ${float(measure["rolling_four_quarter_nzd_m"]) / 1000:,.1f}bn</strong></article>
            <article><span>Change vs prior four quarters</span><strong>{annual_change:+.1f}%</strong></article>
            <article><span>Latest seasonally adjusted quarter</span><strong>NZ${float(measure["latest_quarter_nzd_m"]) / 1000:,.1f}bn</strong></article>
          </div>
          {line_chart({
              "title": f"{measure['boundary_label']} quarterly sales",
              "subtitle": "Seasonally adjusted current-price sales; a broad sector turnover proxy.",
              "unit": "NZD millions",
              "source_ids": ["stats_nz_bfd"],
              "series": [{"name": "Quarterly sales", "values": measure["series"]}],
              "note": measure["limitations"],
          })}
        """
    return f"""
      <section class="review-section" id="{esc(report['sector_id'])}-scale">
        <div class="section-heading">
          <span class="eyebrow">Quarterly sector scale</span>
          <h3>{esc(measure.get("boundary_label"))}</h3>
        </div>
        {visual}
        <div class="scale-notes">
          <p><strong>Interpretation:</strong> {esc(measure.get("interpretation"))}</p>
          <p><strong>Boundary:</strong> {esc(measure.get("limitations"))}</p>
          <p><strong>Reference period:</strong> {esc(measure.get("latest_period"))} · snapshot {esc(snapshot.get("as_of_date"))}</p>
        </div>
      </section>
    """


def overview_section(report: dict) -> str:
    overview = report["overview"]
    return f"""
      <section class="review-section" id="{esc(report['sector_id'])}-overview">
        <div class="section-heading">
          <span class="eyebrow">Sector foundation</span>
          <h3>Overview and operating model</h3>
        </div>
        <div class="lead-copy">{paragraph_text(overview.get("summary"))}</div>
        <div class="detail-grid">
          {labelled_list("Common business models", overview.get("business_models"))}
          {labelled_list("Industry structure", overview.get("industry_structure"))}
          {labelled_list("Demand drivers", overview.get("demand_drivers"))}
          {labelled_list("Margin and cost drivers", overview.get("margin_and_cost_drivers"))}
          {labelled_list("Cyclicality and seasonality", overview.get("cyclicality_and_seasonality"))}
          {labelled_list("Regulatory and compliance", overview.get("regulatory_and_compliance"))}
        </div>
        <div class="two-column">
          <article class="prose-card">
            <h4>Working-capital profile</h4>
            {paragraph_text(overview.get("working_capital_profile"))}
          </article>
          <article class="prose-card">
            <h4>Asset intensity</h4>
            {paragraph_text(overview.get("asset_intensity"))}
          </article>
        </div>
      </section>
    """


def subsector_section(report: dict) -> str:
    cards = []
    for item in report.get("subsectors", []):
        cards.append(
            f"""
            <article class="subsector-card">
              <div class="subsector-title">
                <span class="tag">{esc(item.get("id"))}</span>
                <h4>{esc(item.get("name"))}</h4>
              </div>
              <p>{esc(item.get("business_model"))}</p>
              <dl>
                <dt>Revenue drivers</dt><dd>{esc(" · ".join(item.get("revenue_drivers", [])))}</dd>
                <dt>Cost base</dt><dd>{esc(" · ".join(item.get("cost_base", [])))}</dd>
                <dt>Working capital</dt><dd>{esc(item.get("working_capital"))}</dd>
                <dt>Asset intensity</dt><dd>{esc(item.get("asset_intensity"))}</dd>
              </dl>
              <div class="watch-grid">
                <div><strong>Credit watchpoints</strong>{bullet_list(item.get("credit_watchpoints"))}</div>
                <div><strong>Valuation watchpoints</strong>{bullet_list(item.get("valuation_watchpoints"))}</div>
              </div>
            </article>
            """
        )
    return f"""
      <section class="review-section" id="{esc(report['sector_id'])}-subsectors">
        <div class="section-heading">
          <span class="eyebrow">Business-model differences</span>
          <h3>Sub-sectors</h3>
        </div>
        <div class="subsector-grid">{"".join(cards)}</div>
      </section>
    """


def credit_section(report: dict) -> str:
    credit = report["credit_analysis"]
    risk_rows = []
    for item in credit.get("primary_risks", []):
        risk_rows.append(
            f"""
            <tr>
              <th>{esc(item.get("risk"))}</th>
              <td>{esc(item.get("mechanism"))}</td>
              <td>{esc(" · ".join(item.get("financial_signals", [])))}</td>
              <td>{esc(" · ".join(item.get("mitigants", [])))}</td>
            </tr>
            """
        )
    return f"""
      <section class="review-section" id="{esc(report['sector_id'])}-credit">
        <div class="section-heading">
          <span class="eyebrow">Bank credit paper</span>
          <h3>Credit analysis framework</h3>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Risk</th><th>How it affects the borrower</th><th>Financial signals</th><th>Potential mitigants to verify</th></tr></thead>
            <tbody>{"".join(risk_rows)}</tbody>
          </table>
        </div>
        <div class="detail-grid">
          {labelled_list("Cash conversion and working capital", credit.get("cash_conversion_and_working_capital"))}
          {labelled_list("Collateral considerations", credit.get("collateral_considerations"))}
          {labelled_list("Downside stresses", credit.get("downside_stresses"))}
          {labelled_list("Monitoring KPIs", credit.get("monitoring_kpis"))}
          {labelled_list("Covenant considerations", credit.get("covenant_considerations"))}
          {labelled_list("Diligence questions", credit.get("diligence_questions"))}
        </div>
      </section>
    """


def valuation_section(report: dict) -> str:
    valuation = report["valuation_analysis"]
    return f"""
      <section class="review-section" id="{esc(report['sector_id'])}-valuation">
        <div class="section-heading">
          <span class="eyebrow">Business valuation report</span>
          <h3>Valuation analysis framework</h3>
        </div>
        <div class="detail-grid">
          {labelled_list("Value drivers", valuation.get("value_drivers"))}
          {labelled_list("Multiple influences", valuation.get("multiple_influences"))}
          {labelled_list("Normalisation focus", valuation.get("normalisation_focus"))}
          {labelled_list("Peer selection", valuation.get("peer_selection"))}
          {labelled_list("Preferred metrics", valuation.get("preferred_metrics"))}
          {labelled_list("Discount and premium factors", valuation.get("discount_and_premium_factors"))}
          {labelled_list("Diligence questions", valuation.get("diligence_questions"))}
        </div>
      </section>
    """


def market_section(report: dict) -> str:
    market = report["market_research_sections"]
    return f"""
      <section class="review-section" id="{esc(report['sector_id'])}-market">
        <div class="section-heading">
          <span class="eyebrow">Draft report content</span>
          <h3>Market-research narratives</h3>
        </div>
        <div class="market-grid">
          <article class="market-card credit">
            <span class="document-label">Bank credit paper</span>
            {paragraph_text(market.get("credit_paper"))}
          </article>
          <article class="market-card valuation">
            <span class="document-label">Business valuation report</span>
            {paragraph_text(market.get("valuation_report"))}
          </article>
        </div>
      </section>
    """


def sources_section(report: dict) -> str:
    rows = []
    for source in report.get("sources", []):
        published = source.get("published_date") or "Living source"
        rows.append(
            f"""
            <tr>
              <th>{esc(source.get("title"))}<small>{esc(source.get("publisher"))}</small></th>
              <td>{esc(published)}</td>
              <td>{esc(" · ".join(source.get("supports", [])))}</td>
              <td><a href="{esc(source.get("url"))}" target="_blank" rel="noreferrer">Open source ↗</a></td>
            </tr>
            """
        )
    return f"""
      <section class="review-section" id="{esc(report['sector_id'])}-sources">
        <div class="section-heading">
          <span class="eyebrow">Evidence and safeguards</span>
          <h3>Sources and limitations</h3>
        </div>
        <div class="table-wrap">
          <table class="sources-table">
            <thead><tr><th>Source</th><th>Published</th><th>Used to support</th><th>Link</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
          </table>
        </div>
        <article class="limitations">
          <h4>Limitations the report must retain</h4>
          {bullet_list(report.get("limitations"))}
        </article>
      </section>
    """


def sector_panel(report: dict, position: int, snapshot: dict) -> str:
    return f"""
      <article class="sector-panel{" active" if position == 0 else ""}" data-sector="{esc(report['sector_id'])}">
        <header class="sector-hero">
          <div>
            <span class="eyebrow">AccountIQ sector pack</span>
            <h2>{esc(report['sector_name'])}</h2>
            <p>New Zealand · reviewed {esc(report['as_of_date'])} · next review {esc(report['next_review_date'])}</p>
          </div>
          <nav class="section-nav" aria-label="{esc(report['sector_name'])} sections">
            <a href="#{esc(report['sector_id'])}-overview">Overview</a>
            <a href="#{esc(report['sector_id'])}-scale">Sector scale</a>
            <a href="#{esc(report['sector_id'])}-subsectors">Sub-sectors</a>
            <a href="#{esc(report['sector_id'])}-credit">Credit</a>
            <a href="#{esc(report['sector_id'])}-valuation">Valuation</a>
            <a href="#{esc(report['sector_id'])}-market">Draft narratives</a>
            <a href="#{esc(report['sector_id'])}-sources">Sources</a>
          </nav>
        </header>
        {sector_scale_section(report, snapshot)}
        {overview_section(report)}
        {subsector_section(report)}
        {credit_section(report)}
        {valuation_section(report)}
        {market_section(report)}
        {sources_section(report)}
      </article>
    """


def generate() -> Path:
    index = json.loads((LIBRARY_DIR / "index.json").read_text(encoding="utf-8"))
    reports = [
        json.loads((LIBRARY_DIR / item["file"]).read_text(encoding="utf-8"))
        for item in index["sectors"]
    ]
    quarterly_index = json.loads((QUARTERLY_DIR / "index.json").read_text(encoding="utf-8"))
    snapshot = json.loads(
        (QUARTERLY_DIR / quarterly_index["current_snapshot"]).read_text(encoding="utf-8")
    )
    buttons = "".join(
        f'<button class="sector-button{" active" if index == 0 else ""}" '
        f'data-target="{esc(report["sector_id"])}">'
        f'<span>{index + 1:02d}</span>{esc(report["sector_name"])}</button>'
        for index, report in enumerate(reports)
    )
    panels = "".join(
        sector_panel(report, index, snapshot)
        for index, report in enumerate(reports)
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AccountIQ Sector Research Library — Review</title>
  <style>
    :root {{
      --navy: #14253d;
      --navy-2: #1e3655;
      --ink: #223047;
      --muted: #637083;
      --paper: #f4f2ec;
      --white: #ffffff;
      --line: #d9dee5;
      --gold: #b88b43;
      --teal: #2b7773;
      --credit: #e8f3f2;
      --valuation: #f4ede0;
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ margin: 0; background: var(--paper); }}
    a {{ color: var(--teal); }}
    .library-hero {{
      color: white;
      background:
        radial-gradient(circle at 82% 15%, rgba(184,139,67,.28), transparent 25rem),
        linear-gradient(135deg, var(--navy), #0c192a);
      padding: 52px max(28px, calc((100vw - 1420px) / 2));
    }}
    .library-hero .eyebrow {{ color: #dfc08b; }}
    .library-hero h1 {{ max-width: 850px; margin: 10px 0 14px; font: 700 clamp(34px, 5vw, 62px)/1.05 Georgia, serif; }}
    .library-hero p {{ max-width: 850px; color: #d7e0ea; font-size: 18px; line-height: 1.65; }}
    .hero-stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }}
    .hero-stats span {{ padding: 10px 14px; border: 1px solid rgba(255,255,255,.2); border-radius: 999px; background: rgba(255,255,255,.06); }}
    .boundary {{
      margin-top: 26px; padding: 18px 20px; max-width: 1040px;
      border-left: 4px solid var(--gold); background: rgba(255,255,255,.08);
      color: #edf2f7; line-height: 1.55;
    }}
    .quarterly-overview {{ max-width: 1500px; margin: 0 auto; padding: 48px 32px 56px; }}
    .quarterly-heading {{ max-width: 980px; }}
    .quarterly-heading h2 {{ margin: 7px 0 12px; color: var(--navy); font: 700 38px/1.15 Georgia, serif; }}
    .quarterly-heading > p {{ color: var(--muted); font-size: 18px; line-height: 1.55; }}
    .macro-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; margin: 28px 0; }}
    .macro-card {{ padding: 18px; border: 1px solid var(--line); border-radius: 12px; background: white; }}
    .macro-card > span {{ display: block; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; }}
    .macro-card > strong {{ display: block; margin: 7px 0 3px; color: var(--navy); font: 700 27px/1 Georgia, serif; }}
    .macro-card small {{ color: var(--teal); font-weight: 700; }}
    .macro-card p {{ margin: 10px 0 0; color: var(--muted); font-size: 13px; line-height: 1.45; }}
    .economy-grid {{ display: grid; grid-template-columns: 1.3fr 1fr 1fr; gap: 14px; }}
    .economy-grid article {{ padding: 22px; border: 1px solid var(--line); border-radius: 12px; background: white; line-height: 1.65; }}
    .economy-grid h3 {{ margin: 0 0 10px; color: var(--navy); font-size: 16px; }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 14px; }}
    .review-chart {{ margin: 0; padding: 18px; border: 1px solid var(--line); border-radius: 12px; background: white; break-inside: avoid; }}
    .review-chart figcaption strong {{ display: block; color: var(--navy); }}
    .review-chart figcaption span {{ display: block; margin-top: 4px; color: var(--muted); font-size: 13px; }}
    .review-chart svg {{ width: 100%; height: auto; margin-top: 8px; overflow: visible; }}
    .review-chart svg text {{ fill: var(--muted); font-size: 10px; }}
    .review-chart > p {{ margin: 2px 0 0; color: var(--muted); font-size: 11px; line-height: 1.4; }}
    .chart-legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 10px 0 0; color: var(--muted); font-size: 12px; }}
    .chart-legend span {{ display: inline-flex; align-items: center; gap: 5px; }}
    .chart-legend i {{ width: 16px; height: 3px; border-radius: 999px; }}
    .quarterly-boundary, .scale-notes {{ margin-top: 14px; padding: 16px 18px; border-left: 4px solid var(--gold); background: #fffaf1; line-height: 1.55; }}
    .scale-metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; margin-bottom: 14px; }}
    .scale-metrics article {{ padding: 18px; border: 1px solid var(--line); border-radius: 12px; background: white; }}
    .scale-metrics span {{ display: block; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }}
    .scale-metrics strong {{ display: block; margin-top: 8px; color: var(--navy); font: 700 25px/1 Georgia, serif; }}
    .scale-notes p {{ margin: 5px 0; }}
    .shell {{ display: grid; grid-template-columns: 260px minmax(0, 1fr); max-width: 1500px; margin: 0 auto; }}
    .sector-sidebar {{
      position: sticky; top: 0; height: 100vh; padding: 26px 16px;
      border-right: 1px solid var(--line); background: #ece9e2; overflow-y: auto;
    }}
    .sidebar-title {{ margin: 0 8px 16px; color: var(--muted); font-size: 12px; letter-spacing: .13em; text-transform: uppercase; }}
    .sector-button {{
      width: 100%; display: flex; align-items: center; gap: 12px; margin: 4px 0; padding: 12px;
      border: 0; border-radius: 9px; color: var(--ink); background: transparent; text-align: left;
      font: inherit; font-weight: 650; cursor: pointer;
    }}
    .sector-button span {{ color: var(--gold); font-size: 12px; }}
    .sector-button:hover {{ background: rgba(255,255,255,.7); }}
    .sector-button.active {{ color: white; background: var(--navy); box-shadow: 0 8px 24px rgba(20,37,61,.18); }}
    .content {{ min-width: 0; padding: 0 32px 80px; }}
    .sector-panel {{ display: none; }}
    .sector-panel.active {{ display: block; }}
    .sector-hero {{
      position: sticky; top: 0; z-index: 5; display: flex; justify-content: space-between; gap: 24px;
      padding: 26px 0 20px; background: rgba(244,242,236,.96); backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line);
    }}
    .eyebrow {{ color: var(--teal); font-size: 11px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }}
    .sector-hero h2 {{ margin: 5px 0; color: var(--navy); font: 700 34px/1.1 Georgia, serif; }}
    .sector-hero p {{ margin: 0; color: var(--muted); }}
    .section-nav {{ display: flex; flex-wrap: wrap; justify-content: flex-end; align-content: center; gap: 7px; max-width: 640px; }}
    .section-nav a {{ padding: 7px 10px; border: 1px solid var(--line); border-radius: 999px; color: var(--ink); background: white; font-size: 12px; text-decoration: none; }}
    .review-section {{ scroll-margin-top: 130px; padding: 44px 0 8px; }}
    .section-heading {{ margin-bottom: 22px; }}
    .section-heading h3 {{ margin: 5px 0 0; color: var(--navy); font: 700 28px/1.2 Georgia, serif; }}
    .lead-copy {{ max-width: 1060px; font-size: 17px; line-height: 1.75; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .detail-card, .prose-card, .subsector-card, .market-card, .limitations {{
      border: 1px solid var(--line); border-radius: 12px; background: white; box-shadow: 0 5px 18px rgba(20,37,61,.04);
    }}
    .detail-card {{ padding: 19px; }}
    h4 {{ margin: 0 0 12px; color: var(--navy); font-size: 16px; }}
    ul {{ margin: 0; padding-left: 19px; }}
    li {{ margin: 7px 0; line-height: 1.5; }}
    .two-column {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }}
    .prose-card {{ padding: 22px; line-height: 1.65; }}
    .subsector-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .subsector-card {{ padding: 22px; }}
    .subsector-card > p {{ color: var(--muted); line-height: 1.6; }}
    .subsector-title {{ display: flex; gap: 10px; align-items: center; }}
    .tag {{ padding: 5px 8px; border-radius: 5px; color: var(--teal); background: var(--credit); font: 700 10px/1 monospace; }}
    dl {{ margin: 18px 0; }}
    dt {{ margin-top: 10px; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }}
    dd {{ margin: 3px 0 0; line-height: 1.5; }}
    .watch-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; padding-top: 14px; border-top: 1px solid var(--line); }}
    .watch-grid strong {{ font-size: 12px; color: var(--navy); }}
    .watch-grid ul {{ margin-top: 8px; font-size: 13px; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: white; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 880px; }}
    th, td {{ padding: 14px 16px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; line-height: 1.5; }}
    thead th {{ color: white; background: var(--navy); font-size: 12px; letter-spacing: .04em; }}
    tbody th {{ width: 18%; color: var(--navy); }}
    tbody td {{ font-size: 14px; }}
    tbody tr:last-child th, tbody tr:last-child td {{ border-bottom: 0; }}
    .sources-table th small {{ display: block; margin-top: 4px; color: var(--muted); font-weight: 500; }}
    .market-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .market-card {{ padding: 25px; font-size: 15px; line-height: 1.72; }}
    .market-card.credit {{ background: var(--credit); }}
    .market-card.valuation {{ background: var(--valuation); }}
    .document-label {{ display: inline-block; margin-bottom: 10px; color: var(--navy); font-size: 11px; font-weight: 850; letter-spacing: .12em; text-transform: uppercase; }}
    .limitations {{ padding: 22px; border-left: 5px solid var(--gold); }}
    @media (max-width: 1050px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .sector-sidebar {{ position: static; height: auto; display: flex; gap: 7px; overflow-x: auto; border-right: 0; border-bottom: 1px solid var(--line); }}
      .sidebar-title {{ display: none; }}
      .sector-button {{ min-width: 190px; }}
      .sector-hero {{ position: static; display: block; }}
      .section-nav {{ justify-content: flex-start; margin-top: 18px; }}
      .detail-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .macro-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .economy-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      .content {{ padding: 0 18px 60px; }}
      .quarterly-overview {{ padding: 38px 18px; }}
      .detail-grid, .two-column, .subsector-grid, .market-grid, .macro-grid, .chart-grid, .scale-metrics {{ grid-template-columns: 1fr; }}
      .watch-grid {{ grid-template-columns: 1fr; }}
    }}
    @media print {{
      .sector-sidebar, .section-nav {{ display: none; }}
      .shell {{ display: block; }}
      .content {{ padding: 0; }}
      .sector-panel {{ display: block; page-break-before: always; }}
      .sector-hero {{ position: static; }}
      .review-section {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <header class="library-hero">
    <span class="eyebrow">Review edition · {esc(index["updated_date"])}</span>
    <h1>AccountIQ New Zealand Sector Research Library</h1>
    <p>Review the generic market context that AccountIQ can add to a bank credit paper or business valuation report after matching the subject company's sector and description.</p>
    <div class="hero-stats">
      <span>{len(reports)} sector packs</span>
      <span>{sum(len(report.get("subsectors", [])) for report in reports)} sub-sectors</span>
      <span>{sum(len(report.get("sources", [])) for report in reports)} primary sources</span>
      <span>Credit + valuation narratives</span>
    </div>
    <div class="boundary"><strong>Evidence boundary:</strong> these are generic New Zealand baselines. They guide research, questions and report commentary, but they do not establish facts about the subject company or provide current market multiples, a company-specific beta, funding cost, asset value or credit approval.</div>
  </header>
  {quarterly_overview(snapshot)}
  <main class="shell">
    <aside class="sector-sidebar">
      <p class="sidebar-title">Choose a sector</p>
      {buttons}
    </aside>
    <div class="content">{panels}</div>
  </main>
  <script>
    const buttons = [...document.querySelectorAll(".sector-button")];
    const panels = [...document.querySelectorAll(".sector-panel")];
    function selectSector(id) {{
      buttons.forEach(button => button.classList.toggle("active", button.dataset.target === id));
      panels.forEach(panel => panel.classList.toggle("active", panel.dataset.sector === id));
      history.replaceState(null, "", `#sector=${{id}}`);
      window.scrollTo({{ top: document.querySelector(".library-hero").offsetHeight, behavior: "smooth" }});
    }}
    buttons.forEach(button => button.addEventListener("click", () => selectSector(button.dataset.target)));
    const requested = location.hash.startsWith("#sector=") ? location.hash.replace("#sector=", "") : "";
    if (requested && panels.some(panel => panel.dataset.sector === requested)) {{
      selectSector(requested);
    }}
  </script>
</body>
</html>
"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(document, encoding="utf-8")
    return OUTPUT_PATH


if __name__ == "__main__":
    print(generate())
