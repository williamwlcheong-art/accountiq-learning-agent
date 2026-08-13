"""Professional PDF delivery helpers for AccountIQ reports."""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Flowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from valuation import report_answer_label


NAVY = colors.HexColor("#082B4C")
BLUE = colors.HexColor("#1769AA")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#D7DEE8")
PALE_BLUE = colors.HexColor("#EDF5FC")
WARM = colors.HexColor("#FFF8E8")

VALUATION_RANGE_VISUAL_SUBTITLE = (
    "Low, midpoint and high cases from AccountIQ's valuation schedules."
)
FINANCIAL_TREND_VISUAL_SUBTITLE = (
    "Revenue and EBITDA trend from the uploaded-financials schedule."
)
SENSITIVITY_SPREAD_VISUAL_SUBTITLE = (
    "Downside, base and upside adjusted enterprise value from AccountIQ's sensitivity analysis."
)


_MANAGEMENT_INPUT_TRAIL = [
    (
        "valuation_purpose",
        "Valuation purpose",
        "Frames the report scope, reliance wording and how the valuation conclusion is positioned.",
    ),
    (
        "owner_dependency",
        "Owner or key-person dependency",
        "Informs continuity, handover risk, transition risk and specific-risk commentary.",
    ),
    (
        "customer_concentration",
        "Largest-customer concentration",
        "Informs revenue-retention risk, diligence focus and concentration commentary.",
    ),
    (
        "revenue_quality",
        "Revenue predictability",
        "Informs cash-flow reliability, contract-security commentary and forecast support.",
    ),
    (
        "revenue_outlook",
        "Revenue outlook",
        "Informs the short-term growth assumption or, when no specific forecast is supplied, the decision to derive growth from uploaded financial history.",
    ),
]


class _AccountIQDocTemplate(BaseDocTemplate):
    """DocTemplate that records report headings for a multi-pass contents page."""

    def afterFlowable(self, flowable):
        entry = getattr(flowable, "_accountiq_toc_entry", None)
        if not entry:
            return
        level, text, key = entry
        if key:
            self.canv.bookmarkPage(key)
        self.notify("TOCEntry", (level, text, self.page, key))


def _toc_paragraph(paragraph: Paragraph, *, text: str, key: str, level: int = 0) -> Paragraph:
    """Attach a table-of-contents entry to a heading paragraph."""
    paragraph._accountiq_toc_entry = (
        level,
        html.escape(_normalize_pdf_text(text)),
        key,
    )
    return paragraph


def report_pdf_path(export_dir: Path, report_id: int) -> Path:
    """Return the stable cached path for a generated report PDF."""
    return export_dir / f"report-{report_id}.pdf"


def report_reference_code(report_id: int, report_type: str = "valuation_advisory") -> str:
    """Return a professional, stable reference code for report covers."""
    try:
        number = max(0, int(report_id))
    except (TypeError, ValueError):
        number = 0
    prefix = "AIQ-VAL" if report_type == "valuation_advisory" else "AIQ-REP"
    return f"{prefix}-{number:06d}"


def _running_header_label(company_name: str, report_label: str, max_chars: int = 82) -> str:
    """Return a compact repeated PDF page header label."""
    label = f"{_normalize_pdf_text(report_label)} | {_normalize_pdf_text(company_name)}".strip(" |")
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 3].rstrip() + "..."


def valuation_basis_of_preparation(
    *,
    company_name: str = "",
    report_label: str = "",
    report_id: int | str | None = None,
    demo_mode: bool = False,
    valuation_purpose: str = "",
    generated_at: str = "",
    intake_answers: dict | None = None,
) -> dict:
    """Return reusable valuation front-matter explaining evidence and model basis."""
    research_label = (
        "Simulated public research"
        if demo_mode
        else "Public research and source trail"
    )
    purpose = valuation_purpose.strip() or "Not specified"
    valuation_date = report_display_date(generated_at)
    prepared_for = company_name.strip() or "The business reviewed"
    prepared_report_label = report_label.strip() or "Indicative Valuation Report"
    reference = (
        report_reference_code(report_id, "valuation_advisory")
        if report_id not in (None, "")
        else "Not assigned"
    )
    evidence_rows = [
        [
            "Uploaded financial statements",
            "Used for historical revenue, profitability, balance sheet items, working capital, candidate normalisations and financial ratio analysis.",
        ],
        [
            "Five management-confirmed private inputs",
            "Used for purpose, owner or key-person dependency, customer concentration, revenue predictability and the realistic 12-24 month revenue outlook.",
        ],
        [
            "Earnings-adjustment review",
            "Used to confirm genuine one-off, owner-specific or non-operating items before they appear in the normalisation schedule; recurring operating costs are intentionally left in the earnings base.",
        ],
        [
            "Optional public-source hints",
            "Used only to match the correct business and guide research. They are not required from management and are treated as source hints until corroborated.",
        ],
    ]
    management_input_rows = _valuation_management_input_rows(intake_answers)
    research_hint_summary = _valuation_research_hint_summary(intake_answers)
    if research_hint_summary:
        evidence_rows.append(
            [
                "Research hints provided",
                research_hint_summary,
            ]
        )
    evidence_rows.extend(
        [
            [
                research_label,
                "Used for company and sector context, comparable evidence, RBNZ risk-free-rate context, Damodaran discount-rate inputs and inflation assumptions; URLs are retained in the sources section.",
            ],
            [
                "AccountIQ valuation model",
                "AccountIQ calculates the DCF valuation, discount-rate scenarios, multiples cross-check, enterprise-to-equity bridge, sensitivity matrix and forecast cash-flow schedule before the narrative is written.",
            ],
            [
                "Derived technical assumptions",
                "Discount rate, terminal growth and forecast horizon are derived by the AccountIQ valuation model and disclosed in the report rather than selected by management.",
            ],
            [
                "Questions intentionally not asked",
                "Management is not asked to choose the forecast horizon, WACC, terminal growth or discount-rate scenarios; AccountIQ derives these technical inputs from uploaded financials, public market evidence and its valuation model.",
            ],
        ]
    )

    return {
        "report_letter": {
            "title": "Report letter",
            "narrative": (
                f"AccountIQ has prepared this indicative valuation report for {prepared_for} "
                f"as a professional valuation report pack for {prepared_report_label}. It is intended to "
                "give the reader a clear valuation range, the evidence relied upon, the key "
                "limitations and the management-confirmed assumptions without requiring the "
                "owner to complete a long technical valuation questionnaire."
            ),
            "table": {
                "headers": ["Letter item", "Report position"],
                "rows": [
                    ["Prepared for", prepared_for],
                    ["Prepared by", "AccountIQ valuation team"],
                    ["Preparer role", "Valuation report preparation and evidence synthesis"],
                    ["Organisation", "AccountIQ"],
                    ["Report channel", "Secure AccountIQ workspace and downloadable PDF"],
                    ["Report type", prepared_report_label],
                    ["Reference", reference],
                    ["Purpose and reliance", purpose],
                    ["Information relied upon", "Uploaded financial statements, five management-confirmed private inputs, the earnings-adjustment review, public-source research and AccountIQ valuation calculations."],
                    ["Work performed", "AccountIQ prepared DCF, discount-rate, sensitivity, multiples and enterprise-to-equity schedules and used those outputs to draft the valuation narrative."],
                    ["Important limitation", "This is an indicative valuation report only and is not an audit or assurance engagement, legal advice, tax advice, a fairness opinion or a buyer-specific synergy assessment."],
                ],
            },
        },
        "narrative": (
            "This front-matter explains how AccountIQ prepared the indicative valuation from "
            "uploaded financial information, management-confirmed private inputs, public research and "
            "AccountIQ valuation calculations. Technical assumptions such as discount rate, "
            "terminal growth and forecast horizon are derived and disclosed rather than selected "
            "by management, so the reader can see what each conclusion relies on."
        ),
        "scope_table": {
            "headers": ["Scope item", "Value"],
            "rows": [
                ["Valuation purpose", purpose],
                ["Valuation date", valuation_date],
                [
                    "Basis of value",
                    "Indicative fair-market value of the operating business on a going-concern basis, before buyer-specific synergies or transaction structure.",
                ],
                [
                    "Reliance limitation",
                    "Indicative valuation support for the stated purpose only; not financial advice and not a substitute for independent professional advice.",
                ],
                [
                    "Information basis",
                    "Prepared from uploaded financial statements, the five management-confirmed private inputs, the earnings-adjustment review, public-source research and AccountIQ valuation calculations available at the valuation date.",
                ],
                [
                    "Scope exclusions",
                    "Does not constitute an audit, assurance engagement, legal advice, tax advice, transaction fairness opinion or buyer-specific synergy assessment.",
                ],
            ],
        },
        "management_input_table": {
            "headers": ["Management input", "Basis", "How it informs the report"],
            "rows": management_input_rows,
        },
        "table": {
            "headers": ["Input area", "How it is used in the report"],
            "rows": evidence_rows,
        },
    }


def _valuation_management_input_rows(intake_answers: dict | None) -> list[list[str]]:
    """Return front-matter rows showing how the five private answers affect the report."""
    if not isinstance(intake_answers, dict):
        return []

    rows: list[list[str]] = []
    for field_name, label, treatment in _MANAGEMENT_INPUT_TRAIL:
        raw_value = intake_answers.get(field_name)
        if raw_value in (None, ""):
            continue
        rows.append(
            [
                f"Management input - {label}",
                "Management-confirmed private input",
                f"{report_answer_label(field_name, str(raw_value))}. {treatment}",
            ]
        )
    return rows


def _clean_research_hint(value: object, *, max_chars: int = 180) -> str:
    """Return compact front-matter text for management-supplied research hints."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _research_hint_list(value: object, *, max_items: int = 3) -> tuple[list[str], int]:
    """Normalise a bounded list of management-supplied public link hints for display."""
    if value in (None, ""):
        return [], 0
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[\n,]+", str(value))
    cleaned = [_clean_research_hint(item, max_chars=150) for item in raw_items]
    items = [item for item in cleaned if item]
    return items[:max_items], max(0, len(items) - max_items)


def _valuation_research_hint_summary(intake_answers: dict | None) -> str:
    """Summarise optional website/location/source/private-context hints for front matter."""
    if not isinstance(intake_answers, dict):
        return ""

    parts: list[str] = []
    website = _clean_research_hint(intake_answers.get("company_website"))
    if website:
        parts.append(f"Website: {website}")
    location = _clean_research_hint(intake_answers.get("company_location"), max_chars=120)
    if location:
        parts.append(f"Location: {location}")
    source_links, remaining_links = _research_hint_list(intake_answers.get("public_source_urls"))
    if source_links:
        link_text = "; ".join(source_links)
        if remaining_links:
            link_text += f"; plus {remaining_links} more"
        parts.append(f"Public links: {link_text}")
    private_context = _clean_research_hint(intake_answers.get("private_context"), max_chars=220)
    if private_context:
        parts.append(f"Private valuation context: {private_context}")

    return " | ".join(parts)


def _normalize_pdf_text(text: object) -> str:
    """Normalize report text for clean PDF extraction and conservative glyph support."""
    return (
        str(text)
        .replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("\u2022", "-")
    )


_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def report_display_date(value: object) -> str:
    """Return a formal report-date label while preserving unparseable text."""
    text = _normalize_pdf_text(value).strip()
    if not text:
        return "Prepared date"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return f"{parsed.day} {_MONTH_NAMES[parsed.month - 1]} {parsed.year}"


def _inline_markup(text: str) -> str:
    escaped = html.escape(_normalize_pdf_text(text))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def _narrative_flowables(text: str, styles: dict) -> list:
    flowables: list = []
    bullets: list[str] = []

    def flush_bullets() -> None:
        nonlocal bullets
        if not bullets:
            return
        for item in bullets:
            flowables.append(
                Paragraph(
                    f"- {_inline_markup(item)}",
                    styles["bullet"],
                )
            )
        flowables.append(Spacer(1, 2.2 * mm))
        bullets = []

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            flush_bullets()
            continue
        if line.startswith("## "):
            flush_bullets()
            flowables.append(Spacer(1, 2 * mm))
            flowables.append(Paragraph(_inline_markup(line[3:].strip()), styles["subheading"]))
        elif line.startswith("- ") or line.startswith("* "):
            bullets.append(line[2:].strip())
        else:
            flush_bullets()
            flowables.append(Paragraph(_inline_markup(line), styles["body"]))
            flowables.append(Spacer(1, 1.8 * mm))
    flush_bullets()
    return flowables


def _looks_numeric_table_value(value: object) -> bool:
    """Return True when a table value is mostly a financial number, percent or multiple."""
    text = _normalize_pdf_text(value).strip()
    if not text or "http://" in text.lower() or "https://" in text.lower():
        return False
    if any(char.isalpha() for char in text.replace("x", "").replace("X", "")):
        return False
    compact = (
        text.replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .replace("x", "")
        .replace("X", "")
        .replace("(", "")
        .replace(")", "")
        .replace("+", "")
        .replace("-", "")
        .replace(".", "")
        .replace(" ", "")
    )
    return bool(compact) and compact.isdigit()


def _right_aligned_pdf_columns(headers: list, rows: list[list], column_count: int) -> set[int]:
    """Choose PDF table columns that should be right-aligned as numeric measures."""
    text_header_markers = (
        "assumption",
        "date",
        "evidence",
        "input",
        "item",
        "limitation",
        "method",
        "primary source",
        "rationale",
        "relevance",
        "report treatment",
        "risk factor",
        "scenario",
        "source",
        "treatment",
        "valuation relevance",
        "why it matters",
    )
    right_aligned: set[int] = set()
    for column_index in range(1, column_count):
        header = _normalize_pdf_text(headers[column_index] if column_index < len(headers) else "").lower()
        if any(marker in header for marker in text_header_markers):
            continue
        values = [row[column_index] for row in rows if len(row) > column_index and str(row[column_index]).strip()]
        if not values:
            continue
        numeric_count = sum(1 for value in values if _looks_numeric_table_value(value))
        if numeric_count / len(values) >= 0.6:
            right_aligned.add(column_index)
    return right_aligned


def _report_table(table_data: dict, available_width: float, styles: dict) -> Table | None:
    headers = table_data.get("headers", []) or []
    rows = table_data.get("rows", []) or []
    if not isinstance(headers, list) or not isinstance(rows, list):
        return None
    valid_rows = [row for row in rows if isinstance(row, list)]
    if not headers and not valid_rows:
        return None

    column_count = max(
        len(headers),
        max((len(row) for row in valid_rows), default=0),
    )
    if column_count == 0:
        return None

    compact_table = column_count >= 4 and len(valid_rows) >= 7
    header_style = "table_header_compact" if compact_table else "table_header"
    cell_style = "table_cell_compact" if compact_table else "table_cell"
    horizontal_padding = 5 if compact_table else 7
    vertical_padding = 4.5 if compact_table else 7

    if column_count == 5:
        col_widths = [
            available_width * 0.27,
            available_width * 0.11,
            available_width * 0.14,
            available_width * 0.18,
            available_width * 0.30,
        ]
    else:
        first_width = available_width * (0.34 if column_count > 2 else 0.56)
        remaining = available_width - first_width
        col_widths = [first_width] + [remaining / (column_count - 1)] * (column_count - 1) if column_count > 1 else [available_width]

    right_aligned_columns = _right_aligned_pdf_columns(headers, valid_rows, column_count)
    right_header_style = ParagraphStyle(
        f"{styles[header_style].name}RightAligned",
        parent=styles[header_style],
        alignment=TA_RIGHT,
    )
    right_cell_style = ParagraphStyle(
        f"{styles[cell_style].name}RightAligned",
        parent=styles[cell_style],
        alignment=TA_RIGHT,
    )

    def cells(values: list, style_name: str, right_style: ParagraphStyle) -> list:
        padded = values + [""] * (column_count - len(values))
        return [
            Paragraph(
                html.escape(_normalize_pdf_text(value)),
                right_style if column_index in right_aligned_columns else styles[style_name],
            )
            for column_index, value in enumerate(padded)
        ]

    data = [cells(headers, header_style, right_header_style)] if headers else []
    data.extend(cells(row, cell_style, right_cell_style) for row in valid_rows)

    table = Table(data, colWidths=col_widths, repeatRows=1 if headers else 0, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), horizontal_padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), horizontal_padding),
        ("TOPPADDING", (0, 0), (-1, -1), vertical_padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), vertical_padding),
    ]
    for index in range(2 if headers else 1, len(data), 2):
        commands.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#F6F8FB")))
    first_body_row = 1 if headers else 0
    for column_index in right_aligned_columns:
        commands.extend([
            ("ALIGN", (column_index, first_body_row), (column_index, -1), "RIGHT"),
            ("ALIGN", (column_index, 0), (column_index, 0), "RIGHT"),
        ])
    table.setStyle(TableStyle(commands))
    return table


def _cover_valuation_snapshot(sections: dict) -> tuple[list[str], list[tuple[str, list[str]]]] | None:
    """Extract a compact high/mid/low valuation table for the report cover."""
    for section_key in ("executive_summary", "valuation_summary"):
        content = sections.get(section_key)
        if not isinstance(content, dict):
            continue
        table = content.get("table")
        if not isinstance(table, dict):
            continue
        headers = table.get("headers")
        rows = table.get("rows")
        if not isinstance(headers, list) or len(headers) < 2 or not isinstance(rows, list):
            continue

        scenario_headers = [_normalize_pdf_text(value) for value in headers[1:4]]
        snapshot_rows: list[tuple[str, list[str]]] = []
        priority_terms = (
            "enterprise value",
            "net debt",
            "equity value",
            "indicative equity",
        )
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            label = _normalize_pdf_text(row[0])
            label_lower = label.lower()
            if not any(term in label_lower for term in priority_terms):
                continue
            values = [_normalize_pdf_text(value) for value in row[1:4]]
            if values:
                snapshot_rows.append((label, values))

        if scenario_headers and snapshot_rows:
            return scenario_headers, snapshot_rows[:3]
    return None


def executive_valuation_highlights(sections: dict) -> list[tuple[str, str, str]]:
    """Return executive-summary highlight rows sourced from the computed valuation table."""
    if not isinstance(sections, dict):
        return []
    content = sections.get("executive_summary")
    if not isinstance(content, dict):
        return []
    table = content.get("table")
    if not isinstance(table, dict):
        return []
    headers = table.get("headers")
    rows = table.get("rows")
    if not isinstance(headers, list) or len(headers) < 2 or not isinstance(rows, list):
        return []

    scenario_indexes = {
        _normalize_pdf_text(header).strip().lower(): index
        for index, header in enumerate(headers)
        if index > 0
    }
    high_index = scenario_indexes.get("high", 1)
    mid_index = scenario_indexes.get("mid", 2 if len(headers) > 2 else high_index)
    low_index = scenario_indexes.get("low", min(3, len(headers) - 1))

    def find_row(*terms: str) -> list | None:
        for row in rows:
            if not isinstance(row, list) or not row:
                continue
            label = _normalize_pdf_text(row[0]).lower()
            if all(term in label for term in terms):
                return row
        return None

    def cell(row: list | None, index: int) -> str:
        if not row or index >= len(row):
            return ""
        return _normalize_pdf_text(row[index]).strip()

    enterprise_row = find_row("enterprise", "value")
    equity_row = find_row("equity", "value")
    net_debt_row = find_row("net", "debt")

    highlights: list[tuple[str, str, str]] = []
    enterprise_low = cell(enterprise_row, low_index)
    enterprise_high = cell(enterprise_row, high_index)
    enterprise_mid = cell(enterprise_row, mid_index)
    if enterprise_low and enterprise_high:
        highlights.append(
            (
                "Enterprise value range",
                f"{enterprise_low} - {enterprise_high}",
                "Primary DCF valuation range after the private-company illiquidity adjustment.",
            )
        )
    if enterprise_mid:
        highlights.append(
            (
                "Midpoint enterprise value",
                enterprise_mid,
                "Central indication before the net debt and surplus asset bridge.",
            )
        )
    equity_mid = cell(equity_row, mid_index)
    if equity_mid:
        highlights.append(
            (
                "Midpoint equity value",
                equity_mid,
                "Central shareholder-value indication after the enterprise-to-equity bridge.",
            )
        )
    net_debt_mid = cell(net_debt_row, mid_index)
    if net_debt_mid:
        highlights.append(
            (
                "Net debt adjustment",
                net_debt_mid,
                "Bridge item applied consistently across the valuation scenarios.",
            )
        )

    return highlights[:4]


def valuation_range_visual(sections: dict) -> tuple[str, list[dict[str, object]]] | None:
    """Return low/mid/high range rows sourced from the computed executive valuation table."""
    table = _section_table(sections, "executive_summary")
    if table is None:
        return None

    scenario_indexes = _scenario_column_indexes(table)
    high_index = scenario_indexes.get("high", 1)
    mid_index = scenario_indexes.get("mid", 2)
    low_index = scenario_indexes.get("low", 3)
    range_specs = [
        (
            "Enterprise value",
            _find_table_row(table, "enterprise", "value"),
            "Operating-business value before the net-debt bridge.",
        ),
        (
            "Indicative equity value",
            _find_table_row(table, "equity", "value"),
            "Shareholder-value range after debt, cash and surplus assets.",
        ),
    ]

    rows: list[dict[str, object]] = []
    for label, row, note in range_specs:
        low_label = _table_cell(row, low_index)
        mid_label = _table_cell(row, mid_index)
        high_label = _table_cell(row, high_index)
        low_value = _money_value(low_label)
        mid_value = _money_value(mid_label)
        high_value = _money_value(high_label)
        if low_value is None or mid_value is None or high_value is None:
            continue
        values = sorted([low_value, high_value])
        rows.append(
            {
                "label": label,
                "low_label": low_label,
                "mid_label": mid_label,
                "high_label": high_label,
                "low_value": values[0],
                "mid_value": mid_value,
                "high_value": values[1],
                "note": note,
            }
        )

    if not rows:
        return None
    return "Valuation range visual", rows


def equity_bridge_visual(sections: dict) -> tuple[str, dict[str, object]] | None:
    """Return the enterprise-to-equity bridge sourced from the balance-sheet summary table."""
    table = _section_table(sections, "balance_sheet_summary")
    if table is None:
        return None

    enterprise_label = _table_cell(_find_table_row(table, "midpoint", "enterprise", "value"), 1)
    net_debt_row = _find_table_row(table, "less", "net", "debt") or _find_table_row(table, "net", "debt")
    net_debt_label = _table_cell(net_debt_row, 1)
    surplus_label = _table_cell(_find_table_row(table, "surplus", "assets"), 1)
    equity_label = _table_cell(_find_table_row(table, "midpoint", "equity", "value"), 1)

    enterprise_value = _money_value(enterprise_label)
    net_debt_value = _money_value(net_debt_label)
    surplus_value = _money_value(surplus_label)
    equity_value = _money_value(equity_label)
    if enterprise_value is None or net_debt_value is None or equity_value is None:
        return None

    if surplus_value is None:
        surplus_value = 0.0
        surplus_label = "$0"

    return (
        "Enterprise-to-equity visual",
        {
            "enterprise_label": enterprise_label,
            "enterprise_value": enterprise_value,
            "net_debt_label": net_debt_label,
            "net_debt_value": net_debt_value,
            "surplus_label": surplus_label,
            "surplus_value": surplus_value,
            "equity_label": equity_label,
            "equity_value": equity_value,
            "note": "Shows how operating-business value converts to shareholder value using existing balance-sheet inputs.",
        },
    )


def normalised_ebitda_bridge_visual(sections: dict) -> tuple[str, dict[str, object]] | None:
    """Return a bridge from uploaded EBITDA basis to normalised EBITDA."""
    table = _section_table(sections, "normalisations_schedule")
    if table is None:
        return None
    amount_index = _amount_column_index(table)
    normalised_row = _find_table_row(table, "normalised", "ebitda")
    normalised_label = _table_cell(normalised_row, amount_index)
    normalised_value = _money_value(normalised_label)
    if normalised_value is None:
        return None

    adjustment_rows: list[tuple[str, float]] = []
    for row in _table_rows(table):
        label = _normalize_pdf_text(row[0] if row else "").strip()
        label_lower = label.lower()
        if not label or "normalised" in label_lower:
            continue
        amount = _money_value(row[amount_index] if len(row) > amount_index else "")
        if amount in (None, 0):
            continue
        adjustment_rows.append((label, float(amount)))

    net_adjustment = sum(amount for _label, amount in adjustment_rows)
    uploaded_ebitda_value = normalised_value - net_adjustment
    adjustment_count = len(adjustment_rows)
    if adjustment_count:
        count_label = f"{adjustment_count} adjustment{'s' if adjustment_count != 1 else ''}"
        adjustment_note = "Management-reviewed add-backs or deductions confirmed before valuing maintainable earnings."
    else:
        count_label = "No adjustments confirmed"
        adjustment_note = "No management-reviewed add-backs or deductions were applied."

    return (
        "Normalised EBITDA bridge",
        {
            "uploaded_ebitda_label": _money_cell(uploaded_ebitda_value),
            "net_adjustment_label": _money_cell(net_adjustment),
            "normalised_ebitda_label": normalised_label,
            "adjustment_count_label": count_label,
            "adjustment_note": adjustment_note,
            "note": (
                "Shows how uploaded operating earnings from the uploaded accounts convert to the "
                "maintainable EBITDA used in the valuation. Source basis: uploaded accounts plus "
                "confirmed adjustment rows from the earnings-adjustment review. Valuation use: the "
                "same normalised EBITDA is carried into DCF and multiples."
            ),
        },
    )


def dcf_value_build_visual(sections: dict) -> tuple[str, dict[str, object]] | None:
    """Return the mid-case DCF value build sourced from computed DCF tables."""
    table = _section_table(sections, "dcf_analysis")
    cash_flow_schedule = _section_subtable(sections, "dcf_analysis", "cash_flow_schedule")
    if table is None or cash_flow_schedule is None:
        return None

    scenario_indexes = _scenario_column_indexes(table)
    mid_index = scenario_indexes.get("mid", 2)
    ev_before_label = _table_cell(
        _find_table_row(table, "enterprise", "value", "before", "illiquidity"),
        mid_index,
    )
    adjusted_ev_label = _table_cell(_find_table_row(table, "adjusted", "enterprise", "value"), mid_index)
    ev_before_value = _money_value(ev_before_label)
    adjusted_ev_value = _money_value(adjusted_ev_label)
    discounted_fcff_row = _find_table_row(cash_flow_schedule, "discounted", "free", "cash", "flow")
    explicit_fcff_values = [
        value
        for cell in (discounted_fcff_row or [])[1:]
        if (value := _money_value(cell)) is not None
    ]
    if ev_before_value is None or adjusted_ev_value is None or not explicit_fcff_values:
        return None

    explicit_fcff_value = sum(explicit_fcff_values)
    terminal_value = ev_before_value - explicit_fcff_value
    illiquidity_discount_value = ev_before_value - adjusted_ev_value
    if terminal_value < 0 or illiquidity_discount_value < 0:
        return None

    return (
        "DCF value build visual",
        {
            "explicit_fcff_label": _money_cell(explicit_fcff_value),
            "explicit_fcff_value": explicit_fcff_value,
            "terminal_value_label": _money_cell(terminal_value),
            "terminal_value": terminal_value,
            "ev_before_illiquidity_label": ev_before_label,
            "ev_before_illiquidity_value": ev_before_value,
            "illiquidity_discount_label": _money_cell(illiquidity_discount_value),
            "illiquidity_discount_value": illiquidity_discount_value,
            "adjusted_ev_label": adjusted_ev_label,
            "adjusted_ev_value": adjusted_ev_value,
            "note": "Shows how the mid-case discounted cash flows and terminal value convert to adjusted enterprise value.",
        },
    )


def wacc_build_visual(sections: dict) -> tuple[str, dict[str, object]] | None:
    """Return the mid-case WACC build sourced from the computed WACC assumptions table."""
    table = _section_table(sections, "wacc_assumptions")
    if table is None:
        return None

    scenario_indexes = _scenario_column_indexes(table)
    mid_index = scenario_indexes.get("mid", 2)
    risk_free_label = _table_cell(_find_table_row(table, "risk-free", "rate"), mid_index)
    erp_label = _table_cell(_find_table_row(table, "equity", "risk", "premium"), mid_index)
    beta_label = _table_cell(_find_table_row(table, "industry", "total", "beta"), mid_index)
    wacc_label = _table_cell(_find_table_row(table, "wacc"), mid_index)
    illiquidity_label = _table_cell(_find_table_row(table, "illiquidity", "discount"), mid_index)

    risk_free_value = _money_value(risk_free_label)
    erp_value = _money_value(erp_label)
    beta_value = _money_value(beta_label)
    wacc_value = _money_value(wacc_label)
    if risk_free_value is None or erp_value is None or beta_value is None or wacc_value is None:
        return None

    beta_adjusted_premium_value = wacc_value - risk_free_value
    if beta_adjusted_premium_value < 0:
        return None

    return (
        "WACC build visual",
        {
            "risk_free_label": risk_free_label,
            "risk_free_value": risk_free_value,
            "erp_label": erp_label,
            "erp_value": erp_value,
            "beta_label": beta_label,
            "beta_value": beta_value,
            "beta_adjusted_premium_label": f"{beta_adjusted_premium_value:.1f}%",
            "beta_adjusted_premium_value": beta_adjusted_premium_value,
            "wacc_label": wacc_label,
            "wacc_value": wacc_value,
            "illiquidity_label": illiquidity_label,
            "note": "Shows the mid-case discount-rate build from public market inputs before the separate illiquidity discount.",
            "premium_note": f"Derived from {beta_label} total beta and {erp_label} equity risk premium.",
        },
    )


def implied_multiple_reconciliation(sections: dict) -> tuple[str, dict[str, object]] | None:
    """Return DCF-implied multiples versus the researched market cross-check range."""
    multiples_table = _section_table(sections, "multiples_crosscheck")
    valuation_table = _section_table(sections, "valuation_summary")
    dcf_table = _section_table(sections, "dcf_analysis")
    if multiples_table is None:
        return None

    multiples_indexes = _scenario_column_indexes(multiples_table)
    market_low_index = multiples_indexes.get("low", 1)
    market_mid_index = multiples_indexes.get("mid", 2)
    market_high_index = multiples_indexes.get("high", 3)
    market_multiple_row = _find_table_row(multiples_table, "ev/ebitda")
    ebitda_row = _find_table_row(multiples_table, "normalised", "ebitda")

    normalised_ebitda_label = _table_cell(ebitda_row, market_mid_index) or _table_cell(ebitda_row, market_low_index)
    normalised_ebitda = _money_value(normalised_ebitda_label)
    market_low_label = _table_cell(market_multiple_row, market_low_index)
    market_mid_label = _table_cell(market_multiple_row, market_mid_index)
    market_high_label = _table_cell(market_multiple_row, market_high_index)
    market_low = _multiple_value(market_low_label)
    market_mid = _multiple_value(market_mid_label)
    market_high = _multiple_value(market_high_label)
    if market_mid is None and market_low is not None and market_high is not None:
        market_mid = (market_low + market_high) / 2
        market_mid_label = _multiple_cell(market_mid)
    if normalised_ebitda in (None, 0) or market_low is None or market_high is None:
        return None

    pre_values: list[float] = []
    post_values: list[float] = []
    pre_mid_value: float | None = None
    post_mid_value: float | None = None

    if valuation_table is not None:
        enterprise_value_index = _column_index_by_terms(valuation_table, "enterprise", default=2)
        adjusted_ev_index = _column_index_by_terms(valuation_table, "adjusted", default=3)
        dcf_rows = [
            _find_table_row(valuation_table, "dcf", "high"),
            _find_table_row(valuation_table, "dcf", "mid"),
            _find_table_row(valuation_table, "dcf", "low"),
        ]
        for row in dcf_rows:
            pre_value = _money_value(_table_cell(row, enterprise_value_index))
            post_value = _money_value(_table_cell(row, adjusted_ev_index))
            if pre_value is not None:
                pre_values.append(pre_value)
            if post_value is not None:
                post_values.append(post_value)
        dcf_mid_row = _find_table_row(valuation_table, "dcf", "mid")
        pre_mid_value = _money_value(_table_cell(dcf_mid_row, enterprise_value_index))
        post_mid_value = _money_value(_table_cell(dcf_mid_row, adjusted_ev_index))

    if dcf_table is not None and (not pre_values or not post_values):
        scenario_indexes = _scenario_column_indexes(dcf_table)
        high_index = scenario_indexes.get("high", 1)
        mid_index = scenario_indexes.get("mid", 2)
        low_index = scenario_indexes.get("low", 3)
        pre_row = _find_table_row(dcf_table, "enterprise", "value", "before", "illiquidity")
        post_row = _find_table_row(dcf_table, "adjusted", "enterprise", "value")
        pre_values = [
            value
            for index in (high_index, mid_index, low_index)
            if (value := _money_value(_table_cell(pre_row, index))) is not None
        ]
        post_values = [
            value
            for index in (high_index, mid_index, low_index)
            if (value := _money_value(_table_cell(post_row, index))) is not None
        ]
        pre_mid_value = _money_value(_table_cell(pre_row, mid_index))
        post_mid_value = _money_value(_table_cell(post_row, mid_index))

    if not pre_values or not post_values or pre_mid_value is None or post_mid_value is None:
        return None

    pre_multiples = [value / normalised_ebitda for value in pre_values]
    post_multiples = [value / normalised_ebitda for value in post_values]
    pre_mid_multiple = pre_mid_value / normalised_ebitda
    post_mid_multiple = post_mid_value / normalised_ebitda
    gap_label = ""
    if market_mid is not None:
        gap = post_mid_multiple - market_mid
        if abs(gap) >= 0.05:
            gap_label = f"{_multiple_cell(abs(gap))} {'above' if gap > 0 else 'below'} market midpoint"

    return (
        "Implied multiple reconciliation",
        {
            "normalised_ebitda_label": normalised_ebitda_label,
            "market_range_label": f"{_multiple_cell(min(market_low, market_high))} - {_multiple_cell(max(market_low, market_high))}",
            "market_mid_label": market_mid_label,
            "dcf_pre_range_label": f"{_multiple_cell(min(pre_multiples))} - {_multiple_cell(max(pre_multiples))}",
            "dcf_pre_mid_label": _multiple_cell(pre_mid_multiple),
            "dcf_post_range_label": f"{_multiple_cell(min(post_multiples))} - {_multiple_cell(max(post_multiples))}",
            "dcf_post_mid_label": _multiple_cell(post_mid_multiple),
            "midpoint_gap_label": gap_label,
            "note": "Compares the primary DCF output with the researched EV/EBITDA cross-check range.",
        },
    )


def valuation_method_selection(sections: dict) -> tuple[str, list[dict[str, str]]] | None:
    """Return the adopted valuation approach rationale without adding owner questions."""
    valuation_table = _section_table(sections, "valuation_summary")
    dcf_table = _section_table(sections, "dcf_analysis")
    multiples_table = _section_table(sections, "multiples_crosscheck")
    balance_sheet_table = _section_table(sections, "balance_sheet_summary")

    dcf_range_label = ""
    if valuation_table is not None:
        adjusted_ev_index = _column_index_by_terms(valuation_table, "adjusted", default=3)
        dcf_values = [
            value
            for row in (
                _find_table_row(valuation_table, "dcf", "high"),
                _find_table_row(valuation_table, "dcf", "mid"),
                _find_table_row(valuation_table, "dcf", "low"),
            )
            if (value := _money_value(_table_cell(row, adjusted_ev_index))) is not None
        ]
        if dcf_values:
            dcf_range_label = f"{_money_cell(min(dcf_values))} - {_money_cell(max(dcf_values))}"
    if not dcf_range_label and dcf_table is not None:
        scenario_indexes = _scenario_column_indexes(dcf_table)
        adjusted_ev_row = _find_table_row(dcf_table, "adjusted", "enterprise", "value")
        dcf_values = [
            value
            for index in (
                scenario_indexes.get("high", 1),
                scenario_indexes.get("mid", 2),
                scenario_indexes.get("low", 3),
            )
            if (value := _money_value(_table_cell(adjusted_ev_row, index))) is not None
        ]
        if dcf_values:
            dcf_range_label = f"{_money_cell(min(dcf_values))} - {_money_cell(max(dcf_values))}"

    multiple_row = _find_table_row(multiples_table, "ev/ebitda")
    multiple_indexes = _scenario_column_indexes(multiples_table)
    low_multiple = _table_cell(multiple_row, multiple_indexes.get("low", 1))
    high_multiple = _table_cell(multiple_row, multiple_indexes.get("high", 3))
    market_range_label = f"{low_multiple} - {high_multiple}" if low_multiple and high_multiple else ""

    midpoint_equity_value = _table_cell(
        _find_table_row(balance_sheet_table, "midpoint", "equity", "value"),
        1,
    )

    rows = [
        {
            "approach": "Income approach - DCF",
            "role": "Adopted as primary",
            "rationale": "Best matches a going-concern SME where value is driven by expected maintainable free cash flow.",
            "report_treatment": (
                f"Primary adjusted enterprise-value range: {dcf_range_label}."
                if dcf_range_label
                else "Primary valuation range is calculated from the DCF schedules."
            ),
        },
        {
            "approach": "Market approach - EV/EBITDA",
            "role": "Reasonableness cross-check",
            "rationale": "Useful for market orientation, but not applied mechanically because public and transaction evidence differs in scale, liquidity, growth and participant-specific context.",
            "report_treatment": (
                f"Cross-check range: {market_range_label} EV/EBITDA."
                if market_range_label
                else "Market evidence is retained as a qualitative reasonableness cross-check."
            ),
        },
        {
            "approach": "Asset approach / net assets",
            "role": "Not primary",
            "rationale": "The report values the operating business as a going concern rather than on a liquidation or asset-accumulation basis.",
            "report_treatment": (
                f"Balance-sheet inputs are used for the enterprise-to-equity bridge; midpoint equity value is {midpoint_equity_value}."
                if midpoint_equity_value
                else "Balance-sheet inputs are used for the enterprise-to-equity bridge where available."
            ),
        },
    ]
    return "Valuation approach selection", rows


def financial_trend_visual(sections: dict) -> tuple[str, list[dict[str, object]]] | None:
    """Return revenue/EBITDA trend rows sourced from the computed financial-performance table."""
    table = _section_table(sections, "financial_performance")
    if table is None:
        return None
    headers = table.get("headers")
    if not isinstance(headers, list) or len(headers) < 2:
        return None

    revenue_row = _find_table_row(table, "revenue")
    ebitda_row = _find_exact_table_row(table, "EBITDA") or _find_table_row(table, "ebitda")
    margin_row = _find_exact_table_row(table, "EBITDA margin") or _find_table_row(table, "ebitda", "margin")
    rows: list[dict[str, object]] = []
    for index, header in enumerate(headers[1:], start=1):
        period = _normalize_pdf_text(header).strip()
        revenue_label = _table_cell(revenue_row, index)
        ebitda_label = _table_cell(ebitda_row, index)
        revenue_value = _money_value(revenue_label)
        ebitda_value = _money_value(ebitda_label)
        if not period or revenue_value is None or ebitda_value is None:
            continue
        rows.append(
            {
                "period": period,
                "revenue_label": revenue_label,
                "revenue_value": revenue_value,
                "ebitda_label": ebitda_label,
                "ebitda_value": ebitda_value,
                "margin_label": _table_cell(margin_row, index),
            }
        )

    if len(rows) < 2:
        return None
    return "Financial trend visual", rows


def sensitivity_spread_visual(sections: dict) -> tuple[str, list[dict[str, object]]] | None:
    """Return a downside/base/upside spread sourced from the computed sensitivity matrix."""
    table = _section_table(sections, "sensitivity_and_risks")
    sensitivity_rows = _table_rows(table)
    if not sensitivity_rows:
        return None

    scenario_indexes = _scenario_column_indexes(table)
    mid_index = scenario_indexes.get("mid", 2)
    base_row = _find_table_row(table, "base")
    if not base_row:
        base_row = sensitivity_rows[len(sensitivity_rows) // 2]
    base_label = _table_cell(base_row, mid_index)
    base_value = _money_value(base_label)
    value_cells: list[tuple[float, str]] = []
    for row in sensitivity_rows:
        for index in range(1, len(row)):
            cell = _table_cell(row, index)
            value = _money_value(cell)
            if value is not None:
                value_cells.append((value, cell))
    if not value_cells or base_value is None:
        return None

    downside_value, downside_label = min(value_cells, key=lambda item: item[0])
    upside_value, upside_label = max(value_cells, key=lambda item: item[0])
    growth_labels = [
        _normalize_pdf_text(row[0]).replace("- base", "").strip()
        for row in sensitivity_rows
        if row and _normalize_pdf_text(row[0]).strip()
    ]
    growth_range = (
        f"{growth_labels[0]} to {growth_labels[-1]}"
        if len(growth_labels) >= 2
        else (growth_labels[0] if growth_labels else "tested growth cases")
    )

    return (
        "Sensitivity spread visual",
        [
            {
                "label": "Adjusted enterprise value sensitivity",
                "low_label": downside_label,
                "mid_label": base_label,
                "high_label": upside_label,
                "low_value": downside_value,
                "mid_value": base_value,
                "high_value": upside_value,
                "note": f"Across {growth_range} growth and WACC cases.",
            }
        ],
    )


def _section_table(sections: dict, section_key: str) -> dict | None:
    """Return a structured report table for a section if one is present."""
    if not isinstance(sections, dict):
        return None
    content = sections.get(section_key)
    if not isinstance(content, dict):
        return None
    table = content.get("table")
    return table if isinstance(table, dict) else None


def _section_subtable(sections: dict, section_key: str, table_key: str) -> dict | None:
    """Return a named structured subtable for a section if one is present."""
    if not isinstance(sections, dict):
        return None
    content = sections.get(section_key)
    if not isinstance(content, dict):
        return None
    table = content.get(table_key)
    return table if isinstance(table, dict) else None


def _table_rows(table: dict | None) -> list[list]:
    """Return valid table rows from a structured table."""
    rows = table.get("rows") if isinstance(table, dict) else None
    return [row for row in rows or [] if isinstance(row, list)]


def _find_table_row(table: dict | None, *terms: str) -> list | None:
    """Find the first table row whose label contains all supplied terms."""
    for row in _table_rows(table):
        if not row:
            continue
        label = _normalize_pdf_text(row[0]).lower()
        if all(term.lower() in label for term in terms):
            return row
    return None


def _find_exact_table_row(table: dict | None, *labels: str) -> list | None:
    """Find a table row by exact label before falling back to broad term search."""
    wanted = {
        _normalize_pdf_text(label).strip().lower()
        for label in labels
        if _normalize_pdf_text(label).strip()
    }
    for row in _table_rows(table):
        if not row:
            continue
        label = _normalize_pdf_text(row[0]).strip().lower()
        if label in wanted:
            return row
    return None


def _table_cell(row: list | None, index: int) -> str:
    """Return a normalised table cell value."""
    if not row or index >= len(row):
        return ""
    return _normalize_pdf_text(row[index]).strip()


def _scenario_column_indexes(table: dict | None) -> dict[str, int]:
    """Return likely High/Mid/Low scenario column indexes from table headers."""
    headers = table.get("headers") if isinstance(table, dict) else None
    if not isinstance(headers, list):
        return {}
    indexes: dict[str, int] = {}
    for index, header in enumerate(headers):
        if index == 0:
            continue
        text = _normalize_pdf_text(header).strip().lower()
        for scenario in ("high", "mid", "low"):
            if scenario in text and scenario not in indexes:
                indexes[scenario] = index
    return indexes


def _url_count_from_rows(rows: list[list]) -> int:
    """Count distinct public URLs in table rows."""
    urls: set[str] = set()
    for row in rows:
        for cell in row:
            for match in re.findall(r"https?://[^\s\"'<>]+", _normalize_pdf_text(cell)):
                urls.add(match.rstrip(").,;]"))
    return len(urls)


def _sources_support_text(rows: list[list]) -> str:
    """Return normalised source/support text for source-trail guidance."""
    return " ".join(
        _normalize_pdf_text(cell).lower()
        for row in rows
        for cell in row
    )


def _first_data_cell(row: list | None) -> str:
    """Return the first non-empty non-label value from a table row."""
    for value in (row or [])[1:]:
        text = _normalize_pdf_text(value).strip()
        if text:
            return text
    return ""


def _first_meaningful_data_cell(row: list | None) -> str:
    """Return the first non-empty non-placeholder value from a table row."""
    for value in (row or [])[1:]:
        text = _normalize_pdf_text(value).strip()
        if text and text.lower() not in {"not available", "n/a", "na"}:
            return text
    return _first_data_cell(row)


def _last_data_cell(row: list | None) -> str:
    """Return the last non-empty non-label value from a table row."""
    for value in reversed((row or [])[1:]):
        text = _normalize_pdf_text(value).strip()
        if text:
            return text
    return ""


def _latest_actual_cell(table: dict | None, row: list | None) -> str:
    """Return the latest value under a header labelled Actual, or the last row value."""
    headers = table.get("headers") if isinstance(table, dict) else None
    if not isinstance(headers, list) or not row:
        return _last_data_cell(row)
    actual_indexes = [
        index
        for index, header in enumerate(headers)
        if index > 0 and "actual" in _normalize_pdf_text(header).lower()
    ]
    for index in reversed(actual_indexes):
        value = _table_cell(row, index)
        if value:
            return value
    return _last_data_cell(row)


def _money_value(value: object) -> float | None:
    """Return a numeric money value from a formatted report-table cell."""
    text = _normalize_pdf_text(value).strip()
    if not text or text.lower() in {"not available", "n/a", "na"}:
        return None
    is_negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.strip("()")
        .replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .strip()
    )
    if cleaned.startswith("-"):
        is_negative = True
        cleaned = cleaned[1:].strip()
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return -number if is_negative else number


def _money_cell(value: float) -> str:
    """Format a numeric money value for compact report guidance."""
    if value < 0:
        return f"(${abs(value):,.0f})"
    return f"${value:,.0f}"


def _multiple_value(value: object) -> float | None:
    """Return a numeric multiple from a formatted cell such as '6.0x' or '6.0x EBITDA'."""
    text = _normalize_pdf_text(value).strip().lower()
    if not text or text in {"not available", "n/a", "na"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _multiple_cell(value: float) -> str:
    """Format a valuation multiple for compact report guidance."""
    return f"{value:.1f}x"


def _amount_column_index(table: dict | None, default: int = 1) -> int:
    """Return the most likely amount/value column index for a report table."""
    headers = table.get("headers") if isinstance(table, dict) else None
    if not isinstance(headers, list):
        return default
    for index, header in enumerate(headers):
        if index == 0:
            continue
        text = _normalize_pdf_text(header).strip().lower()
        if "amount" in text or text == "value":
            return index
    return default


def _column_index_by_terms(table: dict | None, *terms: str, default: int = 1) -> int:
    """Return the first non-label column whose header contains all terms."""
    headers = table.get("headers") if isinstance(table, dict) else None
    if not isinstance(headers, list):
        return default
    normalised_terms = [
        _normalize_pdf_text(term).strip().lower()
        for term in terms
        if _normalize_pdf_text(term).strip()
    ]
    if not normalised_terms:
        return default
    for index, header in enumerate(headers):
        if index == 0:
            continue
        text = _normalize_pdf_text(header).strip().lower()
        if all(term in text for term in normalised_terms):
            return index
    return default


def valuation_reader_guidance(sections: dict, section_key: str) -> tuple[str, list[tuple[str, str, str]]] | None:
    """Return compact interpretation panels sourced from computed valuation tables."""
    if section_key == "business_overview":
        assumptions_table = _section_table(sections, "valuation_assumptions")
        value_index = _column_index_by_terms(assumptions_table, "value", default=1)
        owner_dependency = _table_cell(_find_table_row(assumptions_table, "owner", "dependency"), value_index)
        customer_concentration = _table_cell(
            _find_table_row(assumptions_table, "largest", "customer", "concentration"),
            value_index,
        )
        revenue_predictability = _table_cell(
            _find_table_row(assumptions_table, "revenue", "predictability"),
            value_index,
        )
        revenue_outlook = _table_cell(_find_table_row(assumptions_table, "revenue", "outlook"), value_index)
        rows = [
            (
                "Owner or key-person dependency",
                owner_dependency,
                "Management-supplied context used to frame transition and key-person risk.",
            ),
            (
                "Customer concentration",
                customer_concentration,
                "Management-supplied context highlighting whether revenue is exposed to large customers.",
            ),
            (
                "Revenue predictability",
                revenue_predictability,
                "Management-supplied context distinguishing recurring, mixed and project-based revenue.",
            ),
            (
                "Revenue outlook",
                revenue_outlook,
                "Management-supplied context used to support or derive the short-term growth assumption.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Business context at a glance", rows

    if section_key == "market_position":
        comparable_table = _section_table(sections, "comparable_evidence")
        sources_table = _section_table(sections, "sources")
        comparable_rows = _table_rows(comparable_table)
        source_rows = _table_rows(sources_table)
        combined_rows = comparable_rows + source_rows
        if not combined_rows:
            return None
        support_text = _sources_support_text(combined_rows)
        url_count = _url_count_from_rows(combined_rows)
        market_benchmark_supported = any(
            marker in support_text
            for marker in ("ev/ebitda", "benchmark", "market multiple", "sector", "comparable")
        )
        public_profile_supported = any(
            marker in support_text
            for marker in ("company public-profile", "public-profile", "companies office", "public claims")
        )
        comparability_caveat = any(
            marker in support_text
            for marker in ("not directly comparable", "broad", "larger", "more liquid", "limitation")
        )
        rows = [
            (
                "Public sources retained",
                str(url_count) if url_count else "",
                "Source URLs are retained for market, profile and benchmark context.",
            ),
            (
                "Benchmark evidence",
                (
                    "Public evidence supports sector or EV/EBITDA context"
                    if market_benchmark_supported
                    else "No specific public benchmark evidence identified"
                ),
                "Explains whether public evidence supports market or EV/EBITDA context.",
            ),
            (
                "Public profile support",
                (
                    "Public sources support the company profile or operating context"
                    if public_profile_supported
                    else "No specific public company-profile support identified"
                ),
                "Explains whether public sources support company-profile or operating-context statements.",
            ),
            (
                "Comparability caveat",
                (
                    "Limitations explain the evidence is contextual, not direct pricing"
                    if comparability_caveat
                    else "No explicit comparability limitation identified"
                ),
                "Explains that public evidence is used for context and cross-checking, not a direct price.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Market context at a glance", rows

    if section_key == "valuation_methodology":
        wacc_table = _section_table(sections, "wacc_assumptions")
        multiples_table = _section_table(sections, "multiples_crosscheck")
        balance_sheet_table = _section_table(sections, "balance_sheet_summary")
        wacc_row = _find_table_row(wacc_table, "wacc")
        wacc_indexes = _scenario_column_indexes(wacc_table)
        low_discount_rate = _table_cell(wacc_row, wacc_indexes.get("high", 1))
        high_discount_rate = _table_cell(wacc_row, wacc_indexes.get("low", 3))
        multiple_row = _find_table_row(multiples_table, "ev/ebitda")
        multiple_indexes = _scenario_column_indexes(multiples_table)
        low_multiple = _table_cell(multiple_row, multiple_indexes.get("low", 1))
        high_multiple = _table_cell(multiple_row, multiple_indexes.get("high", 3))
        midpoint_equity_value = _table_cell(
            _find_table_row(balance_sheet_table, "midpoint", "equity", "value"),
            1,
        )
        rows = [
            (
                "Primary valuation method",
                "Discounted cash flow",
                "Forecast free cash flows are the primary valuation basis.",
            ),
            (
                "Discount-rate range",
                (
                    f"{low_discount_rate} - {high_discount_rate}"
                    if low_discount_rate and high_discount_rate
                    else ""
                ),
                "High, midpoint and low WACC scenarios create the valuation range.",
            ),
            (
                "Market cross-check",
                (
                    f"{low_multiple} - {high_multiple} EV/EBITDA"
                    if low_multiple and high_multiple
                    else ""
                ),
                "Researched market multiples are used as a reasonableness check.",
            ),
            (
                "Equity bridge",
                midpoint_equity_value,
                "Enterprise value is bridged to shareholder value using debt, cash and surplus assets.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Methodology at a glance", rows

    if section_key == "financial_performance":
        table = _section_table(sections, section_key)
        revenue_row = _find_table_row(table, "revenue")
        direct_cost_row = _find_table_row(table, "direct", "cost")
        gross_profit_row = _find_table_row(table, "gross", "profit")
        operating_expense_row = _find_table_row(table, "operating", "expenses")
        wages_row = (
            _find_table_row(table, "opex", "wages")
            or _find_table_row(table, "wages", "salaries")
            or _find_table_row(table, "wages")
        )
        rent_row = (
            _find_table_row(table, "opex", "rent")
            or _find_table_row(table, "rent", "occupancy")
            or _find_table_row(table, "rent")
        )
        other_opex_row = (
            _find_table_row(table, "opex", "other")
            or _find_table_row(table, "other", "operating", "expenses")
        )
        ebitda_row = _find_exact_table_row(table, "EBITDA") or _find_table_row(table, "ebitda")
        ebitda_margin_row = _find_exact_table_row(table, "EBITDA margin") or _find_table_row(table, "ebitda", "margin")
        revenue_first = _first_data_cell(revenue_row)
        revenue_last = _last_data_cell(revenue_row)
        direct_cost_first = _first_data_cell(direct_cost_row)
        direct_cost_last = _last_data_cell(direct_cost_row)
        gross_profit_first = _first_data_cell(gross_profit_row)
        gross_profit_last = _last_data_cell(gross_profit_row)
        operating_expense_first = _first_data_cell(operating_expense_row)
        operating_expense_last = _last_data_cell(operating_expense_row)
        wages_first = _first_data_cell(wages_row)
        wages_last = _last_data_cell(wages_row)
        rent_first = _first_data_cell(rent_row)
        rent_last = _last_data_cell(rent_row)
        other_opex_first = _first_data_cell(other_opex_row)
        other_opex_last = _last_data_cell(other_opex_row)
        ebitda_first = _first_data_cell(ebitda_row)
        ebitda_last = _last_data_cell(ebitda_row)
        margin_first = _first_data_cell(ebitda_margin_row)
        margin_last = _last_data_cell(ebitda_margin_row)
        latest_actual_ebitda = _latest_actual_cell(table, ebitda_row)
        rows = [
            (
                "Revenue bridge",
                f"{revenue_first} to {revenue_last}" if revenue_first and revenue_last else "",
                "Top-line progression across the historical and forecast period shown in the report.",
            ),
            (
                "Direct-cost bridge",
                (
                    f"{direct_cost_first} to {direct_cost_last}"
                    if direct_cost_first and direct_cost_last
                    else ""
                ),
                "Shows the cost-of-sales deduction used to move from revenue to gross profit.",
            ),
            (
                "Gross profit bridge",
                (
                    f"{gross_profit_first} to {gross_profit_last}"
                    if gross_profit_first and gross_profit_last
                    else ""
                ),
                "Shows the trading margin available before overheads and other operating expenses.",
            ),
            (
                "Operating expense bridge",
                (
                    f"{operating_expense_first} to {operating_expense_last}"
                    if operating_expense_first and operating_expense_last
                    else ""
                ),
                "Shows the overhead deduction used to reconcile gross profit to EBITDA.",
            ),
            (
                "Wages and salaries",
                f"{wages_first} to {wages_last}" if wages_first and wages_last else "",
                "Highlights the main people-cost component inside operating expenses.",
            ),
            (
                "Rent and occupancy",
                f"{rent_first} to {rent_last}" if rent_first and rent_last else "",
                "Highlights the main premises or occupancy cost inside operating expenses.",
            ),
            (
                "Other operating expenses",
                f"{other_opex_first} to {other_opex_last}" if other_opex_first and other_opex_last else "",
                "Residual or other material overheads shown so EBITDA is easier to trace.",
            ),
            (
                "EBITDA bridge",
                f"{ebitda_first} to {ebitda_last}" if ebitda_first and ebitda_last else "",
                "Operating earnings progression before the normalisation schedule is applied.",
            ),
            (
                "EBITDA margin bridge",
                f"{margin_first} to {margin_last}" if margin_first and margin_last else "",
                "Shows whether operating leverage is improving, stable or weakening across the period.",
            ),
            (
                "Latest actual EBITDA",
                latest_actual_ebitda,
                "Latest actual earnings reference point before forecast and valuation adjustments.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Trading performance at a glance", rows

    if section_key == "financial_ratio_analysis":
        table = _section_table(sections, section_key)
        revenue_growth_row = _find_table_row(table, "revenue", "growth")
        gross_margin_row = _find_table_row(table, "gross", "margin")
        ebitda_margin_row = _find_table_row(table, "ebitda", "margin")
        net_profit_margin_row = _find_table_row(table, "net", "profit", "margin")
        revenue_growth_latest = _last_data_cell(revenue_growth_row)
        gross_margin_first = _first_meaningful_data_cell(gross_margin_row)
        gross_margin_last = _last_data_cell(gross_margin_row)
        ebitda_margin_first = _first_meaningful_data_cell(ebitda_margin_row)
        ebitda_margin_last = _last_data_cell(ebitda_margin_row)
        net_profit_margin_first = _first_meaningful_data_cell(net_profit_margin_row)
        net_profit_margin_last = _last_data_cell(net_profit_margin_row)
        rows = [
            (
                "Latest revenue growth",
                revenue_growth_latest,
                "Latest growth rate shown in the uploaded-financials trend table.",
            ),
            (
                "Gross margin bridge",
                f"{gross_margin_first} to {gross_margin_last}" if gross_margin_first and gross_margin_last else "",
                "Shows whether direct-cost efficiency is improving, stable or weakening.",
            ),
            (
                "EBITDA margin bridge",
                f"{ebitda_margin_first} to {ebitda_margin_last}" if ebitda_margin_first and ebitda_margin_last else "",
                "Summarises operating leverage before valuation adjustments.",
            ),
            (
                "Net profit margin bridge",
                (
                    f"{net_profit_margin_first} to {net_profit_margin_last}"
                    if net_profit_margin_first and net_profit_margin_last
                    else ""
                ),
                "Shows the after-tax profit conversion trend visible in the uploaded financials.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Margin and growth at a glance", rows

    if section_key == "normalisations_schedule":
        table = _section_table(sections, section_key)
        amount_index = _amount_column_index(table)
        normalised_row = _find_table_row(table, "normalised", "ebitda")
        adjustment_rows: list[tuple[str, float]] = []
        for row in _table_rows(table):
            label = _normalize_pdf_text(row[0] if row else "").strip()
            label_lower = label.lower()
            if not label or "normalised" in label_lower:
                continue
            amount = _money_value(row[amount_index] if len(row) > amount_index else "")
            if amount in (None, 0):
                continue
            adjustment_rows.append((label, float(amount)))

        net_adjustment = sum(amount for _label, amount in adjustment_rows)
        largest_adjustment = (
            max(adjustment_rows, key=lambda item: abs(item[1]))
            if adjustment_rows
            else None
        )
        normalised_ebitda = _table_cell(normalised_row, amount_index)
        rows = [
            (
                "Confirmed adjustments",
                str(len(adjustment_rows)) if adjustment_rows else "",
                "Management-reviewed normalisation items included in the maintainable earnings bridge.",
            ),
            (
                "Net EBITDA adjustment",
                _money_cell(net_adjustment) if adjustment_rows else "",
                "Net add-back or deduction applied before the valuation earnings base.",
            ),
            (
                "Largest adjustment",
                f"{largest_adjustment[0]} - {_money_cell(largest_adjustment[1])}" if largest_adjustment else "",
                "Largest individual normalisation item for adviser or management review.",
            ),
            (
                "Normalised EBITDA",
                normalised_ebitda,
                "Maintainable earnings base used in the valuation analysis.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Normalisation impact at a glance", rows

    if section_key == "balance_sheet_summary":
        table = _section_table(sections, section_key)
        current_assets = _table_cell(_find_exact_table_row(table, "Total current assets"), 1)
        current_liabilities = _table_cell(_find_exact_table_row(table, "Total current liabilities"), 1)
        receivables = _table_cell(_find_exact_table_row(table, "Accounts receivable / trade debtors"), 1)
        stock = _table_cell(_find_exact_table_row(table, "Inventory / stock"), 1)
        fixed_assets = _table_cell(_find_exact_table_row(table, "Fixed assets (net)"), 1)
        accounts_payable = _table_cell(_find_exact_table_row(table, "Accounts payable / trade creditors"), 1)
        short_term_loans = _table_cell(_find_exact_table_row(table, "Short-term loans / current borrowings"), 1)
        long_term_loans = _table_cell(_find_exact_table_row(table, "Long-term loans / borrowings"), 1)
        total_assets = _table_cell(_find_exact_table_row(table, "Total assets"), 1)
        total_liabilities = _table_cell(_find_exact_table_row(table, "Total liabilities"), 1)
        net_assets = _table_cell(
            _find_exact_table_row(table, "Shareholders' equity / net assets")
            or _find_table_row(table, "shareholders", "equity"),
            1,
        )
        ntoa = _table_cell(_find_exact_table_row(table, "Net tangible operating assets (NTOA)"), 1)
        enterprise_mid = _table_cell(_find_table_row(table, "midpoint", "enterprise", "value"), 1)
        less_net_debt = _table_cell(_find_table_row(table, "less", "net", "debt"), 1)
        if not less_net_debt:
            less_net_debt = _table_cell(_find_table_row(table, "net", "debt"), 1)
        equity_mid = _table_cell(_find_table_row(table, "midpoint", "equity", "value"), 1)
        rows = [
            (
                "Operating asset detail",
                (
                    f"{receivables} receivables, {stock} stock and {fixed_assets} fixed assets"
                    if receivables and stock and fixed_assets
                    else ""
                ),
                "Shows the main operating asset items supporting the NTOA position.",
            ),
            (
                "Operating liability detail",
                accounts_payable,
                "Shows the main operating payable deducted in the NTOA position.",
            ),
            (
                "Loan detail",
                (
                    f"{short_term_loans} current loans and {long_term_loans} long-term loans"
                    if short_term_loans and long_term_loans
                    else ""
                ),
                "Shows borrowings separately from operating assets and liabilities.",
            ),
            (
                "NTOA position",
                ntoa,
                "Net tangible operating assets before cash, interest-bearing debt and surplus assets.",
            ),
            (
                "Current balance sheet position",
                (
                    f"{current_assets} current assets vs {current_liabilities} current liabilities"
                    if current_assets and current_liabilities
                    else ""
                ),
                "Summarises short-term balance-sheet scale before the valuation bridge.",
            ),
            (
                "Total asset and liability base",
                (
                    f"{total_assets} total assets vs {total_liabilities} total liabilities"
                    if total_assets and total_liabilities
                    else ""
                ),
                "Shows the reported balance-sheet base used as context, not as the primary valuation method.",
            ),
            (
                "Reported net assets",
                net_assets,
                "Book equity is shown as context and should not be read as the going-concern valuation conclusion.",
            ),
            (
                "Midpoint enterprise value",
                enterprise_mid,
                "Operating-business value before the debt, cash and surplus-asset bridge.",
            ),
            (
                "Net debt bridge",
                less_net_debt,
                "Debt exceeds cash by this amount, reducing the value attributable to shareholders.",
            ),
            (
                "Midpoint equity value",
                equity_mid,
                "Central shareholder-value indication after the bridge from enterprise value.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Enterprise-to-equity bridge", rows

    if section_key == "valuation_assumptions":
        table = _section_table(sections, section_key)
        if table is None:
            return None
        value_index = _column_index_by_terms(table, "value", default=1)
        source_index = _column_index_by_terms(table, "source", default=2)
        normalised_ebitda = _table_cell(_find_table_row(table, "normalised", "ebitda"), value_index)
        growth_assumption = _table_cell(_find_table_row(table, "revenue", "earnings", "growth"), value_index)
        if not growth_assumption:
            growth_assumption = _table_cell(_find_table_row(table, "revenue", "outlook"), value_index)

        source_cells = [
            _normalize_pdf_text(row[source_index]).strip().lower()
            for row in _table_rows(table)
            if len(row) > source_index and _normalize_pdf_text(row[source_index]).strip()
        ]
        public_count = sum(
            1
            for source in source_cells
            if any(
                marker in source
                for marker in (
                    "public",
                    "rbnz",
                    "reserve bank",
                    "damodaran",
                    "companies office",
                    "market",
                    "inflation",
                    "risk-free",
                )
            )
        )
        management_input_count = sum(
            1
            for source in source_cells
            if (
                "management-confirmed private input" in source
                or "management outlook" in source
                or "management-supplied" in source
                or "management input" in source
            )
        )
        model_count = sum(
            1
            for source in source_cells
            if any(
                marker in source
                for marker in (
                    "model convention",
                    "accountiq valuation model",
                    "accountiq-calculated",
                    "accountiq calculated",
                    "accountiq calculation",
                )
            )
        )
        rows = [
            (
                "Maintainable earnings base",
                normalised_ebitda,
                "Normalised EBITDA used as the valuation earnings base.",
            ),
            (
                "Growth assumption",
                growth_assumption,
                "Forecast growth assumption disclosed with its source.",
            ),
            (
                "Public research inputs",
                str(public_count) if public_count else "",
                "Assumptions supported by public market, inflation or discount-rate evidence.",
            ),
            (
                "Management-confirmed inputs",
                str(management_input_count) if management_input_count else "",
                "Management-supplied private inputs used for business-specific assumptions.",
            ),
            (
                "Technical model inputs",
                str(model_count) if model_count else "",
                "Valuation-model conventions disclosed with the assumption basis.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Assumption basis at a glance", rows

    if section_key == "wacc_assumptions":
        table = _section_table(sections, section_key)
        wacc_row = _find_table_row(table, "wacc")
        illiquidity_row = _find_table_row(table, "illiquidity", "discount")
        scenario_indexes = _scenario_column_indexes(table)
        high_wacc = _table_cell(wacc_row, scenario_indexes.get("high", 1))
        mid_wacc = _table_cell(wacc_row, scenario_indexes.get("mid", 2))
        low_wacc = _table_cell(wacc_row, scenario_indexes.get("low", 3))
        illiquidity_mid = _table_cell(illiquidity_row, scenario_indexes.get("mid", 2))
        rows = [
            (
                "High valuation discount rate",
                high_wacc,
                "Lower WACC means forecast cash flows are discounted less heavily, producing the upper valuation case.",
            ),
            (
                "Mid valuation discount rate",
                mid_wacc,
                "Base discount-rate case used for the central valuation conclusion.",
            ),
            (
                "Low valuation discount rate",
                low_wacc,
                "Higher WACC reflects more risk and produces the lower valuation case.",
            ),
            (
                "Illiquidity discount",
                illiquidity_mid,
                "Private-company marketability discount shown explicitly rather than hidden in the conclusion.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "How the discount rate drives the range", rows

    if section_key == "multiples_crosscheck":
        table = _section_table(sections, section_key)
        multiple_row = _find_table_row(table, "ev/ebitda")
        earnings_row = _find_table_row(table, "normalised", "ebitda")
        enterprise_value_row = _find_table_row(table, "indicated", "enterprise", "value")
        scenario_indexes = _scenario_column_indexes(table)
        low_index = scenario_indexes.get("low", 1)
        mid_index = scenario_indexes.get("mid", 2)
        high_index = scenario_indexes.get("high", 3)
        low_multiple = _table_cell(multiple_row, low_index)
        high_multiple = _table_cell(multiple_row, high_index)
        mid_earnings = _table_cell(earnings_row, mid_index) or _table_cell(earnings_row, low_index)
        low_value = _table_cell(enterprise_value_row, low_index)
        mid_value = _table_cell(enterprise_value_row, mid_index)
        high_value = _table_cell(enterprise_value_row, high_index)
        rows = [
            (
                "Market multiple range",
                f"{low_multiple} - {high_multiple}" if low_multiple and high_multiple else "",
                "Indicative EV/EBITDA range from researched comparable evidence.",
            ),
            (
                "Maintainable EBITDA applied",
                mid_earnings,
                "Earnings base used consistently across the market cross-check.",
            ),
            (
                "Implied enterprise value range",
                f"{low_value} - {high_value}" if low_value and high_value else "",
                "Reasonableness range used to cross-check, not replace, the primary DCF conclusion.",
            ),
            (
                "Midpoint market indication",
                mid_value,
                "Central market-multiple indication before the enterprise-to-equity bridge.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "How the market cross-check is used", rows

    if section_key == "dcf_analysis":
        table = _section_table(sections, section_key)
        cash_flow_schedule = _section_subtable(sections, section_key, "cash_flow_schedule")
        scenario_indexes = _scenario_column_indexes(table)
        high_index = scenario_indexes.get("high", 1)
        mid_index = scenario_indexes.get("mid", 2)
        low_index = scenario_indexes.get("low", 3)
        adjusted_enterprise_row = _find_table_row(table, "adjusted", "enterprise", "value")
        revenue_row = _find_table_row(cash_flow_schedule, "revenue")
        fcff_row = _find_table_row(cash_flow_schedule, "free", "cash", "flow", "firm")
        high_value = _table_cell(adjusted_enterprise_row, high_index)
        mid_value = _table_cell(adjusted_enterprise_row, mid_index)
        low_value = _table_cell(adjusted_enterprise_row, low_index)
        revenue_year_1 = _table_cell(revenue_row, 1)
        revenue_year_5 = _table_cell(revenue_row, 5)
        fcff_year_1 = _table_cell(fcff_row, 1)
        fcff_year_5 = _table_cell(fcff_row, 5)
        rows = [
            (
                "Adjusted enterprise value range",
                f"{low_value} - {high_value}" if low_value and high_value else "",
                "DCF valuation range after the private-company illiquidity adjustment.",
            ),
            (
                "Midpoint adjusted enterprise value",
                mid_value,
                "Central DCF indication before the enterprise-to-equity bridge.",
            ),
            (
                "Revenue forecast bridge",
                f"{revenue_year_1} to {revenue_year_5}" if revenue_year_1 and revenue_year_5 else "",
                "Mid-case revenue progression across the explicit five-year forecast period.",
            ),
            (
                "Free cash flow bridge",
                f"{fcff_year_1} to {fcff_year_5}" if fcff_year_1 and fcff_year_5 else "",
                "Mid-case free cash flow to firm after tax, capex and working-capital reinvestment.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "DCF forecast bridge at a glance", rows

    if section_key == "valuation_summary":
        table = _section_table(sections, section_key)
        if table is None:
            return None
        adjusted_ev_index = _column_index_by_terms(table, "adjusted", default=3)
        equity_value_index = _column_index_by_terms(table, "equity", default=4)
        dcf_high_row = _find_table_row(table, "dcf", "high")
        dcf_mid_row = _find_table_row(table, "dcf", "mid")
        dcf_low_row = _find_table_row(table, "dcf", "low")
        multiples_low_row = _find_table_row(table, "multiples", "low")
        multiples_mid_row = _find_table_row(table, "multiples", "mid")
        multiples_high_row = _find_table_row(table, "multiples", "high")

        dcf_low_adjusted_ev = _table_cell(dcf_low_row, adjusted_ev_index)
        dcf_high_adjusted_ev = _table_cell(dcf_high_row, adjusted_ev_index)
        dcf_mid_adjusted_ev = _table_cell(dcf_mid_row, adjusted_ev_index)
        dcf_mid_equity_value = _table_cell(dcf_mid_row, equity_value_index)
        multiples_low_equity_value = _table_cell(multiples_low_row, equity_value_index)
        multiples_high_equity_value = _table_cell(multiples_high_row, equity_value_index)
        multiples_mid_adjusted_ev = _table_cell(multiples_mid_row, adjusted_ev_index)

        dcf_mid_value = _money_value(dcf_mid_adjusted_ev)
        multiples_mid_value = _money_value(multiples_mid_adjusted_ev)
        midpoint_gap = ""
        if dcf_mid_value is not None and multiples_mid_value is not None:
            gap = dcf_mid_value - multiples_mid_value
            if gap:
                midpoint_gap = f"{_money_cell(abs(gap))} {'above' if gap > 0 else 'below'}"

        rows = [
            (
                "Primary DCF range",
                (
                    f"{dcf_low_adjusted_ev} - {dcf_high_adjusted_ev}"
                    if dcf_low_adjusted_ev and dcf_high_adjusted_ev
                    else ""
                ),
                "Primary enterprise-value range after the private-company illiquidity adjustment.",
            ),
            (
                "Midpoint equity value",
                dcf_mid_equity_value,
                "Central shareholder-value indication after the net-debt bridge.",
            ),
            (
                "Market cross-check range",
                (
                    f"{multiples_low_equity_value} - {multiples_high_equity_value}"
                    if multiples_low_equity_value and multiples_high_equity_value
                    else ""
                ),
                "Market multiples provide an independent reasonableness check, not the selected conclusion.",
            ),
            (
                "DCF vs multiple midpoint",
                midpoint_gap,
                "Shows where the primary DCF midpoint sits relative to the market cross-check midpoint.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Valuation range at a glance", rows

    if section_key == "sensitivity_and_risks":
        table = _section_table(sections, section_key)
        sensitivity_rows = _table_rows(table)
        if not sensitivity_rows:
            return None
        scenario_indexes = _scenario_column_indexes(table)
        mid_index = scenario_indexes.get("mid", 2)
        base_row = _find_table_row(table, "base")
        if not base_row and sensitivity_rows:
            base_row = sensitivity_rows[len(sensitivity_rows) // 2]
        base_mid_value = _table_cell(base_row, mid_index)

        value_cells: list[tuple[float, str]] = []
        for row in sensitivity_rows:
            for index in range(1, len(row)):
                cell = _table_cell(row, index)
                value = _money_value(cell)
                if value is not None:
                    value_cells.append((value, cell))
        downside_value = min(value_cells, key=lambda item: item[0])[1] if value_cells else ""
        upside_value = max(value_cells, key=lambda item: item[0])[1] if value_cells else ""

        growth_labels = [
            _normalize_pdf_text(row[0]).replace("- base", "").strip()
            for row in sensitivity_rows
            if row and _normalize_pdf_text(row[0]).strip()
        ]
        growth_range = (
            f"{growth_labels[0]} to {growth_labels[-1]}"
            if len(growth_labels) >= 2
            else (growth_labels[0] if growth_labels else "")
        )
        specific_risk_table = _section_subtable(sections, section_key, "specific_risk_factors")
        specific_risk_count = len(_table_rows(specific_risk_table))

        rows = [
            (
                "Base sensitivity case",
                base_mid_value,
                "Midpoint case using the base growth assumption and mid WACC scenario.",
            ),
            (
                "Quantified EV span",
                f"{downside_value} - {upside_value}" if downside_value and upside_value else "",
                "Full adjusted enterprise-value span across the WACC and growth matrix.",
            ),
            (
                "Growth cases tested",
                growth_range,
                "Growth sensitivity range tested without asking management for extra valuation inputs.",
            ),
            (
                "Specific risk factors",
                str(specific_risk_count) if specific_risk_count else "",
                "Qualitative risk factors carried into the report from the short management intake.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Sensitivity takeaway at a glance", rows

    if section_key == "comparable_evidence":
        table = _section_table(sections, section_key)
        evidence_rows = _table_rows(table)
        if not evidence_rows:
            return None
        url_count = _url_count_from_rows(evidence_rows)
        support_text = _sources_support_text(evidence_rows)
        market_multiple_supported = any(
            marker in support_text
            for marker in ("ev/ebitda", "ebitda benchmark", "market multiple", "multiple")
        )
        comparability_caveat = any(
            marker in support_text
            for marker in (
                "not directly comparable",
                "broad",
                "limitation",
                "more liquid",
                "corroboration",
            )
        )
        rows = [
            (
                "Evidence rows",
                str(len(evidence_rows)),
                "Public benchmark and context rows retained in the comparable evidence appendix.",
            ),
            (
                "Source URLs retained",
                str(url_count) if url_count else "",
                "Every evidence row should retain a URL so the reader can check the source trail.",
            ),
            (
                "Market multiple support",
                (
                    "Market evidence supports the EV/EBITDA cross-check"
                    if market_multiple_supported
                    else "No specific market-multiple support identified"
                ),
                "Explains whether researched public evidence supports the EV/EBITDA cross-check range.",
            ),
            (
                "Comparability caveat",
                (
                    "Limitations explained as a reasonableness check"
                    if comparability_caveat
                    else "No explicit comparability limitation identified"
                ),
                "Explains that public evidence is used for context and cross-checking, not as a direct private-company price.",
            ),
        ]
        rows = [row for row in rows if row[1]]
        if rows:
            return "Comparable evidence at a glance", rows

    if section_key == "sources":
        table = _section_table(sections, section_key)
        source_rows = _table_rows(table)
        if not source_rows:
            return None
        url_count = _url_count_from_rows(source_rows)
        support_text = _sources_support_text(source_rows)
        discount_rate_supported = any(
            marker in support_text
            for marker in ("risk-free", "discount-rate", "wacc", "equity risk", "beta")
        )
        terminal_growth_supported = any(
            marker in support_text
            for marker in ("inflation", "terminal-growth", "terminal growth")
        )
        company_context_supported = any(
            marker in support_text
            for marker in ("company", "profile", "public-profile", "companies office")
        )
        rows = [
            (
                "Public URLs retained",
                str(url_count),
                "Source links are retained so a reader can inspect the public evidence trail.",
            ),
            (
                "Discount-rate support",
                (
                    "Public sources retained for WACC inputs"
                    if discount_rate_supported
                    else "No public WACC source identified"
                ),
                "Explains whether public evidence supports the risk-free-rate, equity-risk-premium or beta inputs.",
            ),
            (
                "Terminal-growth support",
                (
                    "Inflation source retained for terminal growth"
                    if terminal_growth_supported
                    else "No inflation or terminal-growth source identified"
                ),
                "Explains whether public evidence supports inflation or long-term growth assumptions.",
            ),
            (
                "Business context support",
                (
                    "Public profile sources retained for business context"
                    if company_context_supported
                    else "No business-context public source identified"
                ),
                "Explains whether public sources support company-profile or market-context statements.",
            ),
        ]
        if url_count > 0:
            return "Source trail at a glance", rows

    if section_key == "disclaimer":
        content = sections.get(section_key, "")
        if isinstance(content, dict):
            narrative = str(content.get("narrative", "") or "")
        else:
            narrative = str(content or "")
        normalised = _normalize_pdf_text(narrative).strip().lower()
        if not normalised:
            return None

        purpose_only = "purpose" in normalised and any(
            marker in normalised for marker in ("solely", "stated")
        )
        advice_limited = any(
            marker in normalised
            for marker in ("does not constitute financial advice", "legal", "tax", "accounting advice")
        )
        input_reliance = any(
            marker in normalised
            for marker in ("owner", "financial records", "public sources", "supplied")
        )
        not_audited = "not been independently audited" in normalised or "not independently audited" in normalised
        third_party_limited = "third party" in normalised or "third-party" in normalised

        rows = [
            (
                "Intended use",
                "Stated purpose only" if purpose_only else "Report purpose",
                "Reliance is limited to the valuation purpose stated in the report.",
            ),
            (
                "Advice status",
                "Not advice" if advice_limited else "Read limitations",
                "The report is not a substitute for independent professional advice.",
            ),
            (
                "Information reliance",
                "Management and public inputs" if input_reliance else "Input-dependent",
                "Conclusions depend on management-supplied information, extracted financials and identified sources.",
            ),
            (
                "Verification status",
                "Not audited" if not_audited else "Not assurance",
                "The scope is an indicative valuation pack, not an audit or assurance engagement.",
            ),
            (
                "Third-party reliance",
                "No responsibility accepted" if third_party_limited else "Restricted",
                "Third parties should not rely on the report without their own advice and diligence.",
            ),
        ]
        return "Reliance at a glance", rows

    return None


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            "CoverKicker",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#B9D8F2"),
            spaceAfter=5 * mm,
            uppercase=True,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="Helvetica",
            fontSize=30,
            leading=33,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=7 * mm,
        ),
        "cover_company": ParagraphStyle(
            "CoverCompany",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.white,
            spaceAfter=10 * mm,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#CFE2F3"),
        ),
        "cover_brief_label": ParagraphStyle(
            "CoverBriefLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=5.8,
            leading=7.2,
            textColor=colors.HexColor("#B9D8F2"),
        ),
        "cover_brief_value": ParagraphStyle(
            "CoverBriefValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.0,
            leading=8.8,
            textColor=colors.white,
        ),
        "section_kicker": ParagraphStyle(
            "SectionKicker",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=BLUE,
            spaceAfter=2 * mm,
        ),
        "section_title": ParagraphStyle(
            "SectionTitle",
            parent=base["Heading1"],
            fontName="Helvetica",
            fontSize=23,
            leading=27,
            textColor=NAVY,
            spaceAfter=8 * mm,
        ),
        "subheading": ParagraphStyle(
            "Subheading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=NAVY,
            spaceAfter=2.5 * mm,
            keepWithNext=True,
        ),
        "highlight_label": ParagraphStyle(
            "HighlightLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.6,
            leading=8.0,
            textColor=BLUE,
        ),
        "highlight_value": ParagraphStyle(
            "HighlightValue",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12.5,
            textColor=NAVY,
        ),
        "highlight_note": ParagraphStyle(
            "HighlightNote",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.8,
            leading=8.2,
            textColor=MUTED,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=13,
            textColor=INK,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12.5,
            leftIndent=4 * mm,
            firstLineIndent=-3.5 * mm,
            textColor=INK,
            spaceAfter=1.2 * mm,
        ),
        "contents": ParagraphStyle(
            "Contents",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.2,
            leading=13,
            textColor=INK,
        ),
        "contents_number": ParagraphStyle(
            "ContentsNumber",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=13,
            textColor=BLUE,
        ),
        "toc_entry": ParagraphStyle(
            "TocEntry",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.4,
            leading=11.2,
            textColor=INK,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=0,
            spaceAfter=0,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.6,
            leading=9.5,
            textColor=colors.white,
        ),
        "table_header_compact": ParagraphStyle(
            "TableHeaderCompact",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.0,
            leading=8.2,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.6,
            textColor=INK,
        ),
        "table_cell_compact": ParagraphStyle(
            "TableCellCompact",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.0,
            leading=8.4,
            textColor=INK,
        ),
    }


def _cover_report_brief_table(
    *,
    company_name: str,
    report_label: str,
    report_id: int,
    report_type: str = "valuation_advisory",
    generated_at: str = "",
    valuation_purpose: str = "",
    demo_mode: bool = False,
    available_width: float,
    styles: dict,
) -> Table:
    """Return a compact professional front-cover details panel."""
    purpose = _normalize_pdf_text(valuation_purpose).strip() or "Not specified"
    report_date = report_display_date(generated_at)
    if report_type == "bank_credit_paper":
        reliance = (
            "Demo credit paper only - not for reliance."
            if demo_mode
            else "Indicative lender screening only; not credit approval or a lender commitment."
        )
        row_pairs = [
            (
                ("Prepared for", _normalize_pdf_text(company_name)),
                ("Prepared by", "AccountIQ"),
            ),
            (
                ("Report type", _normalize_pdf_text(report_label)),
                ("Reference", report_reference_code(report_id, report_type)),
            ),
            (
                ("Prepared date", report_date),
                ("Purpose", "Credit paper / lender screening"),
            ),
            (
                ("Credit posture", "Screening-only until diligence and bank approval"),
                ("Reliance", reliance),
            ),
        ]
    else:
        reliance = (
            "Demo data only - not for reliance."
            if demo_mode
            else "Indicative valuation support only; obtain independent professional advice before reliance."
        )

        row_pairs = [
            (
                ("Prepared for", _normalize_pdf_text(company_name)),
                ("Prepared by", "AccountIQ"),
            ),
            (
                ("Report type", _normalize_pdf_text(report_label)),
                ("Reference", report_reference_code(report_id, report_type)),
            ),
            (
                ("Valuation date", report_date),
                ("Purpose", purpose),
            ),
            (
                ("Basis of value", "Indicative fair-market value, going-concern basis"),
                ("Reliance", reliance),
            ),
        ]
    data = []
    for left_pair, right_pair in row_pairs:
        data.append(
            [
                Paragraph(html.escape(left_pair[0].upper()), styles["cover_brief_label"]),
                Paragraph(html.escape(left_pair[1]), styles["cover_brief_value"]),
                Paragraph(html.escape(right_pair[0].upper()), styles["cover_brief_label"]),
                Paragraph(html.escape(right_pair[1]), styles["cover_brief_value"]),
            ]
        )

    table = Table(
        data,
        colWidths=[
            available_width * 0.15,
            available_width * 0.35,
            available_width * 0.15,
            available_width * 0.35,
        ],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#12395E")),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#5F8DB4")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#355D82")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5.5),
        ("TOPPADDING", (0, 0), (-1, -1), 4.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.2),
    ]))
    return table


def _executive_highlights_table(
    highlights: list[tuple[str, str, str]],
    available_width: float,
    styles: dict,
) -> Table | None:
    """Return a compact executive-summary conclusion panel."""
    if not highlights:
        return None
    data = [
        [
            Paragraph("Conclusion", styles["table_header"]),
            Paragraph("Value", styles["table_header"]),
            Paragraph("Reader takeaway", styles["table_header"]),
        ]
    ]
    for label, value, note in highlights:
        data.append(
            [
                Paragraph(html.escape(_normalize_pdf_text(label)), styles["highlight_label"]),
                Paragraph(html.escape(_normalize_pdf_text(value)), styles["highlight_value"]),
                Paragraph(html.escape(_normalize_pdf_text(note)), styles["highlight_note"]),
            ]
        )

    table = Table(
        data,
        colWidths=[
            available_width * 0.26,
            available_width * 0.30,
            available_width * 0.44,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#BFDBFE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#EFF6FF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for index in range(2, len(data), 2):
        commands.append(("BACKGROUND", (0, index), (-1, index), colors.white))
    table.setStyle(TableStyle(commands))
    return table


class _ValuationRangeVisualFlowable(Flowable):
    """Draw a compact low/mid/high valuation range graphic in the PDF."""

    def __init__(
        self,
        rows: list[dict[str, object]],
        available_width: float,
        *,
        title: str = "Valuation range visual",
        subtitle: str = VALUATION_RANGE_VISUAL_SUBTITLE,
        midpoint_prefix: str = "Mid",
    ):
        super().__init__()
        self.rows = rows
        self.width = available_width
        self.title = title
        self.subtitle = subtitle
        self.midpoint_prefix = midpoint_prefix
        self.height = 19 * mm + (18 * mm * len(rows))

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self) -> None:
        if not self.rows:
            return

        canvas = self.canv
        width = self.width
        height = self.height
        values = [
            float(row[key])
            for row in self.rows
            for key in ("low_value", "mid_value", "high_value")
            if row.get(key) is not None
        ]
        if not values:
            return

        scale_min = min(values)
        scale_max = max(values)
        if scale_min == scale_max:
            scale_min *= 0.95
            scale_max *= 1.05
        padding = (scale_max - scale_min) * 0.08
        scale_min -= padding
        scale_max += padding
        scale_span = scale_max - scale_min or 1

        def x_position(value: object) -> float:
            number = float(value)
            return bar_left + ((number - scale_min) / scale_span) * bar_width

        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
        canvas.setFillColor(colors.HexColor("#F8FBFF"))
        canvas.roundRect(0, 0, width, height, 6, stroke=1, fill=1)

        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 8.4)
        canvas.drawString(8 * mm, height - 8 * mm, self.title)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.6)
        canvas.drawString(8 * mm, height - 12 * mm, self.subtitle)

        label_width = min(48 * mm, width * 0.30)
        bar_left = label_width + 12 * mm
        bar_right = width - 12 * mm
        bar_width = max(45 * mm, bar_right - bar_left)
        row_top = height - 23 * mm

        for index, row in enumerate(self.rows):
            y = row_top - index * 18 * mm
            low_x = x_position(row["low_value"])
            mid_x = x_position(row["mid_value"])
            high_x = x_position(row["high_value"])

            canvas.setFillColor(NAVY)
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.drawString(8 * mm, y + 3.8 * mm, _normalize_pdf_text(row.get("label", "")))
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.8)
            note = _normalize_pdf_text(row.get("note", ""))
            canvas.drawString(8 * mm, y - 0.5 * mm, note[:76])

            canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
            canvas.setLineWidth(0.7)
            canvas.line(bar_left, y + 2 * mm, bar_right, y + 2 * mm)
            canvas.setStrokeColor(BLUE)
            canvas.setLineWidth(5.0)
            canvas.line(low_x, y + 2 * mm, high_x, y + 2 * mm)
            canvas.setFillColor(colors.white)
            canvas.setStrokeColor(NAVY)
            canvas.setLineWidth(1.2)
            canvas.circle(mid_x, y + 2 * mm, 2.4, stroke=1, fill=1)

            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.8)
            canvas.drawCentredString(low_x, y - 4 * mm, _normalize_pdf_text(row.get("low_label", "")))
            canvas.drawCentredString(high_x, y - 4 * mm, _normalize_pdf_text(row.get("high_label", "")))
            canvas.setFillColor(NAVY)
            canvas.setFont("Helvetica-Bold", 6.2)
            canvas.drawCentredString(
                mid_x,
                y + 6.2 * mm,
                f"{self.midpoint_prefix} {_normalize_pdf_text(row.get('mid_label', ''))}",
            )

        canvas.restoreState()


def _valuation_range_visual_flowable(
    sections: dict,
    available_width: float,
) -> _ValuationRangeVisualFlowable | None:
    visual = valuation_range_visual(sections)
    if visual is None:
        return None
    _title, rows = visual
    return _ValuationRangeVisualFlowable(rows, available_width)


def _sensitivity_spread_visual_flowable(
    sections: dict,
    available_width: float,
) -> _ValuationRangeVisualFlowable | None:
    visual = sensitivity_spread_visual(sections)
    if visual is None:
        return None
    _title, rows = visual
    return _ValuationRangeVisualFlowable(
        rows,
        available_width,
        title="Sensitivity spread visual",
        subtitle=SENSITIVITY_SPREAD_VISUAL_SUBTITLE,
        midpoint_prefix="Base",
    )


def _normalised_ebitda_bridge_visual_flowable(
    sections: dict,
    available_width: float,
    styles: dict,
) -> Table | None:
    visual = normalised_ebitda_bridge_visual(sections)
    if visual is None:
        return None
    title, row = visual
    inner_width = max(available_width - 16, available_width * 0.92)

    def card(label: str, value: object, note: str) -> list[Paragraph]:
        return [
            Paragraph(html.escape(_normalize_pdf_text(label)), styles["highlight_label"]),
            Paragraph(html.escape(_normalize_pdf_text(value)), styles["highlight_value"]),
            Paragraph(html.escape(_normalize_pdf_text(note)), styles["highlight_note"]),
        ]

    bridge_table = Table(
        [
            [
                card(
                    "Uploaded EBITDA basis",
                    row["uploaded_ebitda_label"],
                    "Starting earnings base from the uploaded financial statements.",
                ),
                Paragraph("+", styles["highlight_value"]),
                card(
                    "Net normalisation",
                    row["net_adjustment_label"],
                    row["adjustment_note"],
                ),
                Paragraph("=", styles["highlight_value"]),
                card(
                    "Normalised EBITDA",
                    row["normalised_ebitda_label"],
                    "Maintainable earnings base carried into DCF and market-multiple checks.",
                ),
            ],
            [
                card(
                    "Owner review",
                    row["adjustment_count_label"],
                    "The earnings bridge comes from the earnings-adjustment review and uploaded accounts.",
                ),
                "",
                card(
                    "Source basis",
                    "Accounts + review",
                    "The bridge is calculated from uploaded accounts and confirmed adjustment rows.",
                ),
                "",
                card(
                    "Valuation use",
                    "DCF and multiples",
                    "The same normalised EBITDA is used consistently across valuation methods.",
                ),
            ],
        ],
        colWidths=[
            inner_width * 0.30,
            inner_width * 0.05,
            inner_width * 0.30,
            inner_width * 0.05,
            inner_width * 0.30,
        ],
        hAlign="LEFT",
    )
    bridge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#BFDBFE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (3, 0), (3, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    wrapper = Table(
        [
            [Paragraph(html.escape(title), styles["subheading"])],
            [Paragraph(html.escape(_normalize_pdf_text(row["note"])), styles["highlight_note"])],
            [bridge_table],
        ],
        colWidths=[available_width],
        hAlign="LEFT",
    )
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return wrapper


def _equity_bridge_visual_flowable(
    sections: dict,
    available_width: float,
    styles: dict,
) -> Table | None:
    visual = equity_bridge_visual(sections)
    if visual is None:
        return None
    title, row = visual
    inner_width = max(available_width - 16, available_width * 0.92)

    def card(label: str, value: object, note: str) -> list[Paragraph]:
        return [
            Paragraph(html.escape(_normalize_pdf_text(label)), styles["highlight_label"]),
            Paragraph(html.escape(_normalize_pdf_text(value)), styles["highlight_value"]),
            Paragraph(html.escape(_normalize_pdf_text(note)), styles["highlight_note"]),
        ]

    bridge_table = Table(
        [
            [
                card(
                    "Midpoint enterprise value",
                    row["enterprise_label"],
                    "Operating-business value before debt, cash and surplus assets.",
                ),
                Paragraph("-", styles["highlight_value"]),
                card(
                    "Less net debt",
                    row["net_debt_label"],
                    "Interest-bearing debt less available cash.",
                ),
                Paragraph("+", styles["highlight_value"]),
                card(
                    "Surplus assets",
                    row["surplus_label"],
                    "Separately identified non-operating assets added back.",
                ),
                Paragraph("=", styles["highlight_value"]),
                card(
                    "Midpoint equity value",
                    row["equity_label"],
                    "Indicative shareholder value after the balance-sheet bridge.",
                ),
            ]
        ],
        colWidths=[
            inner_width * 0.22,
            inner_width * 0.04,
            inner_width * 0.18,
            inner_width * 0.04,
            inner_width * 0.18,
            inner_width * 0.04,
            inner_width * 0.30,
        ],
        hAlign="LEFT",
    )
    bridge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#BFDBFE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (3, 0), (3, 0), "CENTER"),
        ("ALIGN", (5, 0), (5, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    wrapper = Table(
        [
            [Paragraph(html.escape(title), styles["subheading"])],
            [Paragraph(html.escape(_normalize_pdf_text(row["note"])), styles["highlight_note"])],
            [bridge_table],
        ],
        colWidths=[available_width],
        hAlign="LEFT",
    )
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return wrapper


def _dcf_value_build_visual_flowable(
    sections: dict,
    available_width: float,
    styles: dict,
) -> Table | None:
    visual = dcf_value_build_visual(sections)
    if visual is None:
        return None
    title, row = visual
    inner_width = max(available_width - 16, available_width * 0.92)

    def card(label: str, value: object, note: str) -> list[Paragraph]:
        return [
            Paragraph(html.escape(_normalize_pdf_text(label)), styles["highlight_label"]),
            Paragraph(html.escape(_normalize_pdf_text(value)), styles["highlight_value"]),
            Paragraph(html.escape(_normalize_pdf_text(note)), styles["highlight_note"]),
        ]

    def equation_row(
        left: list[Paragraph],
        operator_1: str,
        middle: list[Paragraph],
        operator_2: str,
        right: list[Paragraph],
    ) -> Table:
        table = Table(
            [[left, Paragraph(operator_1, styles["highlight_value"]), middle, Paragraph(operator_2, styles["highlight_value"]), right]],
            colWidths=[
                inner_width * 0.29,
                inner_width * 0.055,
                inner_width * 0.29,
                inner_width * 0.055,
                inner_width * 0.31,
            ],
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
            ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#BFDBFE")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DEE8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("ALIGN", (3, 0), (3, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    row_one = equation_row(
        card(
            "PV explicit FCFF",
            row["explicit_fcff_label"],
            "Present value of the five-year forecast cash flows.",
        ),
        "+",
        card(
            "PV terminal value",
            row["terminal_value_label"],
            "Implied continuing value after the explicit forecast period.",
        ),
        "=",
        card(
            "EV before illiquidity",
            row["ev_before_illiquidity_label"],
            "Mid-case DCF enterprise value before the private-company discount.",
        ),
    )
    row_two = equation_row(
        card(
            "EV before illiquidity",
            row["ev_before_illiquidity_label"],
            "Starting point for the marketability adjustment.",
        ),
        "-",
        card(
            "Illiquidity discount",
            row["illiquidity_discount_label"],
            "Explicit private-company marketability adjustment.",
        ),
        "=",
        card(
            "Adjusted enterprise value",
            row["adjusted_ev_label"],
            "Mid-case operating-business value used in the valuation summary.",
        ),
    )

    wrapper = Table(
        [
            [Paragraph(html.escape(title), styles["subheading"])],
            [Paragraph(html.escape(_normalize_pdf_text(row["note"])), styles["highlight_note"])],
            [row_one],
            [row_two],
        ],
        colWidths=[available_width],
        hAlign="LEFT",
    )
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return wrapper


def _wacc_build_visual_flowable(
    sections: dict,
    available_width: float,
    styles: dict,
) -> Table | None:
    visual = wacc_build_visual(sections)
    if visual is None:
        return None
    title, row = visual
    inner_width = max(available_width - 16, available_width * 0.92)

    def card(label: str, value: object, note: str) -> list[Paragraph]:
        return [
            Paragraph(html.escape(_normalize_pdf_text(label)), styles["highlight_label"]),
            Paragraph(html.escape(_normalize_pdf_text(value)), styles["highlight_value"]),
            Paragraph(html.escape(_normalize_pdf_text(note)), styles["highlight_note"]),
        ]

    build_table = Table(
        [
            [
                card(
                    "Risk-free rate",
                    row["risk_free_label"],
                    "Public market base return before company and sector risk.",
                ),
                Paragraph("+", styles["highlight_value"]),
                card(
                    "Beta-adjusted risk premium",
                    row["beta_adjusted_premium_label"],
                    row["premium_note"],
                ),
                Paragraph("=", styles["highlight_value"]),
                card(
                    "Mid WACC",
                    row["wacc_label"],
                    "Discount rate applied to the mid-case forecast cash flows.",
                ),
            ],
            [
                card(
                    "Illiquidity discount",
                    row.get("illiquidity_label", ""),
                    "Separate private-company marketability adjustment applied after DCF value.",
                ),
                "",
                card(
                    "Source inputs",
                    f"ERP {row['erp_label']} / beta {row['beta_label']}",
                    "Public research inputs are disclosed as part of the valuation evidence trail.",
                ),
                "",
                card(
                    "Technical inputs",
                    "Derived",
                    "WACC, beta and equity-risk-premium assumptions are derived and disclosed as valuation-model inputs.",
                ),
            ],
        ],
        colWidths=[
            inner_width * 0.30,
            inner_width * 0.05,
            inner_width * 0.30,
            inner_width * 0.05,
            inner_width * 0.30,
        ],
        hAlign="LEFT",
    )
    build_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#BFDBFE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (3, 0), (3, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    wrapper = Table(
        [
            [Paragraph(html.escape(title), styles["subheading"])],
            [Paragraph(html.escape(_normalize_pdf_text(row["note"])), styles["highlight_note"])],
            [build_table],
        ],
        colWidths=[available_width],
        hAlign="LEFT",
    )
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return wrapper


def _implied_multiple_reconciliation_flowable(
    sections: dict,
    available_width: float,
    styles: dict,
) -> Table | None:
    visual = implied_multiple_reconciliation(sections)
    if visual is None:
        return None
    title, row = visual

    def card(label: str, value: object, note: str) -> list[Paragraph]:
        return [
            Paragraph(html.escape(_normalize_pdf_text(label)), styles["highlight_label"]),
            Paragraph(html.escape(_normalize_pdf_text(value)), styles["highlight_value"]),
            Paragraph(html.escape(_normalize_pdf_text(note)), styles["highlight_note"]),
        ]

    cards = [
        card(
            "Normalised EBITDA",
            row["normalised_ebitda_label"],
            "Maintainable earnings base used for the market and DCF implied multiple checks.",
        ),
        card(
            "Market EV/EBITDA range",
            row["market_range_label"],
            "Researched market range used as a reasonableness cross-check.",
        ),
        card(
            "DCF post-illiquidity range",
            row["dcf_post_range_label"],
            "Primary DCF adjusted enterprise-value range expressed as an EV/EBITDA multiple.",
        ),
        card(
            "DCF pre-illiquidity range",
            row["dcf_pre_range_label"],
            "DCF enterprise-value range before the private-company marketability discount.",
        ),
        card(
            "DCF midpoint multiple",
            row["dcf_post_mid_label"],
            "Midpoint adjusted DCF enterprise value divided by normalised EBITDA.",
        ),
        card(
            "Cross-check tension",
            row.get("midpoint_gap_label", "") or "In range",
            "Shows whether the selected DCF midpoint sits above or below the market midpoint.",
        ),
    ]
    card_table = Table(
        [cards[:3], cards[3:]],
        colWidths=[available_width * 0.333, available_width * 0.333, available_width * 0.334],
        hAlign="LEFT",
    )
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#BFDBFE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    wrapper = Table(
        [
            [Paragraph(html.escape(title), styles["subheading"])],
            [Paragraph(html.escape(_normalize_pdf_text(row["note"])), styles["highlight_note"])],
            [card_table],
        ],
        colWidths=[available_width],
        hAlign="LEFT",
    )
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return wrapper


def _valuation_method_selection_flowable(
    sections: dict,
    available_width: float,
    styles: dict,
) -> Table | None:
    visual = valuation_method_selection(sections)
    if visual is None:
        return None
    title, rows = visual
    if not rows:
        return None

    table_rows = [
        [
            Paragraph("Approach", styles["table_header"]),
            Paragraph("Role", styles["table_header"]),
            Paragraph("Why this treatment is appropriate", styles["table_header"]),
            Paragraph("Report treatment", styles["table_header"]),
        ]
    ]
    for row in rows:
        table_rows.append(
            [
                Paragraph(html.escape(_normalize_pdf_text(row.get("approach", ""))), styles["table_cell"]),
                Paragraph(html.escape(_normalize_pdf_text(row.get("role", ""))), styles["table_cell"]),
                Paragraph(html.escape(_normalize_pdf_text(row.get("rationale", ""))), styles["table_cell"]),
                Paragraph(html.escape(_normalize_pdf_text(row.get("report_treatment", ""))), styles["table_cell"]),
            ]
        )

    selection_table = Table(
        table_rows,
        colWidths=[
            available_width * 0.22,
            available_width * 0.19,
            available_width * 0.31,
            available_width * 0.28,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )
    selection_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7DEE8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    wrapper = Table(
        [
            [Paragraph(html.escape(title), styles["subheading"])],
            [
                Paragraph(
                    "Explains why the report adopts DCF, uses market multiples as a cross-check and does not rely on a net-asset method.",
                    styles["highlight_note"],
                )
            ],
            [selection_table],
        ],
        colWidths=[available_width],
        hAlign="LEFT",
    )
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return wrapper


class _FinancialTrendVisualFlowable(Flowable):
    """Draw a compact revenue and EBITDA trend graphic in the PDF."""

    def __init__(self, rows: list[dict[str, object]], available_width: float):
        super().__init__()
        self.rows = rows
        self.width = available_width
        self.height = 23 * mm + (12 * mm * len(rows))

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self) -> None:
        if not self.rows:
            return

        canvas = self.canv
        width = self.width
        height = self.height
        max_value = max(
            float(row[key])
            for row in self.rows
            for key in ("revenue_value", "ebitda_value")
            if row.get(key) is not None
        )
        if max_value <= 0:
            return

        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
        canvas.setFillColor(colors.HexColor("#F8FBFF"))
        canvas.roundRect(0, 0, width, height, 6, stroke=1, fill=1)

        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 8.4)
        canvas.drawString(8 * mm, height - 8 * mm, "Financial trend visual")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.6)
        canvas.drawString(8 * mm, height - 12 * mm, FINANCIAL_TREND_VISUAL_SUBTITLE)

        legend_x = width - 47 * mm
        canvas.setFillColor(BLUE)
        canvas.rect(legend_x, height - 8.5 * mm, 4 * mm, 2.2 * mm, stroke=0, fill=1)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.2)
        canvas.drawString(legend_x + 5 * mm, height - 8.5 * mm, "Revenue")
        canvas.setFillColor(colors.HexColor("#2E7D32"))
        canvas.rect(legend_x + 25 * mm, height - 8.5 * mm, 4 * mm, 2.2 * mm, stroke=0, fill=1)
        canvas.setFillColor(MUTED)
        canvas.drawString(legend_x + 30 * mm, height - 8.5 * mm, "EBITDA")

        label_width = min(38 * mm, width * 0.24)
        bar_left = label_width + 11 * mm
        bar_right = width - 12 * mm
        bar_width = max(45 * mm, bar_right - bar_left)
        row_top = height - 23 * mm

        for index, row in enumerate(self.rows):
            y = row_top - index * 12 * mm
            period = _normalize_pdf_text(row.get("period", ""))
            revenue_label = _normalize_pdf_text(row.get("revenue_label", ""))
            ebitda_label = _normalize_pdf_text(row.get("ebitda_label", ""))
            revenue_width = (float(row["revenue_value"]) / max_value) * bar_width
            ebitda_width = (float(row["ebitda_value"]) / max_value) * bar_width

            canvas.setFillColor(NAVY)
            canvas.setFont("Helvetica-Bold", 6.8)
            canvas.drawString(8 * mm, y + 2.2 * mm, period)
            margin_label = _normalize_pdf_text(row.get("margin_label", ""))
            if margin_label:
                canvas.setFillColor(MUTED)
                canvas.setFont("Helvetica", 5.5)
                canvas.drawString(8 * mm, y - 1.4 * mm, f"EBITDA margin {margin_label}")

            for offset, bar_colour, label, fill_width in (
                (2.6 * mm, BLUE, revenue_label, revenue_width),
                (-1.8 * mm, colors.HexColor("#2E7D32"), ebitda_label, ebitda_width),
            ):
                canvas.setFillColor(colors.HexColor("#E6ECF3"))
                canvas.roundRect(bar_left, y + offset, bar_width, 2.4 * mm, 1.2 * mm, stroke=0, fill=1)
                canvas.setFillColor(bar_colour)
                canvas.roundRect(bar_left, y + offset, fill_width, 2.4 * mm, 1.2 * mm, stroke=0, fill=1)
                canvas.setFillColor(NAVY if bar_colour == BLUE else colors.HexColor("#245A28"))
                canvas.setFont("Helvetica-Bold", 5.8)
                label_x = min(bar_left + fill_width + 2 * mm, bar_right - 19 * mm)
                canvas.drawString(label_x, y + offset + 0.2 * mm, label)

        canvas.restoreState()


def _financial_trend_visual_flowable(
    sections: dict,
    available_width: float,
) -> _FinancialTrendVisualFlowable | None:
    visual = financial_trend_visual(sections)
    if visual is None:
        return None
    _title, rows = visual
    return _FinancialTrendVisualFlowable(rows, available_width)


class _MarketLineChartFlowable(Flowable):
    """Draw a sourced, report-ready line chart from quarterly intelligence."""

    _palette = (
        colors.HexColor("#1769AA"),
        colors.HexColor("#D97706"),
        colors.HexColor("#2E7D32"),
        colors.HexColor("#7C3AED"),
    )

    def __init__(self, chart: dict, available_width: float):
        super().__init__()
        self.chart = chart
        self.width = available_width
        self.height = 69 * mm

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self) -> None:
        series_list = [
            series
            for series in (self.chart.get("series") or [])
            if isinstance(series, dict) and isinstance(series.get("values"), list)
        ]
        values: list[float] = []
        for series in series_list:
            for point in series.get("values") or []:
                try:
                    values.append(float(point.get("value")))
                except (AttributeError, TypeError, ValueError):
                    continue
        if len(values) < 2:
            return

        canvas = self.canv
        width, height = self.width, self.height
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#F8FBFF"))
        canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
        canvas.roundRect(0, 0, width, height, 6, stroke=1, fill=1)

        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 8.2)
        canvas.drawString(
            7 * mm,
            height - 8 * mm,
            _normalize_pdf_text(str(self.chart.get("title") or "Market trend"))[:88],
        )
        subtitle = _normalize_pdf_text(str(self.chart.get("subtitle") or ""))
        if subtitle:
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 6.1)
            canvas.drawString(7 * mm, height - 12 * mm, subtitle[:125])

        legend_y = height - 17 * mm
        legend_x = 7 * mm
        for index, series in enumerate(series_list):
            colour = self._palette[index % len(self._palette)]
            canvas.setFillColor(colour)
            canvas.rect(legend_x, legend_y, 4 * mm, 1.7 * mm, fill=1, stroke=0)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.8)
            label = _normalize_pdf_text(str(series.get("name") or "Series"))[:32]
            canvas.drawString(legend_x + 5 * mm, legend_y, label)
            legend_x += min(50 * mm, 12 * mm + len(label) * 1.8 * mm)

        chart_left = 18 * mm
        chart_right = width - 7 * mm
        chart_bottom = 14 * mm
        chart_top = height - 22 * mm
        chart_width = chart_right - chart_left
        chart_height = chart_top - chart_bottom
        minimum, maximum = min(values), max(values)
        all_nonnegative = minimum >= 0
        all_nonpositive = maximum <= 0
        if all_nonnegative:
            minimum = 0.0
        if all_nonpositive:
            maximum = 0.0
        if abs(maximum - minimum) < 1e-9:
            maximum = minimum + 1.0
        padding = (maximum - minimum) * 0.08
        if not all_nonnegative:
            minimum -= padding
        if not all_nonpositive:
            maximum += padding
        span = maximum - minimum

        for grid_index in range(5):
            ratio = grid_index / 4
            y_value = chart_top - ratio * chart_height
            label_value = maximum - ratio * span
            canvas.setStrokeColor(colors.HexColor("#DFE5EC"))
            canvas.setLineWidth(0.4)
            canvas.line(chart_left, y_value, chart_right, y_value)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.2)
            label = (
                f"{label_value / 1000:,.0f}k"
                if abs(label_value) >= 1000
                else f"{label_value:,.1f}"
            )
            canvas.drawRightString(chart_left - 2 * mm, y_value - 1.2 * mm, label)

        periods: list[str] = []
        for series_index, series in enumerate(series_list):
            points: list[tuple[str, float]] = []
            for point in series.get("values") or []:
                try:
                    points.append(
                        (
                            _normalize_pdf_text(str(point.get("period") or "")),
                            float(point.get("value")),
                        )
                    )
                except (AttributeError, TypeError, ValueError):
                    continue
            if len(points) < 2:
                continue
            if not periods:
                periods = [period for period, _value in points]
            colour = self._palette[series_index % len(self._palette)]
            canvas.setStrokeColor(colour)
            canvas.setFillColor(colour)
            canvas.setLineWidth(1.3)
            previous: tuple[float, float] | None = None
            for point_index, (_period, value) in enumerate(points):
                x_value = chart_left + chart_width * point_index / max(len(points) - 1, 1)
                y_value = chart_bottom + ((value - minimum) / span) * chart_height
                if previous is not None:
                    canvas.line(previous[0], previous[1], x_value, y_value)
                canvas.circle(x_value, y_value, 1.15 * mm, fill=1, stroke=0)
                previous = (x_value, y_value)

        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 4.9)
        for index, period in enumerate(periods):
            if len(periods) > 8 and index not in {0, len(periods) - 1} and index % 2:
                continue
            x_value = chart_left + chart_width * index / max(len(periods) - 1, 1)
            canvas.drawCentredString(x_value, chart_bottom - 4 * mm, period)
        unit = _normalize_pdf_text(str(self.chart.get("unit") or ""))
        if unit:
            canvas.drawString(7 * mm, chart_top + 1 * mm, unit[:28])
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
                for source_id in self.chart.get("source_ids") or []
            )
        )
        if sources:
            canvas.drawRightString(
                chart_right,
                4 * mm,
                f"Source: {', '.join(sources)}"[:110],
            )
        canvas.restoreState()


def _market_chart_flowables(
    content: dict,
    available_width: float,
) -> list[_MarketLineChartFlowable]:
    charts = content.get("market_charts") if isinstance(content, dict) else None
    if not isinstance(charts, list):
        return []
    return [
        _MarketLineChartFlowable(chart, available_width)
        for chart in charts
        if isinstance(chart, dict) and isinstance(chart.get("series"), list)
    ]


def _reader_guidance_table(
    guidance_rows: list[tuple[str, str, str]],
    available_width: float,
    styles: dict,
) -> Table | None:
    """Return a compact table that explains how to read a valuation schedule."""
    if not guidance_rows:
        return None
    data = [
        [
            Paragraph("Interpretation", styles["table_header"]),
            Paragraph("Value", styles["table_header"]),
            Paragraph("Meaning", styles["table_header"]),
        ]
    ]
    for label, value, note in guidance_rows:
        data.append(
            [
                Paragraph(html.escape(_normalize_pdf_text(label)), styles["highlight_label"]),
                Paragraph(html.escape(_normalize_pdf_text(value)), styles["highlight_value"]),
                Paragraph(html.escape(_normalize_pdf_text(note)), styles["highlight_note"]),
            ]
        )

    table = Table(
        data,
        colWidths=[
            available_width * 0.26,
            available_width * 0.30,
            available_width * 0.44,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F3B63")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#D7DEE8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FBFF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for index in range(2, len(data), 2):
        commands.append(("BACKGROUND", (0, index), (-1, index), colors.white))
    table.setStyle(TableStyle(commands))
    return table


def write_report_pdf(
    output_path: Path,
    *,
    company_name: str,
    report_label: str,
    report_type: str = "",
    valuation_purpose: str = "",
    intake_answers: dict | None = None,
    sections: dict,
    section_order: list[str],
    section_titles: dict[str, str],
    report_id: int,
    generated_at: str,
    demo_mode: bool = False,
) -> None:
    """Build a paginated A4 report from structured report content."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".tmp.pdf")
    page_width, page_height = A4
    left = 18 * mm
    right = 18 * mm
    top = 18 * mm
    bottom = 17 * mm
    available_width = page_width - left - right
    styles = _styles()
    is_credit_paper = report_type == "bank_credit_paper"
    cover_snapshot = _cover_valuation_snapshot(sections) if report_type == "valuation_advisory" else None
    reference_code = report_reference_code(report_id, report_type)

    doc = _AccountIQDocTemplate(
        str(temporary_path),
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title=f"{_normalize_pdf_text(report_label)} - {_normalize_pdf_text(company_name)}",
        author="AccountIQ",
        subject=(
            "Indicative lender credit paper"
            if is_credit_paper
            else "Indicative business valuation"
        ),
    )

    def cover_page(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#F8FBFF"))
        canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.setFillColor(PALE_BLUE)
        canvas.rect(0, 0, page_width, page_height * 0.48, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, page_width, page_height * 0.37, fill=1, stroke=0)
        canvas.setFillColor(BLUE)
        canvas.rect(left, page_height - 31 * mm, 25 * mm, 2 * mm, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(left, page_height - 40 * mm, "AccountIQ")

        strip_x = left
        strip_y = 207 * mm
        strip_w = page_width - left - right
        strip_h = 25 * mm
        canvas.setFillColor(colors.white)
        canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
        canvas.setLineWidth(0.55)
        canvas.roundRect(strip_x, strip_y, strip_w, strip_h, 4 * mm, fill=1, stroke=1)
        canvas.setFillColor(BLUE)
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawString(strip_x + 7 * mm, strip_y + strip_h - 7 * mm, "REPORT BASIS")
        cover_basis_items = (
            [
                ("Uploaded financials", "Trading, EBITDA and balance sheet"),
                ("Lender inputs", "LVR, funding cost, term and security"),
                ("Public client context", "Business and sector research"),
                ("Debt-capacity model", "DSCR, ICR, leverage and NTOA"),
            ]
            if is_credit_paper
            else [
                ("Uploaded financials", "Revenue, earnings and balance sheet"),
                ("Five private inputs", "Only facts management can confirm"),
                ("Public-source trail", "Research URLs retained for review"),
                ("AccountIQ model", "DCF, WACC, multiples and sensitivity"),
            ]
        )
        item_width = (strip_w - 14 * mm) / len(cover_basis_items)
        item_y = strip_y + 7.6 * mm
        for index, (label, note) in enumerate(cover_basis_items):
            x_pos = strip_x + 7 * mm + index * item_width
            if index:
                canvas.setStrokeColor(colors.HexColor("#D7DEE8"))
                canvas.line(x_pos - 4 * mm, strip_y + 5 * mm, x_pos - 4 * mm, strip_y + strip_h - 11 * mm)
            canvas.setFillColor(NAVY)
            canvas.setFont("Helvetica-Bold", 7.0)
            canvas.drawString(x_pos, item_y + 4.3 * mm, label)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 5.8)
            canvas.drawString(x_pos, item_y, note)
        if cover_snapshot:
            scenario_headers, snapshot_rows = cover_snapshot
            card_x = left
            card_y = 126 * mm
            card_w = page_width - left - right
            card_h = 56 * mm
            canvas.setFillColor(colors.white)
            canvas.setStrokeColor(colors.HexColor("#C8D6E5"))
            canvas.setLineWidth(0.7)
            canvas.roundRect(card_x, card_y, card_w, card_h, 5 * mm, fill=1, stroke=1)

            canvas.setFillColor(BLUE)
            canvas.rect(card_x, card_y + card_h - 8 * mm, card_w, 8 * mm, fill=1, stroke=0)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.drawString(card_x + 7 * mm, card_y + card_h - 5.4 * mm, "VALUATION SNAPSHOT")

            metric_x = card_x + 7 * mm
            scenario_width = 34 * mm
            scenario_x = [
                card_x + card_w - (len(scenario_headers) - index) * scenario_width - 3 * mm
                for index in range(len(scenario_headers))
            ]
            header_y = card_y + card_h - 17 * mm
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica-Bold", 6.8)
            canvas.drawString(metric_x, header_y, "Output")
            for label, x_pos in zip(scenario_headers, scenario_x, strict=False):
                canvas.drawRightString(x_pos + scenario_width - 5 * mm, header_y, label)

            row_y = header_y - 10 * mm
            for label, values in snapshot_rows:
                canvas.setStrokeColor(LINE)
                canvas.line(metric_x, row_y + 5.5 * mm, card_x + card_w - 7 * mm, row_y + 5.5 * mm)
                canvas.setFillColor(INK)
                canvas.setFont("Helvetica", 7.4)
                canvas.drawString(metric_x, row_y, label[:42])
                canvas.setFont("Helvetica-Bold", 8.1)
                for value, x_pos in zip(values, scenario_x, strict=False):
                    canvas.drawRightString(x_pos + scenario_width - 5 * mm, row_y, value)
                row_y -= 9.2 * mm

            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 6.6)
            canvas.drawString(
                metric_x,
                card_y + 6.5 * mm,
                "Computed from the same valuation table used in the body of this report.",
            )
        canvas.restoreState()

    def report_page(canvas, _doc):
        canvas.saveState()
        header_label = _running_header_label(company_name, report_label)
        if header_label:
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 6.5)
            canvas.drawString(left, page_height - 10 * mm, header_label)
        if demo_mode:
            canvas.setFillColor(colors.HexColor("#A4670A"))
            canvas.setFont("Helvetica-Bold", 6.5)
            canvas.drawRightString(
                page_width - right,
                page_height - 10 * mm,
                "DEMO DATA - NOT FOR RELIANCE",
            )
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(0.6)
        canvas.line(left, 13 * mm, page_width - right, 13 * mm)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawString(left, 8.5 * mm, f"AccountIQ | {reference_code}")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(page_width - right, 8.5 * mm, str(canvas.getPageNumber()))
        if demo_mode:
            canvas.setFillColor(colors.HexColor("#A4670A"))
            canvas.setFont("Helvetica-Bold", 6.5)
            canvas.drawCentredString(
                page_width / 2,
                8.5 * mm,
                "DEMO DATA - NOT FOR RELIANCE",
            )
        canvas.restoreState()

    frame = Frame(left, bottom, available_width, page_height - top - bottom, id="content")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover_page),
        PageTemplate(id="report", frames=[frame], onPage=report_page),
    ])

    cover_title = _toc_paragraph(
        Paragraph(html.escape(_normalize_pdf_text(report_label)), styles["cover_title"]),
        text="Cover and credit paper summary" if is_credit_paper else "Cover and valuation snapshot",
        key="cover",
    )
    cover_brief = _cover_report_brief_table(
        company_name=company_name,
        report_label=report_label,
        report_type=report_type,
        report_id=report_id,
        generated_at=generated_at,
        valuation_purpose=valuation_purpose,
        demo_mode=demo_mode,
        available_width=available_width,
        styles=styles,
    )

    story: list = [
        Spacer(1, 170 * mm),
        Paragraph(
            "DEMO DATA - NOT FOR RELIANCE"
            if demo_mode
            else "CONFIDENTIAL - INDICATIVE ONLY",
            styles["cover_kicker"],
        ),
        cover_title,
        Paragraph(html.escape(_normalize_pdf_text(company_name)), styles["cover_company"]),
        cover_brief,
        NextPageTemplate("report"),
        PageBreak(),
        Paragraph("REPORT NAVIGATION", styles["section_kicker"]),
        Paragraph("Contents", styles["section_title"]),
    ]

    contents = TableOfContents(
        rightColumnWidth=14 * mm,
        levelStyles=[styles["toc_entry"]],
        dotsMinLevel=0,
    )
    contents.tableStyle = TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ])
    visible_sections = [key for key in section_order if key in sections]
    story.extend([contents, PageBreak()])

    if report_type == "valuation_advisory":
        basis = valuation_basis_of_preparation(
            company_name=company_name,
            report_label=report_label,
            report_id=report_id,
            demo_mode=demo_mode,
            valuation_purpose=valuation_purpose,
            generated_at=generated_at,
            intake_answers=intake_answers,
        )
        story.append(Paragraph("BASIS OF PREPARATION", styles["section_kicker"]))
        story.append(
            _toc_paragraph(
                Paragraph("Basis of preparation", styles["section_title"]),
                text="Front matter - Report letter and basis of preparation",
                key="basis-of-preparation",
            )
        )
        report_letter = basis.get("report_letter") if isinstance(basis.get("report_letter"), dict) else {}
        if report_letter:
            story.append(Paragraph(html.escape(_normalize_pdf_text(report_letter.get("title") or "Report letter")), styles["subheading"]))
            story.extend(_narrative_flowables(str(report_letter.get("narrative") or ""), styles))
            report_letter_table_data = (
                report_letter.get("table")
                if isinstance(report_letter.get("table"), dict)
                else {}
            )
            report_letter_table = _report_table(report_letter_table_data, available_width, styles)
            if report_letter_table is not None:
                story.append(Spacer(1, 2 * mm))
                story.append(report_letter_table)
                story.append(Spacer(1, 4 * mm))
        story.extend(_narrative_flowables(str(basis["narrative"]), styles))
        scope_table = _report_table(basis["scope_table"], available_width, styles)
        if scope_table is not None:
            story.append(Spacer(1, 3 * mm))
            story.append(scope_table)
        management_input_table_data = basis.get("management_input_table", {})
        management_input_rows = (
            management_input_table_data.get("rows")
            if isinstance(management_input_table_data, dict)
            else None
        )
        if management_input_rows:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Management input trail", styles["subheading"]))
            management_input_table = _report_table(management_input_table_data, available_width, styles)
            if management_input_table is not None:
                story.append(management_input_table)
            story.append(PageBreak())
            story.append(Paragraph("BASIS OF PREPARATION", styles["section_kicker"]))
            story.append(Paragraph("Evidence and model basis", styles["subheading"]))
        basis_table = _report_table(basis["table"], available_width, styles)
        if basis_table is not None:
            if not management_input_rows:
                story.append(Spacer(1, 4 * mm))
                story.append(Paragraph("Evidence and model basis", styles["subheading"]))
            story.append(Spacer(1, 2 * mm))
            story.append(basis_table)
        story.append(PageBreak())

    for index, key in enumerate(visible_sections, start=1):
        content = sections.get(key, "")
        title = section_titles.get(key, key.replace("_", " ").title())
        section_kicker = (
            "ACCOUNTIQ BANK CREDIT PAPER"
            if report_type == "bank_credit_paper"
            else "ACCOUNTIQ INDICATIVE VALUATION"
        )
        story.append(Paragraph(section_kicker, styles["section_kicker"]))
        story.append(
            _toc_paragraph(
                Paragraph(f"{index:02d} {html.escape(_normalize_pdf_text(title))}", styles["section_title"]),
                text=f"{index:02d} {_normalize_pdf_text(title)}",
                key=f"section-{index:02d}-{key}",
            )
        )

        if isinstance(content, dict):
            narrative = str(content.get("narrative", "") or "")
            table_data = content.get("table") if isinstance(content.get("table"), dict) else None
            extra_tables = {
                sub_key: sub_value
                for sub_key, sub_value in content.items()
                if sub_key not in {"narrative", "table"}
                and isinstance(sub_value, dict)
                and isinstance(sub_value.get("headers"), list)
                and isinstance(sub_value.get("rows"), list)
            }
        else:
            narrative = str(content or "")
            table_data = None
            extra_tables = {}

        guidance = valuation_reader_guidance(sections, key) if report_type == "valuation_advisory" else None
        if key == "disclaimer" and guidance is not None:
            guidance_title, guidance_rows = guidance
            guidance_table = _reader_guidance_table(guidance_rows, available_width, styles)
            if guidance_table is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(Paragraph(guidance_title, styles["subheading"]))
                story.append(guidance_table)
            guidance = None
        story.extend(_narrative_flowables(narrative, styles))
        if isinstance(content, dict):
            for market_chart in _market_chart_flowables(content, available_width):
                story.append(Spacer(1, 4 * mm))
                story.append(market_chart)
        if report_type == "valuation_advisory" and key == "executive_summary":
            highlights = executive_valuation_highlights(sections)
            highlight_table = _executive_highlights_table(highlights, available_width, styles)
            if highlight_table is not None:
                story.append(Spacer(1, 3 * mm))
                story.append(Paragraph("Valuation conclusion at a glance", styles["subheading"]))
                story.append(highlight_table)
            range_visual = _valuation_range_visual_flowable(sections, available_width)
            if range_visual is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(range_visual)
        if key == "valuation_methodology" and guidance is not None:
            guidance_title, guidance_rows = guidance
            guidance_table = _reader_guidance_table(guidance_rows, available_width, styles)
            if guidance_table is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(Paragraph(guidance_title, styles["subheading"]))
                story.append(guidance_table)
            guidance = None
        if key == "valuation_methodology":
            method_selection = _valuation_method_selection_flowable(sections, available_width, styles)
            if method_selection is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(method_selection)
        if key in {"financial_performance", "financial_ratio_analysis", "normalisations_schedule", "balance_sheet_summary", "valuation_assumptions", "wacc_assumptions", "dcf_analysis", "multiples_crosscheck", "valuation_summary", "sensitivity_and_risks", "comparable_evidence", "sources"} and guidance is not None:
            guidance_title, guidance_rows = guidance
            guidance_table = _reader_guidance_table(guidance_rows, available_width, styles)
            if guidance_table is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(Paragraph(guidance_title, styles["subheading"]))
                story.append(guidance_table)
            guidance = None
        if key == "financial_performance":
            trend_visual = _financial_trend_visual_flowable(sections, available_width)
            if trend_visual is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(trend_visual)
        if key == "normalisations_schedule":
            normalised_ebitda_bridge = _normalised_ebitda_bridge_visual_flowable(sections, available_width, styles)
            if normalised_ebitda_bridge is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(normalised_ebitda_bridge)
        if key == "balance_sheet_summary":
            equity_bridge = _equity_bridge_visual_flowable(sections, available_width, styles)
            if equity_bridge is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(equity_bridge)
        if key == "wacc_assumptions":
            wacc_build = _wacc_build_visual_flowable(sections, available_width, styles)
            if wacc_build is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(wacc_build)
        if key == "dcf_analysis":
            dcf_value_build = _dcf_value_build_visual_flowable(sections, available_width, styles)
            if dcf_value_build is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(dcf_value_build)
        if key == "multiples_crosscheck":
            implied_multiples = _implied_multiple_reconciliation_flowable(sections, available_width, styles)
            if implied_multiples is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(implied_multiples)
        if key == "sensitivity_and_risks":
            sensitivity_visual = _sensitivity_spread_visual_flowable(sections, available_width)
            if sensitivity_visual is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(sensitivity_visual)
        if table_data:
            story.append(Spacer(1, 3 * mm))
            table = _report_table(table_data, available_width, styles)
            if table is not None:
                story.append(table)
        if guidance is not None:
            guidance_title, guidance_rows = guidance
            guidance_table = _reader_guidance_table(guidance_rows, available_width, styles)
            if guidance_table is not None:
                story.append(Spacer(1, 4 * mm))
                story.append(Paragraph(guidance_title, styles["subheading"]))
                story.append(guidance_table)
        for sub_key, subtable in extra_tables.items():
            subheading = {
                "cash_flow_schedule": "Mid-case forecast cash-flow schedule",
                "specific_risk_factors": "Specific risk factors",
                "debt_capacity_table": "Debt-capacity constraints",
                "amortisation_profile_table": "P&I leverage profile",
                "sector_scale_table": "Sector scale and boundary",
                "market_sources_table": "Market data sources",
            }.get(sub_key, sub_key.replace("_", " ").title())
            story.append(Spacer(1, 5 * mm))
            story.append(Paragraph(html.escape(_normalize_pdf_text(subheading)), styles["subheading"]))
            table = _report_table(subtable, available_width, styles)
            if table is not None:
                story.append(table)

        if index < len(visible_sections):
            story.append(PageBreak())

    doc.multiBuild(story)
    temporary_path.replace(output_path)
