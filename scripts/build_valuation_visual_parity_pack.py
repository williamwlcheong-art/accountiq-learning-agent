"""Build a visual parity review pack for the AccountIQ valuation sample.

The pack is a lightweight HTML artifact that places the rendered AccountIQ PDF
preview pages next to the example-report parity criteria. It intentionally does
not claim final visual parity against the user's original PDFs unless those
source PDFs/page images are available as durable QA inputs.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "tmp"
    / "pdfs"
    / "valuation-preview"
    / "accountiq-demo-sample-indicative-valuation-preview-manifest.json"
)
DEFAULT_PARITY_CHECKLIST = ROOT / "docs" / "valuation-example-parity-checklist.md"
DEFAULT_OUTPUT = ROOT / "output" / "html" / "valuation-visual-parity-review.html"
DEFAULT_REFERENCE_MANIFEST = ROOT / "tmp" / "pdfs" / "reference-examples" / "reference-manifest.json"
DEFAULT_REFERENCE_TEMPLATE = ROOT / "tmp" / "pdfs" / "reference-examples" / "reference-manifest.template.json"

REFERENCE_SPINE = (
    "Cover/title and prepared-for party",
    "Contents",
    "Introduction, scope and reliance wording",
    "Overview and market/business context",
    "About business valuations",
    "Valuation methodology adopted",
    "Financial performance and normalisations",
    "Valuation approach and assumptions",
    "WACC, DCF, sensitivity and multiples cross-check",
    "Comparable evidence, sources, disclaimer, general principles and glossary",
)

REVIEW_CHECKS = (
    (
        "First impression",
        "Cover page reads like a professional valuation pack, not a form confirmation screen.",
    ),
    (
        "Evidence basis",
        "Basis pages explain uploaded financials, five private inputs, public-source trail and AccountIQ model.",
    ),
    (
        "Reader navigation",
        "Contents and numbered sections make the report easy to cross-reference.",
    ),
    (
        "Valuation conclusion",
        "Executive summary and valuation summary show high/mid/low enterprise and equity value clearly.",
    ),
    (
        "Calculation trail",
        "WACC, DCF, multiples, equity bridge and sensitivity pages expose computed mechanics without asking the user for technical assumptions.",
    ),
    (
        "Source trail",
        "Comparable evidence and sources retain public URLs and explain what each source supports.",
    ),
    (
        "Reliance framing",
        "Disclaimer, general principles and glossary close the report like a deliberate professional pack.",
    ),
)

SOURCE_BOUNDARY = (
    "Marina Terrace text extract is available for detailed structure and wording cues.",
    "Propellerhead extract is sparse and mainly confirms the broad professional report spine.",
    "Original example PDFs/page images are not stored as durable QA inputs in this repo.",
    "This pack reviews the current AccountIQ rendered pages; final side-by-side visual parity still needs the original reference pages.",
)

REGEN_COMMANDS = (
    "source venv/bin/activate",
    "python scripts/generate_sample_valuation_pdf.py",
    "python scripts/render_valuation_pdf_preview.py --pdf output/pdf/accountiq-demo-sample-indicative-valuation.pdf --pages auto",
    "python scripts/build_valuation_visual_parity_pack.py",
)


def _load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Preview manifest must be a JSON object.")
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Preview manifest must include a non-empty pages array.")
    return payload


def _load_reference_entries(path: Path | None) -> tuple[list[dict], str | None]:
    """Load optional reference-image entries for true side-by-side review.

    Expected JSON shape:

    {
      "references": [
        {
          "accountiq_target": "Cover valuation snapshot",
          "title": "Marina Terrace cover page",
          "source": "Marina Terrace",
          "path": "marina-cover.png",
          "notes": "Cover/title and prepared-for party"
        }
      ]
    }

    ``accountiq_target`` may also be a list of target labels. Relative paths are
    resolved relative to the reference manifest file.
    """
    if path is None:
        return [], None
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Reference manifest does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    references = payload.get("references") if isinstance(payload, dict) else None
    if not isinstance(references, list):
        raise ValueError("Reference manifest must contain a references array.")

    entries: list[dict] = []
    for index, raw_entry in enumerate(references, start=1):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Reference entry {index} must be an object.")
        entry_path = raw_entry.get("path")
        if not isinstance(entry_path, str) or not entry_path.strip():
            raise ValueError(f"Reference entry {index} must include a path.")
        resolved_path = Path(entry_path)
        if not resolved_path.is_absolute():
            resolved_path = path.parent / resolved_path
        if not resolved_path.exists():
            raise FileNotFoundError(f"Reference image does not exist: {resolved_path}")
        target = raw_entry.get("accountiq_target")
        if isinstance(target, str):
            targets = [target]
        elif isinstance(target, list) and all(isinstance(item, str) for item in target):
            targets = target
        else:
            raise ValueError(f"Reference entry {index} must include accountiq_target as a string or list.")
        entries.append(
            {
                "targets": targets,
                "path": str(resolved_path),
                "title": str(raw_entry.get("title") or raw_entry.get("source") or resolved_path.name),
                "source": str(raw_entry.get("source") or "Reference example"),
                "notes": str(raw_entry.get("notes") or ""),
            }
        )
    return entries, str(path)


def _src_for(target: str | Path, output_path: Path) -> str:
    path = Path(target)
    try:
        return Path(path.resolve()).relative_to(output_path.parent.resolve()).as_posix()
    except ValueError:
        return Path("../../" + Path(path.resolve()).relative_to(ROOT.resolve()).as_posix()).as_posix()


def _references_by_target(reference_entries: list[dict]) -> dict[str, list[dict]]:
    references: dict[str, list[dict]] = {}
    for entry in reference_entries:
        for target in entry.get("targets") or []:
            references.setdefault(str(target), []).append(entry)
    return references


def _targets_by_page(manifest: dict) -> dict[int, list[dict]]:
    targets: dict[int, list[dict]] = {}
    for target in manifest.get("page_targets") or []:
        if not isinstance(target, dict):
            continue
        page = target.get("page")
        if isinstance(page, int):
            targets.setdefault(page, []).append(target)
    return targets


def write_reference_manifest_template(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_REFERENCE_TEMPLATE,
) -> dict:
    """Write a fill-in template for original example-report page images."""
    manifest_path = manifest_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    manifest = _load_manifest(manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    references: list[dict] = []
    for target in manifest.get("page_targets") or []:
        if not isinstance(target, dict):
            continue
        label = str(target.get("label") or "").strip()
        if not label:
            continue
        markers = [str(marker) for marker in target.get("markers") or []]
        matched_page = target.get("page")
        references.append(
            {
                "accountiq_target": label,
                "title": "",
                "source": "",
                "path": "",
                "notes": (
                    f"AccountIQ page {matched_page}; "
                    f"target markers: {', '.join(markers)}"
                    if matched_page
                    else f"Target markers: {', '.join(markers)}"
                ),
            }
        )

    template = {
        "instructions": [
            "Copy this file to reference-manifest.json.",
            "Place original example-report page PNG/JPG files in the same folder.",
            "For each reference image, fill title, source and path.",
            "Keep accountiq_target exactly as generated so the visual review pack can map reference pages to AccountIQ pages.",
            "Delete any unused reference rows before running build_valuation_visual_parity_pack.py --reference-manifest.",
        ],
        "references": references,
    }
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return {
        "template_path": str(output_path),
        "manifest_path": str(manifest_path),
        "reference_rows": len(references),
    }


def _render_reference_entries(entries: list[dict], output_path: Path) -> str:
    if not entries:
        return """
        <div class="reference-placeholder">
          <strong>No mapped reference image supplied yet.</strong>
          <span>Add one in the optional reference manifest to make this a true side-by-side comparison.</span>
        </div>
        """
    rendered: list[str] = []
    for entry in entries:
        src = html.escape(_src_for(entry["path"], output_path), quote=True)
        notes = str(entry.get("notes") or "")
        notes_html = f"<p>{html.escape(notes)}</p>" if notes else ""
        rendered.append(
            f"""
            <figure class="reference-figure">
              <a href="{src}">
                <img src="{src}" alt="{html.escape(str(entry.get("title", "Reference page")), quote=True)}">
              </a>
              <figcaption>
                <strong>{html.escape(str(entry.get("title", "Reference page")))}</strong>
                <span>{html.escape(str(entry.get("source", "Reference example")))}</span>
                {notes_html}
              </figcaption>
            </figure>
            """
        )
    return "\n".join(rendered)


def _render_page_cards(manifest: dict, output_path: Path, reference_entries: list[dict]) -> str:
    targets_by_page = _targets_by_page(manifest)
    references = _references_by_target(reference_entries)
    cards: list[str] = []
    for page in manifest["pages"]:
        if not isinstance(page, dict):
            continue
        page_number = page.get("page")
        path = page.get("path")
        if not isinstance(page_number, int) or not isinstance(path, str):
            continue
        target_hits = targets_by_page.get(page_number, [])
        target_labels = [str(target.get("label", "")) for target in target_hits]
        target_html = "\n".join(
            "<li>"
            f"<strong>{html.escape(str(target.get('label', 'Target')))}</strong>"
            f"<span>{html.escape(', '.join(str(marker) for marker in target.get('markers', [])))}</span>"
            "</li>"
            for target in target_hits
        )
        if not target_html:
            target_html = "<li><strong>Manual review page</strong><span>Selected for visual continuity.</span></li>"
        matched_references = [
            entry
            for label in target_labels
            for entry in references.get(label, [])
        ]
        src = html.escape(_src_for(path, output_path), quote=True)
        cards.append(
            f"""
            <article class="page-card">
              <div class="page-card-text">
                <p class="eyebrow">AccountIQ rendered PDF page {page_number}</p>
                <h2>Page {page_number}</h2>
                <ul class="target-list">{target_html}</ul>
              </div>
              <div class="comparison-grid">
                <figure>
                  <a href="{src}">
                    <img src="{src}" alt="Rendered AccountIQ valuation PDF page {page_number}">
                  </a>
                  <figcaption>
                    <strong>AccountIQ current output</strong>
                    <span>Rendered PDF page {page_number}</span>
                  </figcaption>
                </figure>
                <div class="reference-column">
                  {_render_reference_entries(matched_references, output_path)}
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(cards)


def build_visual_parity_pack(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    parity_checklist_path: Path = DEFAULT_PARITY_CHECKLIST,
    reference_manifest_path: Path | None = None,
) -> dict:
    """Build the visual parity HTML artifact and return output metadata."""
    manifest_path = manifest_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    parity_checklist_path = parity_checklist_path.expanduser().resolve()

    manifest = _load_manifest(manifest_path)
    reference_entries, resolved_reference_manifest = _load_reference_entries(reference_manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    checklist_href = html.escape(_src_for(parity_checklist_path, output_path), quote=True)
    pdf_href = html.escape(_src_for(manifest.get("pdf", ""), output_path), quote=True)
    spine_html = "\n".join(f"<li>{html.escape(item)}</li>" for item in REFERENCE_SPINE)
    source_boundary_html = "\n".join(f"<li>{html.escape(item)}</li>" for item in SOURCE_BOUNDARY)
    checks_html = "\n".join(
        f"<li><strong>{html.escape(label)}</strong><span>{html.escape(description)}</span></li>"
        for label, description in REVIEW_CHECKS
    )
    regen_commands_html = "\n".join(f"<code>{html.escape(command)}</code>" for command in REGEN_COMMANDS)
    page_cards = _render_page_cards(manifest, output_path, reference_entries)
    page_count = len(manifest.get("pages") or [])
    target_count = len(manifest.get("page_targets") or [])
    reference_count = len(reference_entries)
    evidence_boundary = (
        "This pack includes mapped reference images from the supplied reference manifest, so mapped pages can be "
        "reviewed side-by-side against the current AccountIQ output. Unmapped pages still require manual review."
        if reference_entries
        else "This pack proves that the current AccountIQ sample has rendered review pages for the professional "
        "valuation-report spine captured in the example parity checklist. It does not prove final visual parity "
        "against the original example PDFs because those original PDFs are not stored as durable source artifacts "
        "in the repo."
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AccountIQ valuation visual parity review</title>
  <style>
    :root {{
      --navy: #082f4f;
      --blue: #1f73b7;
      --ink: #132033;
      --muted: #607089;
      --line: #d8e2ee;
      --paper: #f5f8fb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
      line-height: 1.55;
    }}
    header {{
      padding: 48px clamp(24px, 5vw, 72px);
      background: linear-gradient(135deg, #082f4f, #0f4774);
      color: white;
    }}
    header p {{ max-width: 920px; color: #d8e7f6; }}
    main {{ padding: 32px clamp(18px, 4vw, 56px) 56px; }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
      margin: -58px 0 28px;
    }}
    .summary-card, .section, .page-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: white;
      box-shadow: 0 18px 45px rgba(8, 47, 79, .08);
    }}
    .summary-card {{ padding: 22px; }}
    .summary-card strong {{ display: block; font-size: 2rem; color: var(--navy); }}
    .summary-card span {{ color: var(--muted); }}
    .section {{ padding: 24px; margin: 24px 0; }}
    .eyebrow {{
      margin: 0 0 6px;
      color: var(--blue);
      font-size: .74rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    h1, h2 {{ margin: 0 0 12px; line-height: 1.15; }}
    h1 {{ font-size: clamp(2rem, 4vw, 3.4rem); }}
    h2 {{ color: var(--navy); }}
    ul {{ padding-left: 1.2rem; }}
    .review-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      padding: 0;
      list-style: none;
    }}
    .review-list li {{
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #f9fbfe;
    }}
    .review-list strong, .review-list span {{ display: block; }}
    .review-list span {{ color: var(--muted); font-size: .92rem; }}
    .page-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 24px;
      align-items: start;
    }}
    .page-card {{ overflow: hidden; }}
    .page-card-text {{ padding: 20px 20px 0; }}
    .comparison-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
      align-items: start;
      padding: 0 20px 20px;
    }}
    figure {{ margin: 0; }}
    figcaption {{
      padding: 12px 0 0;
      color: var(--muted);
      font-size: .86rem;
    }}
    figcaption strong, figcaption span {{ display: block; }}
    figcaption strong {{ color: var(--navy); }}
    figcaption p {{ margin: 8px 0 0; }}
    .reference-column {{
      display: grid;
      gap: 16px;
    }}
    .reference-placeholder {{
      margin-top: 18px;
      min-height: 180px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 6px;
      padding: 18px;
      border: 1px dashed #b8c6d8;
      border-radius: 12px;
      background: #f9fbfe;
      color: var(--muted);
    }}
    .reference-placeholder strong {{ color: var(--navy); }}
    .target-list {{
      display: grid;
      gap: 8px;
      padding: 0;
      list-style: none;
    }}
    .target-list li {{
      padding: 10px 12px;
      border-left: 3px solid var(--blue);
      background: #f4f8fc;
    }}
    .target-list strong, .target-list span {{ display: block; }}
    .target-list span {{ color: var(--muted); font-size: .82rem; }}
    img {{
      display: block;
      width: 100%;
      height: auto;
      margin-top: 18px;
      border-top: 1px solid var(--line);
      background: white;
    }}
    a {{ color: var(--blue); }}
    .warning {{
      border-left: 4px solid #f59e0b;
      background: #fffbeb;
    }}
    .command-stack {{
      display: grid;
      gap: 8px;
      margin-top: 14px;
    }}
    code {{
      display: block;
      padding: 10px 12px;
      border-radius: 10px;
      background: #0b1724;
      color: #dceafe;
      overflow-x: auto;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: .86rem;
    }}
  </style>
</head>
<body>
  <header>
    <p class="eyebrow">AccountIQ visual QA</p>
    <h1>Valuation visual parity review</h1>
    <p>
      Generated {html.escape(date.today().isoformat())} from the current AccountIQ demo valuation PDF preview.
      This pack reviews visual/report-structure parity against the available example-report extracts and links to
      the rendered AccountIQ pages for manual inspection.
    </p>
  </header>
  <main>
    <section class="summary-grid" aria-label="Review summary">
      <div class="summary-card"><strong>{page_count}</strong><span>Rendered pages included</span></div>
      <div class="summary-card"><strong>{target_count}</strong><span>Automatic report targets checked</span></div>
      <div class="summary-card"><strong>{reference_count}</strong><span>Mapped reference images supplied</span></div>
    </section>

    <section class="section warning">
      <p class="eyebrow">Evidence boundary</p>
      <h2>What this proves and does not prove</h2>
      <p>
        {html.escape(evidence_boundary)}
        See <a href="{checklist_href}">the example parity checklist</a> for the source criteria.
      </p>
      <p>Current PDF artifact: <a href="{pdf_href}">{html.escape(str(manifest.get("pdf", "")))}</a></p>
      {f'<p>Reference manifest: {html.escape(resolved_reference_manifest)}</p>' if resolved_reference_manifest else ''}
    </section>

    <section class="section">
      <p class="eyebrow">Source boundary</p>
      <h2>Reference evidence available for this review</h2>
      <ul>{source_boundary_html}</ul>
    </section>

    <section class="section">
      <p class="eyebrow">Reference spine</p>
      <h2>Professional report elements being compared</h2>
      <ul>{spine_html}</ul>
    </section>

    <section class="section">
      <p class="eyebrow">Manual review prompts</p>
      <h2>What to look for on the rendered pages</h2>
      <ul class="review-list">{checks_html}</ul>
    </section>

    <section class="section">
      <p class="eyebrow">Regeneration commands</p>
      <h2>Refresh this pack after changing report rendering</h2>
      <p>
        Run these from the repository root after changing valuation report content,
        PDF rendering, page selection, or parity criteria.
      </p>
      <div class="command-stack">{regen_commands_html}</div>
    </section>

    <section class="page-grid" aria-label="Rendered AccountIQ report pages">
      {page_cards}
    </section>
  </main>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
    return {
        "output_path": str(output_path),
        "manifest_path": str(manifest_path),
        "page_count": page_count,
        "target_count": target_count,
        "reference_count": reference_count,
        "reference_manifest_path": resolved_reference_manifest,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an AccountIQ valuation visual parity review HTML pack.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--parity-checklist", type=Path, default=DEFAULT_PARITY_CHECKLIST)
    parser.add_argument(
        "--reference-manifest",
        type=Path,
        default=None,
        help=(
            "Optional JSON file mapping original example-report page images to AccountIQ target labels. "
            f"Suggested location: {DEFAULT_REFERENCE_MANIFEST}"
        ),
    )
    parser.add_argument(
        "--write-reference-template",
        nargs="?",
        const=DEFAULT_REFERENCE_TEMPLATE,
        type=Path,
        default=None,
        help=(
            "Write a fill-in JSON template for mapping original example-report page images "
            "to AccountIQ target labels, then exit. Optionally pass an output path."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write_reference_template is not None:
            result = write_reference_manifest_template(
                manifest_path=args.manifest,
                output_path=args.write_reference_template,
            )
            print(json.dumps(result, indent=2))
            return 0
        result = build_visual_parity_pack(
            manifest_path=args.manifest,
            output_path=args.output,
            parity_checklist_path=args.parity_checklist,
            reference_manifest_path=args.reference_manifest,
        )
    except Exception as exc:
        print(f"Visual parity pack failed: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
