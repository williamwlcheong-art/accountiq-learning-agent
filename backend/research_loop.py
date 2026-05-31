"""
Agentic web-search research loop for business valuation.

Public API
----------
WEB_SEARCH_TOOL          - Anthropic web_search_20250305 tool config dict
RESEARCH_SYSTEM_PROMPT   - Static system prompt for the research loop
ResearchBrief            - Pydantic v2 model (9 fields) — validated output of the loop
run_research_loop_sync   - Synchronous entry point; call via run_in_executor from async code
run_valuation_research   - Async entry point for FastAPI background tasks

Design decisions:
- D-R1: web_search_20250305 server-side tool (no client-side dispatch)
- D-R2: max_uses=15 caps search cost at ~$0.15/run
- D-R3: user_location.country=NZ biases results toward RBNZ/Stats NZ
- D-R4: max_iterations=5 ceiling on pause_turn resume loop prevents runaway cost
- D-R5: ResearchBrief is an immutable Pydantic v2 model — consumers cannot mutate
         WACC inputs after validation

See: .planning/phases/05.1-valuation-advisory-redesign/05.1-AI-SPEC.md Section 4
See: .planning/phases/05.1-valuation-advisory-redesign/05.1-CONTEXT.md decisions D-R1..D-R5
"""

import os
import json
import asyncio
import logging
import re
import time
from typing import Optional

import anthropic
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (env-loaded, never hardcoded)
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_TOKENS_RESEARCH = 8000
MAX_LOOP_ITERATIONS = 5

# ---------------------------------------------------------------------------
# Web search tool definition (AI-SPEC Section 4 lines 303-312)
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 15,
    "user_location": {
        "type": "approximate",
        "country": "NZ",
        "timezone": "Pacific/Auckland",
    },
}

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
  "sources": ["url1", "url2", ...]    // list of source URLs cited
}

CRITICAL: Do not return the JSON until you have retrieved risk_free_rate, erp, and industry_beta
from actual web search results. These values must come from RBNZ or Damodaran — do not estimate them.
ev_ebitda_low must be less than ev_ebitda_high, and both must be positive."""


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
    """Extract the final text block from the response and parse as JSON.

    Args:
        response: An anthropic.types.Message (or duck-typed equivalent with .content list).

    Returns:
        Parsed JSON dict from the final text block.

    Raises:
        ValueError: If no text block is found or JSON parsing fails.
    """
    text_blocks = [b for b in response.content if b.type == "text"]
    if not text_blocks:
        raise ValueError("No text block in Claude response — cannot extract research brief")
    # Use last non-empty text block; the model sometimes emits an empty text block
    # before or after tool-result blocks, which would cause json.loads("") to fail.
    non_empty = [b for b in text_blocks if b.text.strip()]
    if not non_empty:
        raise ValueError(
            f"All text blocks in Claude response are empty (stop_reason={response.stop_reason}). "
            "The model may not have produced its JSON output yet — check max_iterations."
        )
    raw = non_empty[-1].text.strip()
    # Claude may wrap JSON in a code fence despite instructions
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


# ---------------------------------------------------------------------------
# Guardrails (AI-SPEC Section 6 — Online guardrails)
# ---------------------------------------------------------------------------

def _apply_guardrails(brief: ResearchBrief) -> None:
    """Run all post-Pydantic guardrails. Raises ValueError on any failure.

    Guardrail order (matches AI-SPEC Section 6):
    1. Decimal-form WACC detection (D-W6 / Pitfall 1)
    2. Placeholder detection
    3. Missing RBNZ/Damodaran source URL
    4. WACC range check (8–20% mid WACC for NZ private SME)
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
    # 3. Missing RBNZ/Damodaran source URL
    # Damodaran's NYU pages use the URL path "~adamodar/" (his username) so we
    # match both "damodaran" (his name/domain) and "adamodar" (NYU username).
    sources_concat = " ".join(brief.sources).lower()
    has_rbnz = "rbnz.govt.nz" in sources_concat
    has_damodaran = "damodaran" in sources_concat or "adamodar" in sources_concat
    if not has_rbnz and not has_damodaran:
        raise ValueError(
            "Research brief sources do not include an RBNZ or Damodaran URL. "
            "WACC inputs cannot be verified as sourced from authoritative data. "
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
# Synchronous research loop (AI-SPEC Section 4 lines 371-445)
# ---------------------------------------------------------------------------

def run_research_loop_sync(
    company_name: str,
    company_location: str,
    industry_sector: str,
    max_retries: int = 2,
) -> ResearchBrief:
    """
    Synchronous Anthropic SDK call with web_search tool.

    Run via run_in_executor — never call directly from an async context.
    Raises RuntimeError on max_tokens, unbounded pause_turn loops, or empty API key.
    Raises ValueError when Pydantic validation or any guardrail fails.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set — cannot run research loop")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_prompt = (
        f"Research this business for a valuation report:\n"
        f"Company: {company_name}\n"
        f"Location: {company_location}\n"
        f"Sector: {industry_sector}\n\n"
        f"Use web_search to retrieve current data. Return the structured JSON brief when complete."
    )

    messages = [{"role": "user", "content": user_prompt}]
    iteration = 0
    max_iterations = MAX_LOOP_ITERATIONS

    while iteration < max_iterations:
        # Retry once on rate limit (30K TPM tier) with a 65s back-off
        for _attempt in range(2):
            try:
                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=MAX_TOKENS_RESEARCH,
                    system=RESEARCH_SYSTEM_PROMPT,
                    tools=[WEB_SEARCH_TOOL],
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                if _attempt == 0:
                    logger.warning("Rate limit hit — waiting 65s before retry")
                    time.sleep(65)
                else:
                    raise
        iteration += 1

        # Log search activity for cost tracking (no API key in log output)
        search_count = getattr(response.usage, "server_tool_use", {})
        logger.info(
            "Research loop iter=%d stop_reason=%s searches=%s input_tokens=%d output_tokens=%d",
            iteration,
            response.stop_reason,
            search_count,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Research loop hit max_tokens at iteration {iteration}. "
                "Increase max_tokens or reduce MAX_SEARCHES."
            )

        if response.stop_reason == "pause_turn":
            # API paused long turn — append partial response and resume
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": "Please continue and return the JSON brief when ready."
            })
            continue

        raise RuntimeError(f"Unexpected stop_reason: {response.stop_reason!r}")
    else:
        raise RuntimeError(f"Research loop exceeded {max_iterations} iterations without end_turn")

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
    )
