"""Unit tests for wizard-scoped endpoints (Phase 05.1)."""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app


def test_wizard_ebitda_endpoint_exists():
    """Route is registered (no 404 on the path itself)."""
    routes = {
        (r.path, tuple(sorted(r.methods or [])))
        for r in app.routes
        if hasattr(r, "path") and hasattr(r, "methods")
    }
    assert ("/wizard/company/{company_id}/ebitda-adjustments", ("GET",)) in routes, \
        f"Wizard ebitda-adjustments route missing. Found wizard routes: " \
        f"{[(path, methods) for path, methods in routes if '/wizard/' in path]}"


def test_wizard_ebitda_endpoint_requires_auth():
    """Unauthenticated request → 401."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/wizard/company/1/ebitda-adjustments")
    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


def test_wizard_ebitda_endpoint_does_not_require_admin():
    """The route must NOT use Depends(require_admin). Static check."""
    import inspect
    from main import wizard_get_ebitda_adjustments
    sig = inspect.signature(wizard_get_ebitda_adjustments)
    deps = []
    for p in sig.parameters.values():
        if p.default and hasattr(p.default, "dependency"):
            deps.append(getattr(p.default.dependency, "__name__", str(p.default.dependency)))
    assert "require_admin" not in deps, \
        f"wizard_get_ebitda_adjustments must NOT depend on require_admin. Found: {deps}"
    assert any("get_current_user" in d for d in deps), \
        f"wizard_get_ebitda_adjustments must depend on get_current_user. Found: {deps}"
