"""No-provider public-source research for AccountIQ reports.

This module deliberately does not use a generative-AI service or a search API.
It only retrieves URLs that a user has supplied, follows a small number of
same-domain company pages, and returns an auditable evidence brief.  That keeps
the no-key reporting path useful without representing unverified web content as
independent due diligence.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field


MAX_SOURCE_URLS = 10
MAX_RETRIEVED_SOURCES = 8
MAX_COMPANY_PAGES = 3
MAX_RESPONSE_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 12
MAX_REDIRECTS = 3
_INTERESTING_COMPANY_PATH = re.compile(
    r"(?:about|company|our-story|who-we-are|services|what-we-do|solutions|fleet|locations|news)",
    re.IGNORECASE,
)


class EvidenceSource(BaseModel):
    """A single public source actually reviewed by the evidence collector."""

    url: str
    title: str
    source_type: str
    retrieved_at: str
    excerpt: str
    status: str = "retrieved"
    error: str = ""


class EvidenceResearchBrief(BaseModel):
    """Deterministic research context consumed by valuation and credit reports."""

    company_summary: str
    sector_summary: str
    comparable_transactions: str
    ev_ebitda_low: float = 3.5
    ev_ebitda_high: float = 5.0
    risk_free_rate: float = 4.0
    erp: float = 5.5
    industry_beta: float = 1.0
    industry_category: str
    inflation_rate: float = 2.5
    sources: list[str] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    research_mode: str = "evidence"


class _PageParser(HTMLParser):
    """Small dependency-free extractor for readable website text and links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.description = ""
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._ignore_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg", "template"}:
            self._ignore_depth += 1
        elif lowered == "title":
            self._in_title = True
        elif lowered == "meta":
            name = attributes.get("name", "").lower()
            property_name = attributes.get("property", "").lower()
            if name == "description" or property_name == "og:description":
                self.description = self.description or attributes.get("content", "")
        elif lowered == "a" and attributes.get("href"):
            self.links.append(attributes["href"])

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg", "template"} and self._ignore_depth:
            self._ignore_depth -= 1
        elif lowered == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned or self._ignore_depth:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned)


def _is_public_host(hostname: str) -> bool:
    """Return whether a hostname resolves only to public network addresses."""
    host = (hostname or "").strip().lower().strip("[]").rstrip(".")
    if not host or host == "localhost" or host.endswith((".localhost", ".local")):
        return False
    try:
        literal = ipaddress.ip_address(host)
        return literal.is_global
    except ValueError:
        pass
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    resolved: set[str] = {record[4][0] for record in addresses if record[4]}
    if not resolved:
        return False
    try:
        return all(ipaddress.ip_address(address).is_global for address in resolved)
    except ValueError:
        return False


def _validate_research_url(url: str) -> str:
    """Validate a public web URL before a server-side fetch."""
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if (
        not raw
        or len(raw) > 2048
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or any(char.isspace() for char in raw)
        or parsed.port not in {None, 80, 443}
    ):
        raise ValueError("Source must be a full public HTTP(S) URL using port 80 or 443")
    if not _is_public_host(parsed.hostname):
        raise ValueError("Source URL must resolve to a public internet host")
    return raw.rstrip("/")


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip("/")


def _same_host(left: str, right: str) -> bool:
    return (urlparse(left).hostname or "").lower().rstrip(".") == (
        urlparse(right).hostname or ""
    ).lower().rstrip(".")


def _extract_page(html: str) -> tuple[str, str, list[str]]:
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
    text = re.sub(r"\s+", " ", " ".join(parser.text_parts)).strip()
    description = re.sub(r"\s+", " ", parser.description).strip()
    excerpt = description or text
    return title[:180] or "Public web page", excerpt[:900], parser.links


def _fetch_source(url: str, source_type: str) -> tuple[EvidenceSource, list[str]]:
    """Fetch one source with SSRF protections and a small redirect budget."""
    current = _validate_research_url(url)
    with httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        follow_redirects=False,
        headers={"User-Agent": "AccountIQ-EvidenceResearch/1.0 (+https://accountiq.local)"},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_research_url(current)
            response = client.get(current)
            if response.is_redirect:
                location = response.headers.get("location", "")
                if not location:
                    raise ValueError("Source returned a redirect without a destination")
                current = _validate_research_url(urljoin(current, location))
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type and "text/plain" not in content_type:
                raise ValueError("Source is not an HTML or text page")
            raw = response.content[:MAX_RESPONSE_BYTES]
            encoding = response.encoding or "utf-8"
            html = raw.decode(encoding, errors="replace")
            title, excerpt, links = _extract_page(html)
            if len(excerpt) < 40:
                raise ValueError("Source did not contain enough readable public text")
            return (
                EvidenceSource(
                    url=_canonical_url(str(response.url)),
                    title=title,
                    source_type=source_type,
                    retrieved_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    excerpt=excerpt,
                ),
                links,
            )
    raise ValueError("Source redirected too many times")


def _source_failure(url: str, source_type: str, exc: Exception) -> EvidenceSource:
    return EvidenceSource(
        url=url,
        title="Source not retrieved",
        source_type=source_type,
        retrieved_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        excerpt="",
        status="not_retrieved",
        error=str(exc)[:220],
    )


def _normalise_urls(company_website: str, public_source_urls: Iterable[object] | object) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    if company_website:
        candidates.append((str(company_website), "company website"))
    if isinstance(public_source_urls, str):
        links = re.split(r"[\n,]+", public_source_urls)
    elif isinstance(public_source_urls, Iterable):
        links = [str(item) for item in public_source_urls]
    elif public_source_urls:
        links = [str(public_source_urls)]
    else:
        links = []
    candidates.extend((url, "management-supplied public source") for url in links if url and url.strip())

    normalised: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_url, source_type in candidates:
        url = _canonical_url(_validate_research_url(raw_url))
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        normalised.append((url, source_type))
    if len(normalised) > MAX_SOURCE_URLS:
        raise ValueError(f"Up to {MAX_SOURCE_URLS} public source URLs can be reviewed")
    return normalised


def _company_child_urls(homepage: str, links: Iterable[str]) -> list[str]:
    children: list[str] = []
    seen: set[str] = {_canonical_url(homepage).lower()}
    for href in links:
        candidate = urljoin(homepage, href)
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not _same_host(homepage, candidate):
            continue
        candidate = _canonical_url(candidate)
        if candidate.lower() in seen or not _INTERESTING_COMPANY_PATH.search(parsed.path):
            continue
        seen.add(candidate.lower())
        children.append(candidate)
        if len(children) >= MAX_COMPANY_PAGES - 1:
            break
    return children


def collect_evidence_research_sync(
    *,
    company_name: str,
    company_location: str,
    industry_sector: str,
    company_website: str = "",
    public_source_urls: Iterable[object] | object = (),
) -> EvidenceResearchBrief:
    """Collect approved public-source evidence without a search or AI provider."""
    requested = _normalise_urls(company_website, public_source_urls)
    records: list[EvidenceSource] = []
    child_queue: list[str] = []
    for url, source_type in requested:
        if len(records) >= MAX_RETRIEVED_SOURCES:
            break
        try:
            record, links = _fetch_source(url, source_type)
            records.append(record)
            if source_type == "company website":
                child_queue.extend(_company_child_urls(record.url, links))
        except Exception as exc:
            records.append(_source_failure(url, source_type, exc))

    seen = {record.url.lower() for record in records}
    for child_url in child_queue:
        if len(records) >= MAX_RETRIEVED_SOURCES or child_url.lower() in seen:
            continue
        seen.add(child_url.lower())
        try:
            record, _links = _fetch_source(child_url, "company website page")
            records.append(record)
        except Exception as exc:
            records.append(_source_failure(child_url, "company website page", exc))

    retrieved = [record for record in records if record.status == "retrieved"]
    source_urls = [record.url for record in records]
    if retrieved:
        first = retrieved[0]
        description = first.excerpt[:520].rstrip(" .")
        company_summary = (
            f"AccountIQ reviewed {len(retrieved)} approved public source(s) for {company_name}. "
            f"The source titled '{first.title}' describes the business as follows: {description}. "
            "This is published public information retained in the source trail; it has not been independently verified."
        )
    else:
        company_summary = (
            f"No approved public source could be retrieved for {company_name}. "
            "The business description in this report is therefore limited to uploaded financial statements and management-supplied intake information."
        )

    sector = industry_sector or "the stated operating sector"
    location = company_location or "New Zealand"
    sector_summary = (
        f"The report treats {company_name} as operating in {sector} in {location}. "
        "Evidence mode does not perform open-web discovery, paid database searches or automated comparable-transaction searches. "
        "Any sector growth rate, peer comparison, transaction multiple or regulatory conclusion requires a separately cited source."
    )
    limitations = [
        "Only the company website and public URLs supplied in the intake were reviewed; no open-web search was performed.",
        "Website content is public-source context, not independent verification of management claims.",
        "Discount-rate and multiple inputs use documented model conventions when independent market evidence is unavailable.",
    ]
    if not retrieved:
        limitations.insert(0, "None of the supplied public URLs could be retrieved, so no website facts are used in the report.")

    return EvidenceResearchBrief(
        company_summary=company_summary,
        sector_summary=sector_summary,
        comparable_transactions=(
            "No independent comparable-transaction evidence was retrieved in evidence mode. "
            "The EV/EBITDA cross-check is a documented model convention and is not a market-data conclusion."
        ),
        industry_category=sector,
        sources=source_urls,
        evidence_sources=records,
        limitations=limitations,
    )


async def collect_evidence_research(**kwargs) -> EvidenceResearchBrief:
    """Async entry point for FastAPI background report generation."""
    return await asyncio.to_thread(collect_evidence_research_sync, **kwargs)


def evidence_sources_table(records: Iterable[dict] | Iterable[EvidenceSource]) -> dict:
    """Render the retained source ledger in a report-ready table."""
    rows: list[list[str]] = []
    for raw in records:
        record = raw if isinstance(raw, EvidenceSource) else EvidenceSource.model_validate(raw)
        if record.status == "retrieved":
            support = (
                f"Retrieved {record.retrieved_at}. Reviewed public excerpt: "
                f"{record.excerpt[:280]}"
            )
        elif record.status == "curated":
            support = (
                f"Reviewed for the AccountIQ sector library at {record.retrieved_at}. "
                f"{record.excerpt[:280]}"
            )
        else:
            support = (
                f"Source was supplied but not retrieved "
                f"({record.error or 'no readable public text'}); it was not used for a factual claim."
            )
        rows.append([record.title, record.url, support])
    return {
        "headers": ["Source", "URL", "Supports / used for"],
        "rows": rows,
    }
