"""Select the document revision authorised for each financial statement period."""


class AuthorityConflictError(RuntimeError):
    """Raised when completed sources overlap without an explicit assignment."""

    def __init__(self, conflicts: list[dict]):
        self.conflicts = conflicts
        super().__init__("Financial document authority conflict")


async def _document_slots(db, document_id: int) -> list[tuple[str, str]]:
    async with db.execute(
        """
        SELECT DISTINCT statement, period
        FROM financial_rows
        WHERE document_id=?
        ORDER BY statement, period
        """,
        (document_id,),
    ) as cur:
        return [(row["statement"], row["period"]) for row in await cur.fetchall()]


async def _superseded_revision_ids(db, document_id: int) -> set[int]:
    revision_ids = set()
    current_id = document_id
    while current_id:
        async with db.execute(
            "SELECT supersedes_document_id FROM documents WHERE id=?",
            (current_id,),
        ) as cur:
            row = await cur.fetchone()
        current_id = row["supersedes_document_id"] if row else None
        if current_id is not None:
            if current_id in revision_ids:
                raise ValueError("Document revision chain contains a cycle")
            revision_ids.add(current_id)
    return revision_ids


async def _has_newer_revision(db, document_id: int) -> bool:
    """Return whether this revision has a newer descendant in its chain."""
    pending_ids = [document_id]
    visited = {document_id}
    while pending_ids:
        current_id = pending_ids.pop()
        async with db.execute(
            "SELECT id FROM documents WHERE supersedes_document_id=?",
            (current_id,),
        ) as cur:
            descendants = await cur.fetchall()
        for row in descendants:
            descendant_id = row["id"]
            if descendant_id in visited:
                raise ValueError("Document revision chain contains a cycle")
            visited.add(descendant_id)
            pending_ids.append(descendant_id)
    return len(visited) > 1


async def _assign_document_authority(db, document_id: int) -> None:
    """Assign authority while the caller holds the write transaction."""
    async with db.execute(
        """
        SELECT company_id, extraction_status, extraction_completed_at,
               supersedes_document_id
        FROM documents
        WHERE id=?
        """,
        (document_id,),
    ) as cur:
        document = await cur.fetchone()
    if not document:
        raise ValueError("Document not found")
    if document["extraction_status"] != "done" or not document["extraction_completed_at"]:
        raise ValueError("Document must have a completed extraction")
    if await _has_newer_revision(db, document_id):
        raise ValueError("A newer document revision exists")

    slots = await _document_slots(db, document_id)
    superseded_revision_ids = await _superseded_revision_ids(db, document_id)
    conflicts = []
    assignments = []
    for statement, period in slots:
        async with db.execute(
            """
            SELECT document_id
            FROM document_authority
            WHERE company_id=? AND statement=? AND period=?
            """,
            (document["company_id"], statement, period),
        ) as cur:
            authority = await cur.fetchone()

        current_document_id = authority["document_id"] if authority else None
        can_replace = (
            current_document_id is None
            or current_document_id == document_id
            or current_document_id in superseded_revision_ids
        )
        if can_replace:
            assignments.append((statement, period, current_document_id))
        else:
            conflicts.append({
                "statement": statement,
                "period": period,
                "document_id": current_document_id,
            })

    if conflicts:
        raise AuthorityConflictError(conflicts)

    for statement, period, expected_document_id in assignments:
        if expected_document_id is None:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO document_authority
                    (company_id, statement, period, document_id)
                VALUES (?, ?, ?, ?)
                """,
                (document["company_id"], statement, period, document_id),
            )
        else:
            cursor = await db.execute(
                """
                UPDATE document_authority
                SET document_id=?, assigned_at=datetime('now')
                WHERE company_id=? AND statement=? AND period=?
                  AND document_id=?
                """,
                (
                    document_id,
                    document["company_id"],
                    statement,
                    period,
                    expected_document_id,
                ),
            )
        if cursor.rowcount != 1:
            raise AuthorityConflictError([{
                "statement": statement,
                "period": period,
                "document_id": expected_document_id,
            }])


async def claim_document_retry(db, document_id: int, user_id: int) -> bool:
    """Atomically claim an eligible non-authoritative revision for retry."""
    await db.execute("BEGIN IMMEDIATE")
    try:
        cursor = await db.execute(
            """
            UPDATE documents
            SET extraction_status='processing', updated_at=datetime('now')
            WHERE id=? AND user_id=?
              AND extraction_status IN ('pending', 'failed')
              AND NOT EXISTS (
                  SELECT 1 FROM document_authority da WHERE da.document_id=documents.id
              )
            """,
            (document_id, user_id),
        )
        await db.commit()
        return cursor.rowcount == 1
    except Exception:
        await db.rollback()
        raise


async def complete_document_authority(
    db,
    document_id: int,
    confidence_score: float,
) -> None:
    """Publish extraction completion and authority in one transaction."""
    await db.execute("BEGIN IMMEDIATE")
    try:
        cursor = await db.execute(
            """
            UPDATE documents SET
                extraction_status='done',
                confidence_score=?,
                extraction_completed_at=datetime('now'),
                updated_at=datetime('now')
            WHERE id=? AND extraction_status='processing'
            """,
            (confidence_score, document_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Document is not processing")
        await _assign_document_authority(db, document_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def promote_document_authority(db, document_id: int) -> None:
    """Atomically assign a completed revision where no conflict exists."""
    await db.execute("BEGIN IMMEDIATE")
    try:
        await _assign_document_authority(db, document_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def authoritative_financial_rows(
    db,
    company_id: int,
    statement: str | None = None,
) -> list[dict]:
    """Return only rows from explicitly authorised completed revisions."""
    params: list = [company_id]
    statement_filter = ""
    if statement:
        statement_filter = " AND fr.statement=?"
        params.append(statement)

    async with db.execute(
        f"""
        SELECT fr.statement, fr.row_key, fr.row_label, fr.period, fr.value,
               fr.currency, fr.unit, fr.source_text, fr.confidence, fr.document_id
        FROM financial_rows fr
        JOIN documents d ON d.id=fr.document_id
        JOIN document_authority da
          ON da.company_id=fr.company_id
         AND da.statement=fr.statement
         AND da.period=fr.period
         AND da.document_id=fr.document_id
        WHERE fr.company_id=? AND d.extraction_status='done'
              {statement_filter}
        ORDER BY fr.statement, fr.row_key, fr.period DESC
        """,
        params,
    ) as cur:
        rows = [dict(row) for row in await cur.fetchall()]

    conflict_params: list = [company_id]
    conflict_filter = ""
    if statement:
        conflict_filter = " AND fr.statement=?"
        conflict_params.append(statement)
    async with db.execute(
        f"""
        SELECT fr.statement, fr.period, fr.document_id, da.document_id AS authority_document_id
        FROM financial_rows fr
        JOIN documents d ON d.id=fr.document_id AND d.extraction_status='done'
        LEFT JOIN document_authority da
          ON da.company_id=fr.company_id
         AND da.statement=fr.statement
         AND da.period=fr.period
        WHERE fr.company_id=?
              {conflict_filter}
        GROUP BY fr.statement, fr.period, fr.document_id, da.document_id
        ORDER BY fr.statement, fr.period, fr.document_id
        """,
        conflict_params,
    ) as cur:
        candidates = [dict(row) for row in await cur.fetchall()]

    unresolved: set[tuple[str, str, int]] = set()
    slot_counts: dict[tuple[str, str], int] = {}
    ancestor_cache: dict[int, set[int]] = {}

    async def ancestors(document_id: int) -> set[int]:
        if document_id not in ancestor_cache:
            ancestor_cache[document_id] = await _superseded_revision_ids(db, document_id)
        return ancestor_cache[document_id]

    for candidate in candidates:
        slot = (candidate["statement"], candidate["period"])
        slot_counts[slot] = slot_counts.get(slot, 0) + 1
    for candidate in candidates:
        authority_id = candidate["authority_document_id"]
        candidate_id = candidate["document_id"]
        slot = (candidate["statement"], candidate["period"])
        if authority_id is None:
            if slot_counts[slot] > 1:
                unresolved.add((*slot, candidate_id))
            continue
        if candidate_id == authority_id:
            continue
        authority_ancestors = await ancestors(authority_id)
        candidate_ancestors = await ancestors(candidate_id)
        if candidate_id in authority_ancestors or authority_id in candidate_ancestors:
            continue
        unresolved.add((*slot, candidate_id))
    if unresolved:
        raise AuthorityConflictError([
            {"statement": statement, "period": period, "document_id": document_id}
            for statement, period, document_id in sorted(unresolved)
        ])

    return rows
