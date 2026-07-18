"""Unit tests for wizard_report_view section rendering (Phase 05.1 D-I4)."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _narrative_to_html, _render_report_sections_html


def test_renders_plain_string_section():
    html = _render_report_sections_html(
        {"introduction": "Hello world.\n\nSecond para."},
        ["introduction"],
    )
    assert "<h2>Introduction</h2>" in html
    assert "<p>Hello world.</p>" in html
    assert "<p>Second para.</p>" in html
    assert "report-table" not in html


def test_renders_dict_section_with_table():
    sections = {
        "wacc_assumptions": {
            "narrative": "WACC inputs were derived from research.",
            "table": {
                "headers": ["Component", "High", "Mid", "Low"],
                "rows": [["Risk-free rate", "4.8%", "4.8%", "4.8%"], ["WACC", "13.5%", "11.1%", "8.7%"]],
            },
        },
    }
    html = _render_report_sections_html(sections, ["wacc_assumptions"])
    assert "<table class='report-table'>" in html
    assert "class='table-scroll' tabindex='0' role='region' aria-label='Wacc Assumptions table'" in html
    assert "<th>Component</th>" in html
    assert "<th>High</th>" in html
    assert "<td>Risk-free rate</td>" in html
    assert "<td>11.1%</td>" in html
    assert "WACC inputs were derived from research." in html


def test_escapes_html_in_table_cells():
    sections = {
        "valuation_summary": {
            "narrative": "Result <script>alert(1)</script>",
            "table": {"headers": ["A<x>"], "rows": [["<b>bold</b>"]]},
        },
    }
    html = _render_report_sections_html(sections, ["valuation_summary"])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<th>A<x></th>" not in html
    assert "&lt;x&gt;" in html
    assert "<td><b>bold</b></td>" not in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html


def test_handles_missing_table_data():
    sections = {"foo": {"narrative": "ok"}}
    html = _render_report_sections_html(sections, ["foo"])
    assert "<p>ok</p>" in html
    assert "<table" not in html


def test_handles_empty_section_value():
    sections = {"foo": ""}
    html = _render_report_sections_html(sections, ["foo"])
    assert "<h2>Foo</h2>" in html
    assert "<p></p>" not in html


# ---------------------------------------------------------------------------
# _narrative_to_html tests
# ---------------------------------------------------------------------------

def test_narrative_heading_renders_h3():
    html = _narrative_to_html("## Background\nSome text.")
    assert "<h3>Background</h3>" in html
    assert "<p>Some text.</p>" in html
    assert "## Background" not in html


def test_narrative_bullets_render_ul():
    html = _narrative_to_html("- Revenue grew 20%\n- Margins improved\n- New clients won")
    assert "<ul>" in html
    assert "<li>Revenue grew 20%</li>" in html
    assert "<li>Margins improved</li>" in html
    assert "<li>New clients won</li>" in html
    assert "</ul>" in html


def test_narrative_star_bullets_render_ul():
    html = _narrative_to_html("* First point\n* Second point")
    assert "<li>First point</li>" in html
    assert "<li>Second point</li>" in html


def test_narrative_bold_renders_strong():
    html = _narrative_to_html("The **WACC** is derived from first principles.")
    assert "<strong>WACC</strong>" in html
    assert "**WACC**" not in html


def test_narrative_escapes_html_before_inline():
    html = _narrative_to_html("<script>alert(1)</script>\n## <evil> heading\n- <b>item</b>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<evil>" not in html
    assert "&lt;evil&gt;" in html
    assert "<b>item</b>" not in html
    assert "&lt;b&gt;item&lt;/b&gt;" in html


def test_narrative_empty_lines_do_not_produce_paragraphs():
    html = _narrative_to_html("\n\n\n")
    assert "<p>" not in html


def test_narrative_mixed_content():
    text = "## Revenue Model\nThe company sells SaaS.\n\n## Key Metrics\n- ARR: $2.1m\n- NRR: 115%"
    html = _narrative_to_html(text)
    assert "<h3>Revenue Model</h3>" in html
    assert "<p>The company sells SaaS.</p>" in html
    assert "<h3>Key Metrics</h3>" in html
    assert "<li>ARR: $2.1m</li>" in html
    assert "<li>NRR: 115%</li>" in html


def test_disclaimer_section_gets_class():
    html = _render_report_sections_html(
        {"disclaimer": "This report is indicative only."},
        ["disclaimer"],
    )
    assert "class='disclaimer'" in html


def test_non_disclaimer_section_no_class():
    html = _render_report_sections_html(
        {"introduction": "Hello."},
        ["introduction"],
    )
    assert "class='disclaimer'" not in html
