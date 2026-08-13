"""
Agentic web-search research loop for business valuation.

Public API
----------
WEB_SEARCH_TOOL          - OpenAI Responses API web_search tool config dict
RESEARCH_SYSTEM_PROMPT   - Static system prompt for the research loop
ResearchBrief            - Pydantic v2 model (9 fields) — validated output of the loop
run_research_loop_sync   - Synchronous entry point; call via run_in_executor from async code
run_valuation_research   - Async entry point for FastAPI background tasks

Design decisions:
- D-R1: OpenAI Responses API hosted web_search tool (no client-side dispatch)
- D-R2: the research prompt prioritises management-supplied public sources
- D-R3: the model performs its own bounded search plan inside one Responses API call
- D-R4: a retry ceiling prevents repeated rate-limit retries
- D-R5: ResearchBrief is an immutable Pydantic v2 model — consumers cannot mutate
         WACC inputs after validation

See: .planning/phases/05.1-valuation-advisory-redesign/05.1-AI-SPEC.md Section 4
See: .planning/phases/05.1-valuation-advisory-redesign/05.1-CONTEXT.md decisions D-R1..D-R5
"""

import os
import json
import asyncio
import logging
import ipaddress
import re
import time
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults captured at import for diagnostics. Runtime calls re-read the
# environment so credentials saved through Admin Settings apply immediately.
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
MAX_TOKENS_RESEARCH = 8000

# ---------------------------------------------------------------------------
# Web search tool definition (AI-SPEC Section 4 lines 303-312)
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {"type": "web_search"}


def _create_openai_client(api_key: str):
    """Create the optional OpenAI SDK client only when live AI is configured."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI SDK is not installed. Install backend requirements before using live AI research."
        ) from exc
    return OpenAI(api_key=api_key)

# ---------------------------------------------------------------------------
# System prompt (AI-SPEC Section 4 lines 314-341)
# ---------------------------------------------------------------------------

RESEARCH_SYSTEM_PROMPT = """You are a financial research analyst preparing inputs for a business valuation.
Your task: research the company and sector, find comparable transactions, and retrieve current WACC inputs
from authoritative NZ sources (RBNZ, Damodaran, Stats NZ).

Research in this order:
1. Company research — name, location, business model, notable clients, recent news, significant events.
2. Sector research — NZ market context, growth rates, competitors, regulatory environment.
3. Comparable M&A transactions — recent (within 3 years) NZ/ANZ sector deals with disclosed EV/EBITDA multiples.
   From these transactions, determine a realistic low and high EV/EBITDA multiple range for this sector.
   If fewer than 2 transactions are found, use Damodaran sector EV/EBITDA data for NZ private SMEs as a fallback.
   Typical NZ SME ranges: 2.5–4.5x for commodity/cyclical sectors; 4.0–7.0x for service/recurring-revenue businesses.
4. WACC inputs — RBNZ 10-yr NZ govt bond yield (risk-free rate), Damodaran current-year ERP for NZ
   and total beta for the relevant industry, Stats NZ / RBNZ current NZ CPI inflation rate.

When you have sufficient data for all four categories, output a JSON object ONLY (no surrounding text)
with this exact schema:

{
  "company_summary": "string — 2-3 paragraph narrative",
  "sector_summary": "string — 2-3 paragraph narrative",
  "comparable_transactions": "string — bullet list of transactions with EV/EBITDA multiples",
  "ev_ebitda_low": float,             // e.g. 3.5  — low end of comparable transaction multiple range
  "ev_ebitda_high": float,            // e.g. 6.0  — high end of comparable transaction multiple range
  "risk_free_rate": float,            // e.g. 4.65  (percent, not decimal)
  "erp": float,                       // e.g. 5.94
  "industry_beta": float,             // e.g. 1.08  (total beta from Damodaran)
  "industry_category": "string",      // Damodaran industry category used for beta
  "inflation_rate": float,            // e.g. 2.5
  "sources": ["https://...", "https://...", ...] // full http(s) source URLs cited; no bare domains or host-only strings
}

CRITICAL: Do not return the JSON until you have retrieved risk_free_rate, erp, and industry_beta
from actual web search results. These values must come from RBNZ or Damodaran — do not estimate them.
ev_ebitda_low must be less than ev_ebitda_high, and both must be positive.
Every entry in sources must be a full http:// or https:// URL that can be rendered as a clickable report link."""


# ---------------------------------------------------------------------------
# Pydantic model (AI-SPEC Section 4 lines 344-353)
# ---------------------------------------------------------------------------

class ResearchBrief(BaseModel):
    company_summary: str = Field(min_length=50)
    sector_summary: str = Field(min_length=50)
    comparable_transactions: str = Field(min_length=20)
    ev_ebitda_low: float = Field(gt=0, lt=30)        # low end of market comparable multiple range
    ev_ebitda_high: float = Field(gt=0, lt=30)       # high end of market comparable multiple range
    risk_free_rate: float = Field(gt=0, lt=20)       # percent; reasonable NZ range
    erp: float = Field(gt=0, lt=20)
    industry_beta: float = Field(gt=0, lt=10)
    industry_category: str = Field(min_length=2)
    inflation_rate: float = Field(gt=-5, lt=30)
    sources: list[str] = Field(min_length=1)


# ---------------------------------------------------------------------------
# JSON extraction helper (AI-SPEC Section 4 lines 356-368)
# ---------------------------------------------------------------------------

def _extract_json_from_response(response) -> dict:
    """Extract the final text output from a Responses API result and parse JSON.

    Args:
        response: An OpenAI Responses API result (or duck-typed equivalent).

    Returns:
        Parsed JSON dict from the final text block.

    Raises:
        ValueError: If no text block is found or JSON parsing fails.
    """
    raw = str(getattr(response, "output_text", "") or "").strip()
    if not raw:
        raise ValueError("OpenAI research response did not include text output")
    # A model may still wrap JSON in a code fence despite instructions.
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    # If there's surrounding prose, try to extract the JSON object
    if not raw.startswith("{"):
        import re as _re
        m = _re.search(r'\{[\s\S]+\}', raw)
        if m:
            raw = m.group(0)
    return json.loads(raw)


def _is_local_or_private_host(hostname: str) -> bool:
    """Return True for hostnames/IPs that should never be sent as public source hints."""
    host = (hostname or "").strip().lower().strip("[]").rstrip(".")
    if not host:
        return True
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_loopback
        or address.is_link_local
        or address.is_private
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _normalise_prompt_source_hint_url(url: object, field_label: str) -> str:
    """Return a safe public http(s) URL for the live research prompt, or raise."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    if len(raw) > 2048:
        raise ValueError(f"{field_label} is too long")
    parsed = urlparse(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or any(char.isspace() for char in raw)
    ):
        raise ValueError(f"{field_label} must be a full public HTTP(S) URL")
    if _is_local_or_private_host(parsed.hostname):
        raise ValueError(f"{field_label} must be a public HTTP(S) URL")
    return raw.rstrip("/")


def _coerce_public_source_urls(public_source_urls: object) -> list[str]:
    """Coerce optional management-supplied public source hints into prompt-safe lines."""
    if public_source_urls in (None, ""):
        return []
    if isinstance(public_source_urls, str):
        candidates = re.split(r"[\n,]+", public_source_urls)
    elif isinstance(public_source_urls, (list, tuple, set)):
        candidates = [str(item) for item in public_source_urls]
    else:
        candidates = [str(public_source_urls)]
    urls: list[str] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates, start=1):
        if not candidate or not candidate.strip():
            continue
        url = _normalise_prompt_source_hint_url(candidate, f"public source URL {index}")
        key = url.lower()
        if key in seen:
            continue
        urls.append(url)
        seen.add(key)
    if len(urls) > 10:
        raise ValueError("public source URL hints can include up to 10 links")
    return urls


def _source_host(url: object) -> str:
    """Return a lowercase URL host, accepting friendly host/path strings."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower().rstrip(".")


def _source_path(url: object) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return parsed.path.lower()


def _invalid_source_urls(sources: object) -> list[str]:
    """Return research sources that cannot be rendered as real report links."""
    invalid: list[str] = []
    iterable = sources if isinstance(sources, list) else []
    for source in iterable:
        raw = str(source or "").strip()
        parsed = urlparse(raw)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or any(char.isspace() for char in raw)
        ):
            invalid.append(raw)
    return invalid


def _is_rbnz_source(url: object) -> bool:
    """Return True only for RBNZ URLs, not lookalike hosts."""
    host = _source_host(url)
    return host == "rbnz.govt.nz" or host.endswith(".rbnz.govt.nz")


def _is_damodaran_source(url: object) -> bool:
    """Return True only for recognised Damodaran data-source URLs."""
    host = _source_host(url)
    path = _source_path(url)
    if (host == "pages.stern.nyu.edu" or host.endswith(".stern.nyu.edu")) and "adamodar" in path:
        return True
    return host == "damodaran.com" or host.endswith(".damodaran.com")


# ---------------------------------------------------------------------------
# Guardrails (AI-SPEC Section 6 — Online guardrails)
# ---------------------------------------------------------------------------

def _apply_guardrails(brief: ResearchBrief) -> None:
    """Run all post-Pydantic guardrails. Raises ValueError on any failure.

    Guardrail order (matches AI-SPEC Section 6):
    1. Decimal-form WACC detection (D-W6 / Pitfall 1)
    2. Placeholder detection
    3. Invalid research source URLs
    4. Missing RBNZ or Damodaran source URL
    5. WACC range check (8–20% mid WACC for NZ private SME)
    """
    # 1. Decimal-form WACC detection (D-W6 / Pitfall 1)
    if brief.risk_free_rate < 1.0:
        raise ValueError(
            f"risk_free_rate appears to be in decimal form (got {brief.risk_free_rate}); "
            f"must be percent e.g. 4.65 not 0.0465"
        )
    if brief.erp < 1.0:
        raise ValueError(
            f"erp appears to be in decimal form (got {brief.erp}); must be percent"
        )
    # 1b. EV/EBITDA multiple range sanity check
    if brief.ev_ebitda_low >= brief.ev_ebitda_high:
        raise ValueError(
            f"ev_ebitda_low ({brief.ev_ebitda_low}) must be less than ev_ebitda_high ({brief.ev_ebitda_high})"
        )
    if brief.ev_ebitda_high > 20.0:
        raise ValueError(
            f"ev_ebitda_high ({brief.ev_ebitda_high}) exceeds 20x — implausible for NZ private SME; check comparable transactions"
        )
    # 2. Placeholder detection
    placeholder_pattern = re.compile(r"\b(N/?A|TBC|to be confirmed)\b", re.IGNORECASE)
    for field_name in ("company_summary", "sector_summary", "comparable_transactions", "industry_category"):
        value = getattr(brief, field_name, "")
        if placeholder_pattern.search(value):
            raise ValueError(
                f"Research brief field '{field_name}' contains placeholder text: '{value[:80]}'"
            )
    # 3. Invalid research source URLs. The finished report can only render and
    # validate evidence links that are real http(s) URLs.
    invalid_sources = _invalid_source_urls(brief.sources)
    if invalid_sources:
        raise ValueError(
            "Research brief sources must be valid http(s) URLs: "
            f"{invalid_sources}"
        )

    # 4. Missing RBNZ or Damodaran source URL. Parse hosts/paths so lookalike
    # URLs do not satisfy the professional evidence trail.
    has_rbnz = any(_is_rbnz_source(source) for source in brief.sources)
    has_damodaran = any(_is_damodaran_source(source) for source in brief.sources)
    missing_authoritative_sources = []
    if not has_rbnz:
        missing_authoritative_sources.append("RBNZ")
    if not has_damodaran:
        missing_authoritative_sources.append("Damodaran")
    if missing_authoritative_sources:
        raise ValueError(
            "Research brief sources must include both RBNZ and Damodaran URLs. "
            "Risk-free-rate, inflation, ERP and beta inputs cannot be verified "
            f"without: {', '.join(missing_authoritative_sources)}. "
            f"sources={brief.sources}"
        )
    # 4. WACC range check
    mid_wacc = brief.risk_free_rate + (brief.industry_beta * brief.erp)
    if not (8.0 <= mid_wacc <= 20.0):
        raise ValueError(
            f"Computed mid WACC {mid_wacc:.2f}% is outside plausible 8-20% range "
            f"(risk_free_rate={brief.risk_free_rate}, beta={brief.industry_beta}, erp={brief.erp})"
        )


# ---------------------------------------------------------------------------
# Synchronous research call (AI-SPEC Section 4 lines 371-445)
# ---------------------------------------------------------------------------

def run_research_loop_sync(
    company_name: str,
    company_location: str,
    industry_sector: str,
    company_website: str = "",
    public_source_urls: object = None,
    sector_context: str = "",
    max_retries: int = 2,
) -> ResearchBrief:
    """
    Synchronous OpenAI Responses API call with hosted web_search.

    Run via run_in_executor — never call directly from an async context.
    Raises RuntimeError on an empty API key or exhausted rate-limit retries.
    Raises ValueError when Pydantic validation or any guardrail fails.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot run research")

    company_website = _normalise_prompt_source_hint_url(company_website, "company website")
    source_urls = _coerce_public_source_urls(public_source_urls)
    source_hint_text = "\n".join(f"- {url}" for url in source_urls) or "Not supplied"
    generic_sector_context = str(sector_context or "").strip()
    sector_context_text = (
        generic_sector_context
        if generic_sector_context
        else "No AccountIQ generic sector pack matched this business."
    )

    client = _create_openai_client(api_key)

    user_prompt = (
        f"Research this business for a valuation report:\n"
        f"Company: {company_name}\n"
        f"Official website supplied by management: {company_website or 'Not supplied'}\n"
        f"Additional public source URLs supplied by management:\n{source_hint_text}\n"
        f"Location: {company_location}\n"
        f"Sector: {industry_sector}\n\n"
        f"AccountIQ generic New Zealand sector baseline:\n{sector_context_text}\n\n"
        f"Use the management-supplied website and source URLs first when available, then corroborate material facts "
        f"with independent public sources. Treat supplied URLs as source hints, not proof on their own. "
        f"Use the AccountIQ sector baseline as a research checklist and retain its primary-source URLs when relied on, "
        f"but do not treat typical sector characteristics as facts about the subject company. Corroborate time-sensitive "
        f"market statements and do not derive a current transaction multiple, beta or funding rate from the generic pack. "
        f"Do not use a public fact in the brief unless the supporting source URL is retained in sources. "
        f"If a supplied link cannot be corroborated, mention only that it was supplied as a matching hint. "
        f"Return the structured JSON brief when complete."
    )

    response = None
    attempts = max(1, int(max_retries))
    for attempt in range(attempts):
        try:
            response = client.responses.create(
                model=model,
                instructions=RESEARCH_SYSTEM_PROMPT,
                input=user_prompt,
                tools=[WEB_SEARCH_TOOL],
                max_output_tokens=MAX_TOKENS_RESEARCH,
            )
            break
        except Exception as exc:
            is_rate_limited = type(exc).__name__ == "RateLimitError" or getattr(exc, "status_code", None) == 429
            if not is_rate_limited or attempt >= attempts - 1:
                raise
            logger.warning("OpenAI rate limit hit — waiting 5s before retry")
            time.sleep(5)

    if response is None:
        raise RuntimeError("OpenAI research did not return a response")

    output_items = getattr(response, "output", []) or []
    search_count = sum(
        1
        for item in output_items
        if (item.get("type") if isinstance(item, dict) else getattr(item, "type", "")) == "web_search_call"
    )
    usage = getattr(response, "usage", None)
    logger.info(
        "OpenAI research complete searches=%d input_tokens=%s output_tokens=%s",
        search_count,
        getattr(usage, "input_tokens", "unknown"),
        getattr(usage, "output_tokens", "unknown"),
    )

    # Parse and validate structured brief
    raw_dict = _extract_json_from_response(response)
    try:
        brief = ResearchBrief(**raw_dict)
    except ValidationError as exc:
        raise ValueError(f"Research brief failed Pydantic validation: {exc}") from exc

    # Run post-Pydantic guardrails (AI-SPEC Section 6 Online guardrails)
    _apply_guardrails(brief)

    return brief


# ---------------------------------------------------------------------------
# Async entry point (AI-SPEC Section 4 lines 448-464)
# ---------------------------------------------------------------------------

async def run_valuation_research(
    company_name: str,
    company_location: str,
    industry_sector: str,
    company_website: str = "",
    public_source_urls: object = None,
    sector_context: str = "",
) -> ResearchBrief:
    """
    Async entry point for FastAPI background tasks.
    Wraps synchronous SDK call in thread pool executor.
    Uses get_running_loop() per project conventions (not the blocking run helper).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        run_research_loop_sync,
        company_name,
        company_location,
        industry_sector,
        company_website,
        public_source_urls,
        sector_context,
    )
