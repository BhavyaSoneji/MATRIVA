"""Live web search as a supplementary evidence source (Tavily, https://tavily.com).

Gap this closes: Section 43's grounding gate (`app.rag.grounding`) correctly
refuses to let the LLM answer from general knowledge when the local
knowledge base has no relevant evidence -- but until now the only outcome of
that gate was the fixed INSUFFICIENT_EVIDENCE_RESPONSE, even for perfectly
reasonable questions the reviewed local corpus simply doesn't cover yet.

This module adds ONE more thing the pipeline may try, and ONLY after the
Section 43 gate has already fired on the local corpus: search the live web
via Tavily (an LLM/RAG-oriented search API) for a small number of results,
and hand those to the same source-grounded generation + citation validation
+ safety post-check path as local evidence -- never bypassing any of it.

Two safety properties this module exists to preserve, both enforced by
CALLERS (see app.rag.pipeline.answer_query), not here:
  1. The safety pre-check (`classify`/`classify_query`) always runs, and
     urgent/high-risk queries always short-circuit, BEFORE this module is
     ever invoked -- web search never gets a chance to run for those.
  2. Web results are never treated as reviewed knowledge: callers must wrap
     them as `app.rag.context_packet.WebSourceEntry` (source_type
     "external_web", evidence_level UNCERTAIN) so the LLM prompt and the
     final citations structurally separate them from the local knowledge
     base -- see context_packet.to_prompt_text().

This module itself has exactly one job: turn a query into a short list of
(title, url, domain, content) results, or an empty list if anything at all
goes wrong. It never raises -- a Tavily outage, timeout, bad response shape,
or missing dependency must degrade to "no web results" (which callers then
treat exactly like local insufficient evidence), never crash the chat
request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

logger = logging.getLogger("matriva.web_search")

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 3
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class WebSearchResult:
    """One Tavily search hit, reduced to what the pipeline actually needs.

    `content` is Tavily's own extracted-snippet text, not the raw page --
    still untrusted external data (see app.safety.prompt_injection), just
    like every other piece of retrieved content in this codebase.
    """

    title: str
    url: str
    domain: str
    content: str


def _domain_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        return url
    return netloc.removeprefix("www.") or url


def search_web(
    query: str,
    api_key: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[WebSearchResult]:
    """Query Tavily's REST search endpoint and return up to `max_results` hits.

    Never raises: any network error, timeout, non-2xx status, or unexpected
    response shape is logged and treated as "no results" so the caller falls
    back to the existing insufficient-evidence behavior rather than a 500.

    `query` is sent to Tavily as a plain search term, exactly as the user
    typed it -- that is a normal, expected use of a search API and is not
    the same thing as feeding untrusted text into an LLM prompt as
    instructions. The results that come BACK from Tavily are the untrusted
    part; callers must route them through `WebSourceEntry`
    (app.rag.context_packet) so they only ever appear as labelled, isolated
    "external/unverified" data in the LLM prompt, never merged into system
    instructions -- same structural defense already used for local
    knowledge-base content (app.safety.prompt_injection).
    """
    if not api_key or not query.strip():
        return []

    try:
        response = requests.post(
            TAVILY_SEARCH_URL,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max(1, min(max_results, 10)),
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        logger.warning("Tavily web search request failed", exc_info=True)
        return []
    except ValueError:  # response body was not valid JSON
        logger.warning("Tavily web search returned a non-JSON response", exc_info=True)
        return []

    raw_results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(raw_results, list):
        return []

    results: list[WebSearchResult] = []
    for item in raw_results[:max_results]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        if not url or not content:
            continue
        results.append(
            WebSearchResult(
                title=str(item.get("title") or url).strip(),
                url=url,
                domain=_domain_from_url(url),
                content=content,
            )
        )
    return results
