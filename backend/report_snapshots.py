"""Create and verify immutable report-generation inputs."""
import hashlib
import json
from pathlib import Path

from financial_authority import authoritative_financial_rows

SNAPSHOT_SCHEMA_VERSION = "1"
VALUATION_ENGINE_VERSION = "typed-inputs-v2"


class SnapshotIntegrityError(RuntimeError):
    """Raised when a stored report snapshot no longer matches its digest."""


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_payload(
    manifest: list[dict],
    frozen_inputs: dict,
    rows: list[dict],
    schema_version: str,
    valuation_engine_version: str,
) -> str:
    payload = {
        "document_manifest": manifest,
        "frozen_inputs": frozen_inputs,
        "financial_rows": rows,
        "schema_version": schema_version,
        "valuation_engine_version": valuation_engine_version,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


async def build_report_input_snapshot_candidate(
    db,
    report_id: int | None = None,
    company_id: int | None = None,
    user_id: int | None = None,
    *,
    report_type: str | None = None,
    intake_answers: dict | None = None,
) -> dict:
    """Build canonical report inputs without persisting a snapshot."""
    if company_id is None or user_id is None:
        raise ValueError("company_id and user_id are required")
    if report_id is None and (report_type is None or intake_answers is None):
        raise ValueError(
            "report_type and intake_answers are required before report creation"
        )

    if report_id is not None:
        async with db.execute(
            """
            SELECT r.id, r.report_type, c.name, c.sector, c.description, c.country,
                   c.exchange, ri.answers
            FROM reports r
            JOIN companies c ON c.id=r.company_id AND c.user_id=r.user_id
            LEFT JOIN report_intake ri ON ri.report_id=r.id
            WHERE r.id=? AND r.company_id=? AND r.user_id=?
            ORDER BY ri.id DESC
            LIMIT 1
            """,
            (report_id, company_id, user_id),
        ) as cur:
            source = await cur.fetchone()
        if not source:
            raise ValueError("Report or owned company not found")
        report_type = source["report_type"]
        intake_answers = json.loads(source["answers"]) if source["answers"] else {}
    else:
        async with db.execute(
            """
            SELECT name, sector, description, country, exchange
            FROM companies
            WHERE id=? AND user_id=?
            """,
            (company_id, user_id),
        ) as cur:
            source = await cur.fetchone()
        if not source:
            raise ValueError("Owned company not found")

    financial_rows = await authoritative_financial_rows(db, company_id)
    if not financial_rows:
        raise ValueError("No completed authoritative financial data is available")

    document_ids = sorted({row["document_id"] for row in financial_rows})
    placeholders = ",".join("?" for _ in document_ids)
    async with db.execute(
        f"""
        SELECT id, filename, filepath, file_hash
        FROM documents
        WHERE company_id=? AND extraction_status='done' AND id IN ({placeholders})
        ORDER BY id
        """,
        [company_id, *document_ids],
    ) as cur:
        documents = [dict(row) for row in await cur.fetchall()]
    if len(documents) != len(document_ids):
        raise ValueError("Authoritative documents are unavailable")
    for document in documents:
        if document["file_hash"] or report_type != "valuation_advisory":
            continue
        retained_path = Path(document["filepath"])
        if not retained_path.is_file():
            raise ValueError(
                f"Authoritative source '{document['filename']}' cannot be verified because its retained file is missing"
            )
        digest = hashlib.sha256(retained_path.read_bytes()).hexdigest()
        await db.execute(
            "UPDATE documents SET file_hash=? WHERE id=? AND file_hash IS NULL",
            (digest, document["id"]),
        )
        document["file_hash"] = digest

    document_hashes = {document["id"]: document["file_hash"] for document in documents}
    slots_by_document = {document_id: set() for document_id in document_ids}
    for row in financial_rows:
        slots_by_document[row["document_id"]].add((row["statement"], row["period"]))

    manifest = []
    for document in documents:
        slots = sorted(slots_by_document[document["id"]])
        manifest.append({
            "document_id": document["id"],
            "filename": document["filename"],
            "file_hash": document["file_hash"],
            "slots": [{"statement": statement, "period": period} for statement, period in slots],
        })

    async with db.execute(
        "SELECT name, title, bio FROM management_team WHERE company_id=? ORDER BY id",
        (company_id,),
    ) as cur:
        management_team = [dict(row) for row in await cur.fetchall()]
    async with db.execute(
        "SELECT label, amount, rationale FROM ebitda_adjustments WHERE company_id=? ORDER BY id",
        (company_id,),
    ) as cur:
        adjustments = [dict(row) for row in await cur.fetchall()]

    frozen_inputs = {
        "company": {
            "name": source["name"],
            "sector": source["sector"],
            "description": source["description"],
            "country": source["country"],
            "exchange": source["exchange"],
        },
        "report_type": report_type,
        "management_team": management_team,
        "ebitda_adjustments": adjustments,
        "intake_answers": intake_answers,
    }
    rows = [
        {
            "document_id": row["document_id"],
            "document_hash": document_hashes[row["document_id"]],
            "statement": row["statement"],
            "row_key": row["row_key"],
            "row_label": row["row_label"],
            "period": row["period"],
            "value": row["value"],
            "currency": row["currency"],
            "unit": row["unit"],
            "source_text": row.get("source_text"),
            "confidence": row["confidence"],
        }
        for row in financial_rows
    ]
    rows.sort(key=lambda row: (
        row["statement"], row["row_key"], row["period"], row["document_id"]
    ))
    digest = _digest_payload(
        manifest, frozen_inputs, rows,
        SNAPSHOT_SCHEMA_VERSION, VALUATION_ENGINE_VERSION,
    )

    return {
        **frozen_inputs,
        "document_manifest": manifest,
        "financial_rows": rows,
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "valuation_engine_version": VALUATION_ENGINE_VERSION,
        "canonical_digest": digest,
    }


async def persist_report_input_snapshot(db, report_id: int, candidate: dict) -> int:
    """Persist an already built candidate without rereading mutable inputs."""
    async with db.execute(
        "SELECT id FROM report_input_snapshots WHERE report_id=?",
        (report_id,),
    ) as cur:
        existing = await cur.fetchone()
    if existing:
        return existing["id"]

    manifest = candidate["document_manifest"]
    rows = candidate["financial_rows"]
    frozen_inputs = {
        key: value
        for key, value in candidate.items()
        if key not in {
            "document_manifest",
            "financial_rows",
            "schema_version",
            "valuation_engine_version",
            "canonical_digest",
        }
    }
    schema_version = candidate["schema_version"]
    valuation_engine_version = candidate["valuation_engine_version"]
    digest = candidate["canonical_digest"]
    expected_digest = _digest_payload(
        manifest, frozen_inputs, rows, schema_version, valuation_engine_version
    )
    if digest != expected_digest:
        raise SnapshotIntegrityError("Candidate report snapshot digest verification failed")

    try:
        async with db.execute(
            """
            INSERT INTO report_input_snapshots
                (report_id, document_manifest, frozen_inputs, schema_version,
                 valuation_engine_version, canonical_digest)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                _canonical_json(manifest),
                _canonical_json(frozen_inputs),
                schema_version,
                valuation_engine_version,
                digest,
            ),
        ) as cur:
            snapshot_id = cur.lastrowid
    except Exception:
        async with db.execute(
            "SELECT id FROM report_input_snapshots WHERE report_id=?",
            (report_id,),
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            return existing["id"]
        raise

    await db.executemany(
        """
        INSERT INTO report_snapshot_rows
            (snapshot_id, document_id, statement, row_key, row_label, period,
             value, currency, unit, source_text, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                snapshot_id, row["document_id"], row["statement"], row["row_key"],
                row["row_label"], row["period"], row["value"], row["currency"],
                row["unit"], row["source_text"], row["confidence"],
            )
            for row in rows
        ],
    )
    return snapshot_id


async def create_report_input_snapshot(
    db,
    report_id: int,
    company_id: int,
    user_id: int,
) -> int:
    """Build and persist the report's authoritative inputs."""
    async with db.execute(
        "SELECT id FROM report_input_snapshots WHERE report_id=?",
        (report_id,),
    ) as cur:
        existing = await cur.fetchone()
    if existing:
        return existing["id"]

    candidate = await build_report_input_snapshot_candidate(
        db, report_id, company_id, user_id
    )
    return await persist_report_input_snapshot(db, report_id, candidate)


async def load_report_input_snapshot(db, report_id: int) -> dict:
    """Load a report snapshot and fail closed if its canonical digest changed."""
    async with db.execute(
        "SELECT * FROM report_input_snapshots WHERE report_id=?",
        (report_id,),
    ) as cur:
        snapshot = await cur.fetchone()
    if not snapshot:
        raise SnapshotIntegrityError("Report input snapshot is missing")
    if snapshot["schema_version"] != SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotIntegrityError("Unsupported report snapshot schema version")
    if snapshot["valuation_engine_version"] != VALUATION_ENGINE_VERSION:
        raise SnapshotIntegrityError("Unsupported valuation engine version")

    manifest = json.loads(snapshot["document_manifest"])
    frozen_inputs = json.loads(snapshot["frozen_inputs"])
    document_hashes = {row["document_id"]: row["file_hash"] for row in manifest}
    async with db.execute(
        """
        SELECT document_id, statement, row_key, row_label, period, value,
               currency, unit, source_text, confidence
        FROM report_snapshot_rows
        WHERE snapshot_id=?
        ORDER BY statement, row_key, period, document_id
        """,
        (snapshot["id"],),
    ) as cur:
        rows = [dict(row) for row in await cur.fetchall()]
    for row in rows:
        row["document_hash"] = document_hashes.get(row["document_id"])

    actual_digest = _digest_payload(
        manifest, frozen_inputs, rows,
        snapshot["schema_version"], snapshot["valuation_engine_version"],
    )
    if actual_digest != snapshot["canonical_digest"]:
        raise SnapshotIntegrityError("Report input snapshot digest verification failed")

    return {
        **frozen_inputs,
        "document_manifest": manifest,
        "financial_rows": rows,
        "schema_version": snapshot["schema_version"],
        "valuation_engine_version": snapshot["valuation_engine_version"],
        "canonical_digest": snapshot["canonical_digest"],
    }
