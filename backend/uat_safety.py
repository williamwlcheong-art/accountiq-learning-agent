"""Fail-closed safety and evidence helpers for live valuation UAT."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from report_validation import validate_generated_report


TRUTHY = {"1", "true", "yes", "on"}
SENSITIVE_KEY_PARTS = ("secret", "password", "token", "content", "narrative")


class UATSafetyError(RuntimeError):
    """Raised before UAT can reach any external or persistent side effect."""


@dataclass(frozen=True)
class UATPreflight:
    database_path: Path
    origin: str
    fixture_sha256: str


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUTHY


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and parsed.port is not None
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def require_safe_uat_environment(
    fixture_path: Path,
    fixture: dict,
    *,
    environ: dict[str, str] | os._Environ[str] | None = None,
    default_database_path: Path,
    repository_root: Path | None = None,
) -> UATPreflight:
    """Validate every live-UAT guard before backend modules are imported."""
    env = os.environ if environ is None else environ
    errors: list[str] = []

    if not _enabled(env.get("ACCOUNTIQ_UAT_MODE")):
        errors.append("ACCOUNTIQ_UAT_MODE must be explicitly true")

    production_markers = {
        name: env.get(name, "").strip().lower()
        for name in ("ACCOUNTIQ_ENV", "ENVIRONMENT", "NODE_ENV")
    }
    production_names = [name for name, value in production_markers.items() if value == "production"]
    if production_names:
        errors.append("production environment is forbidden: " + ", ".join(production_names))

    raw_db_path = env.get("ACCOUNTIQ_DB_PATH", "").strip()
    database_path = Path(raw_db_path).expanduser().resolve() if raw_db_path else None
    default_path = default_database_path.expanduser().resolve()
    if database_path is None:
        errors.append("ACCOUNTIQ_DB_PATH must name a disposable UAT database")
    else:
        if database_path == default_path:
            errors.append("ACCOUNTIQ_DB_PATH must not be the default application database")
        if repository_root is not None and database_path.is_relative_to(repository_root.resolve()):
            errors.append("ACCOUNTIQ_DB_PATH must be outside the repository")
        if database_path.exists():
            errors.append("ACCOUNTIQ_DB_PATH must not already exist")
        if database_path.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
            errors.append("ACCOUNTIQ_DB_PATH must be a SQLite database path")
        if not any(marker in database_path.name.lower() for marker in ("uat", "disposable", "tmp")):
            errors.append("ACCOUNTIQ_DB_PATH filename must identify it as UAT/disposable")

    origin = env.get("APP_BASE_URL", "").strip()
    if not _is_loopback_origin(origin):
        errors.append("APP_BASE_URL must be an explicit loopback origin with a port")

    fixture_kind = str(fixture.get("fixture_classification", "")).strip().lower()
    authorised = fixture.get("authorised_for_uat") is True
    if fixture_kind != "synthetic" and not authorised:
        errors.append("fixture must be synthetic or expressly authorised for UAT")

    email = str(fixture.get("uat_user", {}).get("email", "")).strip().lower()
    email_domain = email.rpartition("@")[2]
    if not email or not email_domain.endswith(".invalid"):
        errors.append("fixture UAT email must use the reserved .invalid domain")

    if _enabled(env.get("ACCOUNTIQ_E2E_MODE")):
        errors.append("ACCOUNTIQ_E2E_MODE must be false for live-model UAT")

    review_setting = env.get("ACCOUNTIQ_REQUIRE_ADMIN_REVIEW", "true")
    if not _enabled(review_setting):
        errors.append("ACCOUNTIQ_REQUIRE_ADMIN_REVIEW must be true for live-model UAT")

    refused = [
        name for name in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "SMTP_HOST",
            "SMTP_USER",
            "SMTP_PASSWORD",
            "FROM_EMAIL",
        )
        if env.get(name, "").strip()
    ]
    if refused:
        errors.append("payment/email configuration must be absent: " + ", ".join(refused))

    if not env.get("ANTHROPIC_API_KEY", "").strip():
        errors.append("ANTHROPIC_API_KEY must be configured for an explicitly run live UAT")

    if errors:
        raise UATSafetyError("Unsafe valuation UAT configuration:\n- " + "\n- ".join(errors))

    fixture_bytes = fixture_path.read_bytes()
    return UATPreflight(
        database_path=database_path,  # type: ignore[arg-type]
        origin=origin,
        fixture_sha256=_sha256_bytes(fixture_bytes),
    )


def evaluate_valuation_report(
    *,
    report_status: str,
    sections: dict,
    purchase_status: str,
    review_status: str | None,
) -> list[dict[str, object]]:
    """Return deterministic, narrative-free checks for a generated draft."""
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    add("awaiting_review", report_status == "awaiting_review", report_status)
    add("paid_fixture_purchase", purchase_status == "paid", purchase_status)
    add("review_record", review_status == "awaiting_review", str(review_status))

    try:
        validate_generated_report(sections, "valuation_advisory")
    except ValueError as exc:
        add("report_validation", False, str(exc))
    else:
        add("report_validation", True, "complete")
    return checks


def _is_sensitive_evidence_key(key: object) -> bool:
    lowered = str(key).lower()
    return (
        any(part in lowered for part in SENSITIVE_KEY_PARTS)
        or lowered == "key"
        or lowered.endswith("_key")
        or lowered.startswith("key_")
    )


def sanitise_evidence(value):
    """Recursively remove likely secrets and generated report prose from evidence."""
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if _is_sensitive_evidence_key(key):
                if item not in (None, ""):
                    clean[f"{key}_sha256"] = _sha256_bytes(str(item).encode())
                continue
            clean[key] = sanitise_evidence(item)
        return clean
    if isinstance(value, list):
        return [sanitise_evidence(item) for item in value]
    if isinstance(value, Path):
        return value.name
    return value


def write_immutable_json(path: Path, payload: dict) -> None:
    """Create evidence once; refuse overwrite and make it read-only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(sanitise_evidence(payload), indent=2, sort_keys=True).encode() + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
