"""Render original example-report PDF pages for visual parity review.

This helper converts selected pages from supplied reference/example PDFs into
PNG files and writes the ``reference-manifest.json`` consumed by
``build_valuation_visual_parity_pack.py --reference-manifest``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "tmp" / "pdfs" / "reference-examples" / "reference-pdf-map.json"
DEFAULT_SPEC_TEMPLATE = ROOT / "tmp" / "pdfs" / "reference-examples" / "reference-pdf-map.template.json"
DEFAULT_OUTPUT_DIR = ROOT / "tmp" / "pdfs" / "reference-examples"
DEFAULT_REFERENCE_MANIFEST = ROOT / "tmp" / "pdfs" / "reference-examples" / "reference-manifest.json"
DEFAULT_PREVIEW_MANIFEST = (
    ROOT
    / "tmp"
    / "pdfs"
    / "valuation-preview"
    / "accountiq-demo-sample-indicative-valuation-preview-manifest.json"
)


def _slug(value: object, *, fallback: str = "reference") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return text or fallback


def _resolve_path(value: object, *, base_dir: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a non-empty file path.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _targets(value: object, *, index: int) -> str | list[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
        return [item.strip() for item in value]
    raise ValueError(f"Reference page entry {index} must include accountiq_target as a string or non-empty list.")


def _pdftoppm_binary() -> str:
    binary = shutil.which("pdftoppm")
    if not binary:
        raise RuntimeError("pdftoppm is required. Install Poppler or use the bundled Codex runtime.")
    return binary


def _render_pdf_page(
    *,
    pdf_path: Path,
    page_number: int,
    output_path: Path,
    resolution: int,
    binary: str,
    cache_dir: Path,
) -> None:
    prefix = output_path.with_suffix("")
    temporary_prefix = output_path.parent / f".render-{prefix.name}"
    for stale in output_path.parent.glob(f"{temporary_prefix.name}-*.png"):
        stale.unlink()
    output_path.unlink(missing_ok=True)

    env = os.environ.copy()
    env["XDG_CACHE_HOME"] = str(cache_dir)
    result = subprocess.run(
        [
            binary,
            "-png",
            "-r",
            str(int(resolution)),
            "-f",
            str(int(page_number)),
            "-l",
            str(int(page_number)),
            str(pdf_path),
            str(temporary_prefix),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pdftoppm failed for {pdf_path.name} page {page_number}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    matches = sorted(output_path.parent.glob(f"{temporary_prefix.name}-*.png"))
    if not matches:
        raise RuntimeError(f"pdftoppm did not create a PNG for {pdf_path.name} page {page_number}")
    matches[0].replace(output_path)
    for extra in matches[1:]:
        extra.unlink()


def write_reference_pdf_map_template(
    *,
    preview_manifest_path: Path = DEFAULT_PREVIEW_MANIFEST,
    output_path: Path = DEFAULT_SPEC_TEMPLATE,
) -> dict:
    """Write a fill-in template mapping original PDFs/pages to AccountIQ targets."""
    preview_manifest_path = preview_manifest_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    payload = json.loads(preview_manifest_path.read_text(encoding="utf-8"))
    targets = payload.get("page_targets") if isinstance(payload, dict) else None
    if not isinstance(targets, list) or not targets:
        raise ValueError("Preview manifest must include page_targets.")

    pages: list[dict] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        label = str(target.get("label") or "").strip()
        if not label:
            continue
        markers = ", ".join(str(marker) for marker in target.get("markers") or [])
        pages.append(
            {
                "page": None,
                "accountiq_target": label,
                "title": "",
                "notes": f"AccountIQ target markers: {markers}",
            }
        )

    template = {
        "instructions": [
            "Copy this file to reference-pdf-map.json.",
            "Set source and pdf for each original example report.",
            "Set page for each reference page you want rendered, or delete unused rows.",
            "Run: python scripts/render_reference_pdf_pages.py --spec tmp/pdfs/reference-examples/reference-pdf-map.json",
            "Then run: python scripts/build_valuation_visual_parity_pack.py --reference-manifest tmp/pdfs/reference-examples/reference-manifest.json",
        ],
        "references": [
            {
                "source": "",
                "pdf": "",
                "pages": pages,
            }
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return {
        "template_path": str(output_path),
        "preview_manifest_path": str(preview_manifest_path),
        "reference_page_rows": len(pages),
    }


def render_reference_pdf_pages(
    *,
    spec_path: Path = DEFAULT_SPEC,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    reference_manifest_path: Path = DEFAULT_REFERENCE_MANIFEST,
    resolution: int = 110,
) -> dict:
    """Render reference PDF pages and write a pack-builder reference manifest."""
    spec_path = spec_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    reference_manifest_path = reference_manifest_path.expanduser().resolve()
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    references = payload.get("references") if isinstance(payload, dict) else None
    if not isinstance(references, list) or not references:
        raise ValueError("Reference PDF map must include a non-empty references array.")

    output_dir.mkdir(parents=True, exist_ok=True)
    reference_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / ".font-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    binary = _pdftoppm_binary()

    rendered_entries: list[dict] = []
    rendered_pdf_paths: set[str] = set()
    for reference_index, reference in enumerate(references, start=1):
        if not isinstance(reference, dict):
            raise ValueError(f"Reference PDF entry {reference_index} must be an object.")
        source = str(reference.get("source") or f"Reference example {reference_index}").strip()
        pdf_path = _resolve_path(reference.get("pdf"), base_dir=spec_path.parent)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Reference PDF does not exist: {pdf_path}")
        if not pdf_path.read_bytes().startswith(b"%PDF-"):
            raise ValueError(f"Reference file does not look like a PDF: {pdf_path}")
        rendered_pdf_paths.add(str(pdf_path))
        pages = reference.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError(f"Reference PDF entry {reference_index} must include a non-empty pages array.")

        source_slug = _slug(source, fallback=f"reference-{reference_index}")
        for page_index, page_entry in enumerate(pages, start=1):
            if not isinstance(page_entry, dict):
                raise ValueError(f"Reference page entry {page_index} must be an object.")
            page_number = page_entry.get("page")
            if not isinstance(page_number, int) or page_number <= 0:
                raise ValueError(f"Reference page entry {page_index} must include a positive integer page.")
            output_name = f"{source_slug}-page-{page_number:03d}.png"
            output_path = output_dir / output_name
            _render_pdf_page(
                pdf_path=pdf_path,
                page_number=page_number,
                output_path=output_path,
                resolution=resolution,
                binary=binary,
                cache_dir=cache_dir,
            )
            rendered_entries.append(
                {
                    "accountiq_target": _targets(page_entry.get("accountiq_target"), index=page_index),
                    "title": str(page_entry.get("title") or f"{source} page {page_number}"),
                    "source": source,
                    "path": output_path.relative_to(reference_manifest_path.parent).as_posix(),
                    "notes": str(page_entry.get("notes") or f"Rendered from {pdf_path.name} page {page_number}."),
                }
            )

    manifest = {
        "generated_from": str(spec_path),
        "references": rendered_entries,
    }
    reference_manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "spec_path": str(spec_path),
        "output_dir": str(output_dir),
        "reference_manifest_path": str(reference_manifest_path),
        "reference_count": len(rendered_entries),
        "pdf_count": len(rendered_pdf_paths),
        "resolution": int(resolution),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render selected original example-report PDF pages for AccountIQ visual parity review.",
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reference-manifest", type=Path, default=DEFAULT_REFERENCE_MANIFEST)
    parser.add_argument("--resolution", type=int, default=110)
    parser.add_argument(
        "--write-template",
        nargs="?",
        const=DEFAULT_SPEC_TEMPLATE,
        type=Path,
        default=None,
        help="Write a fill-in reference PDF/page mapping template and exit. Optionally pass an output path.",
    )
    parser.add_argument("--preview-manifest", type=Path, default=DEFAULT_PREVIEW_MANIFEST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write_template is not None:
            result = write_reference_pdf_map_template(
                preview_manifest_path=args.preview_manifest,
                output_path=args.write_template,
            )
        else:
            result = render_reference_pdf_pages(
                spec_path=args.spec,
                output_dir=args.output_dir,
                reference_manifest_path=args.reference_manifest,
                resolution=args.resolution,
            )
    except Exception as exc:
        print(f"Reference PDF rendering failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
