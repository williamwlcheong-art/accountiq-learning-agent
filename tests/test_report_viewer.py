"""Unit tests for wizard_report_view section rendering (Phase 05.1 D-I4)."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import _render_report_sections_html


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
