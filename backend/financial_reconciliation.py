"""Reconcile financial rows selected from one or more uploaded statements.

The wizard permits a user to upload a pack of statements (for example, an
annual report plus management accounts).  This module keeps the source trail
intact, normalises equivalent fiscal-year labels and units, and makes a user
choose whenever materially different overlapping figures are found.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re


_UNIT_MULTIPLIERS = {
    "whole": 1.0,
    "ones": 1.0,
    "unit": 1.0,
    "units": 1.0,
    "thousand": 1_000.0,
    "thousands": 1_000.0,
    "000": 1_000.0,
    "000s": 1_000.0,
    "$000": 1_000.0,
    "million": 1_000_000.0,
    "millions": 1_000_000.0,
    "m": 1_000_000.0,
    "$m": 1_000_000.0,
}


BALANCE_SHEET_CLASSIFICATIONS = {
    "cash_and_bank": "Cash and bank",
    "trade_debtors": "Accounts receivable",
    "inventory": "Stock / inventory",
    "other_current_assets": "Other current assets",
    "total_current_assets": "Total current assets",
    "fixed_assets_net": "Fixed assets",
    "property_plant_equipment": "Fixed assets",
    "total_fixed_assets": "Fixed assets",
    "other_noncurrent_assets": "Other non-current assets",
    "total_assets": "Total assets",
    "trade_creditors": "Accounts payable",
    "short_term_debt": "Short-term loans",
    "other_current_liab": "Other current liabilities",
    "total_current_liab": "Total current liabilities",
    "long_term_debt": "Long-term loans",
    "other_noncurrent_liab": "Other non-current liabilities",
    "total_liabilities": "Total liabilities",
    "shareholders_equity": "Shareholders' equity / net assets",
}


def normalise_financial_period(value: object) -> str:
    """Return one stable fiscal-year label for common account-period formats."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return "Unspecified period"

    range_match = re.search(r"(?<!\d)((?:19|20)\d{2})\s*[/\-.]\s*(\d{2})(?!\d)", text)
    if range_match:
        start_year = int(range_match.group(1))
        end_suffix = int(range_match.group(2))
        century = start_year - (start_year % 100)
        end_year = century + end_suffix
        if end_year < start_year:
            end_year += 100
        return f"FY{end_year}"

    years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    if years:
        return f"FY{int(years[-1])}"

    short_years = re.findall(r"(?<!\d)(\d{2})(?!\d)", text)
    if short_years and re.search(r"(?:fy|year|ended|march|june|september|december|jan|feb|mar|apr|may|jul|aug|sep|oct|nov|dec)", text.lower()):
        year = int(short_years[-1])
        return f"FY{2000 + year if year < 80 else 1900 + year}"
    return text


def _unit_multiplier(unit: object) -> float:
    cleaned = re.sub(r"\s+", "", str(unit or "whole").lower())
    return _UNIT_MULTIPLIERS.get(cleaned, 1.0)


def _normalised_value(value: object, unit: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number * _unit_multiplier(unit)


def _values_agree(candidates: list[dict]) -> bool:
    values = [float(candidate["value"]) for candidate in candidates]
    if not values:
        return True
    spread = max(values) - min(values)
    tolerance = max(1.0, max(abs(value) for value in values) * 0.005)
    currencies = {str(candidate.get("currency") or "").upper() for candidate in candidates}
    return spread <= tolerance and len(currencies) <= 1


def _candidate_sort_key(candidate: dict) -> tuple[float, int, str]:
    try:
        confidence = float(candidate.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return (-confidence, int(candidate.get("document_id") or 0), str(candidate.get("filename") or ""))


def _conflict_id(statement: str, row_key: str, period: str) -> str:
    return f"{statement}:{row_key}:{period}"


def _balance_sheet_review(rows: list[dict]) -> dict:
    by_period: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if str(row.get("statement") or "").lower() == "bs":
            by_period[str(row.get("period") or "Unspecified period")].append(row)

    period_reviews: list[dict] = []
    warnings: list[str] = []
    issues: list[str] = []
    required_categories = (
        "cash_and_bank",
        "trade_debtors",
        "inventory",
        "fixed_assets_net",
        "trade_creditors",
        "short_term_debt",
        "long_term_debt",
    )

    for period in sorted(by_period):
        entries = by_period[period]
        by_key = {str(entry.get("row_key") or "").lower(): entry for entry in entries}
        unclassified = [
            str(entry.get("row_label") or entry.get("row_key") or "Unknown line")
            for entry in entries
            if str(entry.get("row_key") or "").lower() not in BALANCE_SHEET_CLASSIFICATIONS
        ]
        missing = [key for key in required_categories if key not in by_key]
        classifications = [
            {
                "key": key,
                "label": BALANCE_SHEET_CLASSIFICATIONS.get(key, str(entry.get("row_label") or key)),
                "value": entry.get("value"),
                "source_filename": entry.get("source_filename"),
            }
            for key, entry in sorted(by_key.items())
            if key in BALANCE_SHEET_CLASSIFICATIONS
        ]

        assets = by_key.get("total_assets", {}).get("value")
        liabilities = by_key.get("total_liabilities", {}).get("value")
        equity = by_key.get("shareholders_equity", {}).get("value")
        checks: list[dict] = []
        if assets is not None and liabilities is not None and equity is not None:
            difference = float(assets) - float(liabilities) - float(equity)
            tolerance = max(1.0, abs(float(assets)) * 0.005)
            status = "balanced" if abs(difference) <= tolerance else "unbalanced"
            checks.append(
                {
                    "name": "Assets = liabilities + equity",
                    "status": status,
                    "difference": round(difference, 2),
                }
            )
            if status == "unbalanced":
                issues.append(f"{period}: total assets do not reconcile to total liabilities plus equity.")

        current_asset_total = by_key.get("total_current_assets", {}).get("value")
        current_asset_components = sum(
            float(by_key[key]["value"])
            for key in ("cash_and_bank", "trade_debtors", "inventory", "other_current_assets")
            if key in by_key
        )
        if current_asset_total is not None and current_asset_components:
            difference = float(current_asset_total) - current_asset_components
            tolerance = max(1.0, abs(float(current_asset_total)) * 0.01)
            checks.append(
                {
                    "name": "Current-asset components",
                    "status": "reconciled" if abs(difference) <= tolerance else "review",
                    "difference": round(difference, 2),
                }
            )

        current_liability_total = by_key.get("total_current_liab", {}).get("value")
        current_liability_components = sum(
            float(by_key[key]["value"])
            for key in ("trade_creditors", "short_term_debt", "other_current_liab")
            if key in by_key
        )
        if current_liability_total is not None and current_liability_components:
            difference = float(current_liability_total) - current_liability_components
            tolerance = max(1.0, abs(float(current_liability_total)) * 0.01)
            checks.append(
                {
                    "name": "Current-liability components",
                    "status": "reconciled" if abs(difference) <= tolerance else "review",
                    "difference": round(difference, 2),
                }
            )

        if missing:
            warnings.append(
                f"{period}: some balance-sheet categories were not extracted ({', '.join(missing)})."
            )
        if unclassified:
            warnings.append(f"{period}: unclassified balance-sheet lines need review ({', '.join(unclassified)}).")
        period_reviews.append(
            {
                "period": period,
                "classifications": classifications,
                "missing_categories": missing,
                "unclassified_lines": unclassified,
                "checks": checks,
            }
        )

    return {
        "ready": bool(period_reviews) and not issues,
        "periods": period_reviews,
        "warnings": warnings,
        "issues": issues,
    }


def reconcile_financial_rows(
    financial_rows: list[dict],
    *,
    overrides: dict[str, int] | None = None,
) -> dict:
    """Consolidate selected source rows and expose material overlaps for review.

    ``overrides`` maps a stable conflict ID to the document ID chosen by the
    user.  It is intentionally source-level rather than value-level so the
    resulting valuation and credit paper retain an auditable source path.
    """
    overrides = overrides or {}
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    warnings: list[str] = []

    for source_row in financial_rows:
        if not isinstance(source_row, dict):
            continue
        statement = str(source_row.get("statement") or "").strip().lower()
        row_key = str(source_row.get("row_key") or source_row.get("canonical_key") or "").strip().lower()
        if not statement or not row_key:
            continue
        value = _normalised_value(source_row.get("value"), source_row.get("unit"))
        if value is None:
            continue
        period = normalise_financial_period(source_row.get("period"))
        grouped[(statement, row_key, period)].append(
            {
                "document_id": int(source_row.get("document_id") or 0),
                "filename": str(source_row.get("filename") or source_row.get("source_filename") or "Uploaded statement"),
                "statement": statement,
                "row_key": row_key,
                "row_label": str(source_row.get("row_label") or row_key.replace("_", " ").title()),
                "period": period,
                "value": value,
                "currency": str(source_row.get("currency") or "NZD").upper(),
                "confidence": source_row.get("confidence"),
            }
        )

    reconciled_rows: list[dict] = []
    conflicts: list[dict] = []
    unresolved_conflicts: list[str] = []
    invalid_overrides: list[str] = []

    for (statement, row_key, period), source_candidates in sorted(grouped.items()):
        candidates_by_document: dict[int, dict] = {}
        for candidate in sorted(source_candidates, key=_candidate_sort_key):
            document_id = int(candidate.get("document_id") or 0)
            existing = candidates_by_document.get(document_id)
            if existing is None:
                candidates_by_document[document_id] = candidate
            elif not _values_agree([existing, candidate]):
                warnings.append(
                    f"{candidate['filename']} contains conflicting extracted values for "
                    f"{candidate['row_label']} in {period}; the highest-confidence extraction was retained."
                )
        candidates = list(candidates_by_document.values())
        preferred = sorted(candidates, key=_candidate_sort_key)[0]
        conflict_id = _conflict_id(statement, row_key, period)
        material_conflict = len(candidates) > 1 and not _values_agree(candidates)
        selected = preferred

        if material_conflict:
            requested_document_id = overrides.get(conflict_id)
            if requested_document_id is not None:
                selected_candidate = candidates_by_document.get(int(requested_document_id))
                if selected_candidate is None:
                    invalid_overrides.append(conflict_id)
                else:
                    selected = selected_candidate
            else:
                unresolved_conflicts.append(conflict_id)
            conflicts.append(
                {
                    "id": conflict_id,
                    "statement": statement,
                    "row_key": row_key,
                    "row_label": preferred["row_label"],
                    "period": period,
                    "suggested_document_id": preferred["document_id"],
                    "selected_document_id": selected["document_id"],
                    "resolved": conflict_id not in unresolved_conflicts and conflict_id not in invalid_overrides,
                    "sources": [
                        {
                            "document_id": candidate["document_id"],
                            "filename": candidate["filename"],
                            "value": candidate["value"],
                            "currency": candidate["currency"],
                            "confidence": candidate["confidence"],
                        }
                        for candidate in sorted(candidates, key=_candidate_sort_key)
                    ],
                }
            )

        reconciled_rows.append(
            {
                "document_id": selected["document_id"],
                "source_filename": selected["filename"],
                "statement": statement,
                "row_key": row_key,
                "row_label": selected["row_label"],
                "period": period,
                "value": selected["value"],
                "currency": selected["currency"],
                "confidence": selected["confidence"],
            }
        )

    for override_id in overrides:
        if override_id not in {conflict["id"] for conflict in conflicts}:
            invalid_overrides.append(override_id)

    balance_sheet = _balance_sheet_review(reconciled_rows)
    return {
        "status": "needs_review" if unresolved_conflicts or invalid_overrides else "ready",
        "rows": reconciled_rows,
        "conflicts": conflicts,
        "unresolved_conflict_ids": unresolved_conflicts,
        "invalid_override_ids": sorted(set(invalid_overrides)),
        "warnings": warnings,
        "balance_sheet": balance_sheet,
    }
