"""Tests for valuation PDF visual-preview rendering."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


PREVIEW_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "render_valuation_pdf_preview.py"
SAMPLE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_sample_valuation_pdf.py"
PACK_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_valuation_visual_parity_pack.py"
REFERENCE_RENDER_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "render_reference_pdf_pages.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pdf_preview_page_parser_supports_ranges_and_dedupes():
    preview = _load_module(PREVIEW_SCRIPT, "render_valuation_pdf_preview")

    assert "demo" in preview.DEFAULT_PDF.name
    assert preview._parse_pages("1,3-5,5,2") == [1, 2, 3, 4, 5]
    assert preview._parse_pages("auto") is None


def test_pdf_preview_page_parser_rejects_invalid_ranges():
    preview = _load_module(PREVIEW_SCRIPT, "render_valuation_pdf_preview")

    with pytest.raises(ValueError, match="Invalid page range"):
        preview._parse_pages("5-3")


def test_visual_parity_pack_builder_creates_review_html(tmp_path):
    pack = _load_module(PACK_SCRIPT, "build_valuation_visual_parity_pack")
    image_path = tmp_path / "page-01.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pdf": str(pdf_path),
                "pages": [
                    {"page": 1, "path": str(image_path)},
                ],
                "page_targets": [
                    {
                        "label": "Cover valuation snapshot",
                        "page": 1,
                        "markers": ["VALUATION SNAPSHOT"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    checklist_path = tmp_path / "checklist.md"
    checklist_path.write_text("# Checklist\n", encoding="utf-8")
    output_path = tmp_path / "review.html"

    result = pack.build_visual_parity_pack(
        manifest_path=manifest_path,
        output_path=output_path,
        parity_checklist_path=checklist_path,
    )

    html = output_path.read_text(encoding="utf-8")
    assert result["page_count"] == 1
    assert result["target_count"] == 1
    assert "Valuation visual parity review" in html
    assert "Cover valuation snapshot" in html
    assert "VALUATION SNAPSHOT" in html
    assert "page-01.png" in html
    assert "Reference evidence available for this review" in html
    assert "python scripts/render_valuation_pdf_preview.py" in html
    assert "python scripts/build_valuation_visual_parity_pack.py" in html
    assert "does not prove final visual parity against the original example PDFs" in html


def test_visual_parity_pack_builder_maps_reference_images(tmp_path):
    pack = _load_module(PACK_SCRIPT, "build_valuation_visual_parity_pack")
    accountiq_image_path = tmp_path / "accountiq-cover.png"
    accountiq_image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    reference_image_path = tmp_path / "marina-cover.png"
    reference_image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pdf": str(pdf_path),
                "pages": [
                    {"page": 1, "path": str(accountiq_image_path)},
                ],
                "page_targets": [
                    {
                        "label": "Cover valuation snapshot",
                        "page": 1,
                        "markers": ["VALUATION SNAPSHOT"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    reference_manifest_path = tmp_path / "reference-manifest.json"
    reference_manifest_path.write_text(
        json.dumps(
            {
                "references": [
                    {
                        "accountiq_target": "Cover valuation snapshot",
                        "title": "Marina Terrace cover",
                        "source": "Marina Terrace example",
                        "path": reference_image_path.name,
                        "notes": "Cover/title and prepared-for party",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    checklist_path = tmp_path / "checklist.md"
    checklist_path.write_text("# Checklist\n", encoding="utf-8")
    output_path = tmp_path / "review.html"

    result = pack.build_visual_parity_pack(
        manifest_path=manifest_path,
        output_path=output_path,
        parity_checklist_path=checklist_path,
        reference_manifest_path=reference_manifest_path,
    )

    html = output_path.read_text(encoding="utf-8")
    assert result["reference_count"] == 1
    assert result["reference_manifest_path"] == str(reference_manifest_path)
    assert "Marina Terrace cover" in html
    assert "Marina Terrace example" in html
    assert "marina-cover.png" in html
    assert "mapped reference images from the supplied reference manifest" in html


def test_visual_parity_pack_builder_writes_reference_template(tmp_path):
    pack = _load_module(PACK_SCRIPT, "build_valuation_visual_parity_pack")
    image_path = tmp_path / "accountiq-cover.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pdf": str(pdf_path),
                "pages": [
                    {"page": 1, "path": str(image_path)},
                ],
                "page_targets": [
                    {
                        "label": "Cover valuation snapshot",
                        "page": 1,
                        "markers": ["VALUATION SNAPSHOT", "Enterprise value"],
                    },
                    {
                        "label": "Contents",
                        "page": 2,
                        "markers": ["REPORT NAVIGATION", "Contents"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    template_path = tmp_path / "reference-manifest.template.json"

    result = pack.write_reference_manifest_template(
        manifest_path=manifest_path,
        output_path=template_path,
    )

    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert result["reference_rows"] == 2
    assert template["references"][0]["accountiq_target"] == "Cover valuation snapshot"
    assert template["references"][0]["path"] == ""
    assert "AccountIQ page 1" in template["references"][0]["notes"]
    assert "VALUATION SNAPSHOT" in template["references"][0]["notes"]
    assert template["references"][1]["accountiq_target"] == "Contents"
    assert "Copy this file to reference-manifest.json." in template["instructions"]


def test_reference_pdf_renderer_writes_pack_builder_manifest(tmp_path, monkeypatch):
    renderer = _load_module(REFERENCE_RENDER_SCRIPT, "render_reference_pdf_pages")
    pdf_path = tmp_path / "Marina Terrace.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    spec_path = tmp_path / "reference-pdf-map.json"
    spec_path.write_text(
        json.dumps(
            {
                "references": [
                    {
                        "source": "Marina Terrace example",
                        "pdf": pdf_path.name,
                        "pages": [
                            {
                                "page": 1,
                                "accountiq_target": "Cover valuation snapshot",
                                "title": "Marina Terrace cover",
                                "notes": "Cover/title and prepared-for party",
                            },
                            {
                                "page": 3,
                                "accountiq_target": ["Basis of preparation", "Executive valuation conclusion"],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_run(args, **_kwargs):
        page = args[args.index("-f") + 1]
        prefix = Path(args[-1])
        (prefix.parent / f"{prefix.name}-{page}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(renderer, "_pdftoppm_binary", lambda: "pdftoppm")
    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    result = renderer.render_reference_pdf_pages(
        spec_path=spec_path,
        output_dir=tmp_path / "reference-examples",
        reference_manifest_path=tmp_path / "reference-examples" / "reference-manifest.json",
        resolution=72,
    )

    manifest_path = Path(result["reference_manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert result["reference_count"] == 2
    assert result["pdf_count"] == 1
    assert manifest["generated_from"] == str(spec_path)
    assert manifest["references"][0]["accountiq_target"] == "Cover valuation snapshot"
    assert manifest["references"][0]["title"] == "Marina Terrace cover"
    assert manifest["references"][0]["source"] == "Marina Terrace example"
    assert manifest["references"][0]["path"] == "marina-terrace-example-page-001.png"
    assert manifest["references"][0]["notes"] == "Cover/title and prepared-for party"
    assert manifest["references"][1]["accountiq_target"] == [
        "Basis of preparation",
        "Executive valuation conclusion",
    ]
    assert manifest["references"][1]["path"] == "marina-terrace-example-page-003.png"
    assert (manifest_path.parent / "marina-terrace-example-page-001.png").read_bytes().startswith(b"\x89PNG")
    assert (manifest_path.parent / "marina-terrace-example-page-003.png").read_bytes().startswith(b"\x89PNG")


def test_reference_pdf_renderer_writes_mapping_template(tmp_path):
    renderer = _load_module(REFERENCE_RENDER_SCRIPT, "render_reference_pdf_pages")
    preview_manifest_path = tmp_path / "preview-manifest.json"
    preview_manifest_path.write_text(
        json.dumps(
            {
                "page_targets": [
                    {
                        "label": "Cover valuation snapshot",
                        "page": 1,
                        "markers": ["VALUATION SNAPSHOT", "Enterprise value"],
                    },
                    {
                        "label": "Basis of preparation",
                        "page": 3,
                        "markers": ["BASIS OF PREPARATION", "Report letter"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    template_path = tmp_path / "reference-pdf-map.template.json"

    result = renderer.write_reference_pdf_map_template(
        preview_manifest_path=preview_manifest_path,
        output_path=template_path,
    )

    template = json.loads(template_path.read_text(encoding="utf-8"))
    pages = template["references"][0]["pages"]
    assert result["reference_page_rows"] == 2
    assert template["references"][0]["pdf"] == ""
    assert pages[0]["page"] is None
    assert pages[0]["accountiq_target"] == "Cover valuation snapshot"
    assert "VALUATION SNAPSHOT" in pages[0]["notes"]
    assert pages[1]["accountiq_target"] == "Basis of preparation"
    assert "reference-pdf-map.json" in template["instructions"][0]


def test_pdf_preview_auto_pages_follow_current_report_structure(tmp_path):
    pytest.importorskip("pdfplumber")
    generator = _load_module(SAMPLE_SCRIPT, "generate_sample_valuation_pdf")
    preview = _load_module(PREVIEW_SCRIPT, "render_valuation_pdf_preview")
    pdf_path = generator.generate_sample_pdf(tmp_path / "sample.pdf")

    pages = preview._default_preview_pages(pdf_path)
    _pages_from_hits, target_hits = preview._default_preview_page_hits(pdf_path)
    page_texts = preview._extract_pdf_page_text(pdf_path)
    selected_text = "\n".join(page_texts[page - 1] for page in pages)
    targets_by_label = {hit["label"]: hit["page"] for hit in target_hits}

    assert 1 in pages
    assert len(targets_by_label) == len(preview.DEFAULT_PAGE_TARGETS)
    assert all(page is not None for page in targets_by_label.values())
    assert set(targets_by_label.values()).issubset(set(pages))
    assert "VALUATION SNAPSHOT" in selected_text
    assert "Indicative equity value" in selected_text
    assert "18 Sources and References" in selected_text
    assert "19 Disclaimer" in selected_text
    assert "20 General Principles" in selected_text
    assert "21 Glossary" in selected_text
    assert "14 Indicative Valuation Summary" in selected_text
    assert "15 Multiples Cross-check" in selected_text
    assert "Specific risk factors" in selected_text
    assert "Specific risk factor Management input Valuation relevance Report treatment" in selected_text
    assert "Evidence and model basis" in selected_text
    assert "Valuation conclusion at a glance" in selected_text
    assert targets_by_label["Cover valuation snapshot"] == 1
    assert targets_by_label["Contents"] in pages
    assert targets_by_label["Basis of preparation"] in pages
    assert targets_by_label["Executive valuation conclusion"] in pages
    assert targets_by_label["Valuation assumptions"] in pages
    assert targets_by_label["DCF analysis"] in pages
    assert targets_by_label["Indicative valuation summary"] in pages
    assert targets_by_label["Multiples cross-check"] in pages
    assert targets_by_label["Sensitivity"] in pages
    assert targets_by_label["Specific risk factors"] in pages
    risk_target = next(target for target in target_hits if target["label"] == "Specific risk factors")
    assert "Valuation relevance" in risk_target["markers"]
    assert "Report treatment" in risk_target["markers"]
    assert targets_by_label["Comparable evidence"] in pages
    assert targets_by_label["Sources"] in pages
    assert targets_by_label["Disclaimer"] in pages
    assert targets_by_label["General principles"] in pages
    assert targets_by_label["Glossary"] in pages


def test_pdf_preview_fallback_pages_cover_current_professional_pack(monkeypatch):
    preview = _load_module(PREVIEW_SCRIPT, "render_valuation_pdf_preview")

    def fail_extract(_pdf_path):
        raise RuntimeError("text extraction unavailable")

    monkeypatch.setattr(preview, "_extract_pdf_page_text", fail_extract)

    pages, target_hits = preview._default_preview_page_hits(Path("sample.pdf"))

    assert target_hits == []
    assert pages == sorted(set(pages))
    assert {
        1,   # cover
        2,   # contents
        3,   # basis of preparation
        4,   # evidence and model basis
        6,   # executive summary
        10,  # valuation methodology
        11,  # financial performance
        13,  # normalisations
        14,  # balance sheet summary
        15,  # valuation assumptions
        18,  # DCF analysis
        20,  # indicative valuation summary
        21,  # multiples cross-check
        22,  # sensitivity
        23,  # specific risk factors
        24,  # comparable evidence
        25,  # sources
        26,  # disclaimer
        27,  # general principles
        28,  # glossary
    }.issubset(set(pages))


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="pdftoppm is not available")
def test_pdf_preview_renderer_creates_manifest_and_pngs(tmp_path):
    generator = _load_module(SAMPLE_SCRIPT, "generate_sample_valuation_pdf")
    preview = _load_module(PREVIEW_SCRIPT, "render_valuation_pdf_preview")
    pdf_path = generator.generate_sample_pdf(tmp_path / "sample.pdf")

    manifest = preview.render_pdf_preview(
        pdf_path,
        output_dir=tmp_path / "preview",
        pages=[1, 2],
        resolution=72,
    )

    assert Path(manifest["manifest_path"]).exists()
    assert manifest["pdf"] == str(pdf_path)
    assert [page["page"] for page in manifest["pages"]] == [1, 2]
    for page in manifest["pages"]:
        output_path = Path(page["path"])
        assert output_path.exists()
        assert output_path.read_bytes().startswith(b"\x89PNG")


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="pdftoppm is not available")
def test_pdf_preview_renderer_auto_manifest_covers_tail_sections(tmp_path):
    pytest.importorskip("pdfplumber")
    generator = _load_module(SAMPLE_SCRIPT, "generate_sample_valuation_pdf")
    preview = _load_module(PREVIEW_SCRIPT, "render_valuation_pdf_preview")
    pdf_path = generator.generate_sample_pdf(tmp_path / "sample.pdf")

    manifest = preview.render_pdf_preview(
        pdf_path,
        output_dir=tmp_path / "preview-auto",
        pages=None,
        resolution=72,
    )

    page_numbers = [page["page"] for page in manifest["pages"]]
    page_texts = preview._extract_pdf_page_text(pdf_path)
    selected_text = "\n".join(page_texts[page - 1] for page in page_numbers)

    assert manifest["selection_mode"] == "auto"
    assert page_numbers == sorted(set(page_numbers))
    target_labels = {target["label"] for target in manifest["page_targets"]}
    matched_target_labels = {target["label"] for target in manifest["page_targets"] if target["page"]}
    assert target_labels == {label for label, _markers in preview.DEFAULT_PAGE_TARGETS}
    assert matched_target_labels == target_labels
    assert "VALUATION SNAPSHOT" in selected_text
    assert "Indicative equity value" in selected_text
    assert "18 Sources and References" in selected_text
    assert "19 Disclaimer" in selected_text
    assert "20 General Principles" in selected_text
    assert "21 Glossary" in selected_text
    assert "14 Indicative Valuation Summary" in selected_text
    assert "15 Multiples Cross-check" in selected_text
    assert "Specific risk factor Management input Valuation relevance Report treatment" in selected_text
