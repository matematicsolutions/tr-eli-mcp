"""FastMCP entry point - Turkish legislation via the Adalet Bakanligi Bedesten API.

Run:

    python -m tr_eli_mcp.server

Configuration via env:

- ``TR_ELI_CACHE_DIR`` (default ``~/.matematic/cache/tr-eli``)
- ``TR_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``TR_ELI_BASE_URL`` (default ``https://bedesten.adalet.gov.tr/mevzuat``)
"""

from __future__ import annotations

import os

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .audit import AuditLogger, hash_input, timer
from .citations import (
    decode_document_content,
    parse_article_tree,
    parse_mevzuat_types,
    parse_search,
    strip_html,
)
from .client import DEFAULT_BASE_URL, BedestenClient, TrError
from .models import (
    ArticleNode,
    ArticleTree,
    Legislation,
    LegislationContent,
    LegislationType,
    LegislationTypeList,
    SearchResult,
)

INSTRUCTIONS = """\
This MCP server exposes Turkish legislation through the Adalet Bakanligi (Ministry of Justice) Bedesten API (bedesten.adalet.gov.tr/mevzuat, keyless). Bedesten is the JSON backend behind the mevzuat.adalet.gov.tr search portal, itself a mirror of the canonical mevzuat.gov.tr legislation database. Every response carries a stable `eli_uri`, a `human_readable_citation` and a `source_url` (the citation contract).

## Call order

1. `tr_search_legislation` - search Turkish legislation by title and/or full text, optionally filtered by type (e.g. `KANUN`, `KHK`, `YONETMELIK`) and legislation number. Returns items, each with `mevzuat_id`, `mevzuat_no`, `eli_uri`, `human_readable_citation`, `source_url`.
2. `tr_get_legislation_content` - the full text of one document by its `mevzuat_id` (from search results), converted from HTML to plain text.
3. `tr_get_legislation_toc` - the article tree (madde agaci / table of contents) for one document by its `mevzuat_id`.
4. `tr_list_legislation_types` - enumerate all legislation types with live document counts (e.g. KANUN, KHK, TUZUK, YONETMELIK, CB_KARARNAME, CB_KARAR, CB_YONETMELIK, CB_GENELGE, TEBLIGLER).

## Hard constraints

- **eli_uri is the citability key, but Turkey does NOT publish native ELI (/eli/) URIs.** `eli_uri` therefore carries the canonical, resolvable `https://www.mevzuat.gov.tr/mevzuat?...` URL for the document (or a Bedesten API fallback if that URL is absent from the record). Never fabricate a `/eli/` URI.
- **Cite using the Turkish convention** - law number + name + Official Gazette (Resmi Gazete) date/number, e.g. "5237 sayili Turk Ceza Kanunu (Resmi Gazete: 12/10/2004, Sayi: 25611)". `human_readable_citation` already carries this.
- **Every response has `human_readable_citation` + `source_url`** - cite both to the user.
- **No case law.** This server covers legislation only. Yargitay (Court of Cassation) case search was unreachable at build time and Anayasa Mahkemesi (Constitutional Court) exposes only a client-rendered SPA with no discovered server API - neither is covered here.
- **No modification of official text** - returned verbatim from Bedesten (HTML converted to plain text, nothing summarized or altered).
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/tr-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing or malformed (e.g. an empty query, a non-numeric mevzuat_id).
- `not_found` - no document exists for that id / no hits for the query.
- `upstream_error` - a Bedesten API error (HTTP, timeout, malformed JSON, FMTY=ERROR). Retry once before surfacing.

## Response style

- Cite legislation as `human_readable_citation` with the identifier: "5237 sayili Turk Ceza Kanunu, https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5237&MevzuatTur=1&MevzuatTertip=5".
- NEVER invent a mevzuat number, a title or an identifier - take each from the tool output.
"""

_MAX_SEARCH_RECORDS = 20


class ToolError(Exception):
    """Structured error for tr-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="tr-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("TR_ELI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "No document found in the Bedesten repository.")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"Bedesten API error: {type(exc).__name__}: {exc}")
    if isinstance(exc, TrError):
        return ToolError("upstream_error", str(exc))
    return exc


# ---------------------------------------------------------------------------
# tr_search_legislation
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def tr_search_legislation(
    query: str,
    mevzuat_turu: str | None = None,
    mevzuat_no: str | None = None,
    baslikta_ara: bool = True,
) -> SearchResult:
    """Search Turkish legislation by title and/or full text.

    Args:
        query: Search phrase, e.g. ``"vergi"``.
        mevzuat_turu: Optional legislation type filter, e.g. ``"KANUN"``, ``"KHK"``,
            ``"YONETMELIK"``. See ``tr_list_legislation_types`` for the full list.
        mevzuat_no: Optional legislation number filter.
        baslikta_ara: Search in title only (default True). Set False to search full text too.

    Returns:
        ``SearchResult`` with ``items: list[Legislation]``, each carrying the citation contract.
    """
    audit = _audit()
    if not query or not query.strip():
        raise ToolError("invalid_arg", "query must be a non-empty string.")
    input_hash = hash_input(
        {"query": query, "mevzuat_turu": mevzuat_turu, "mevzuat_no": mevzuat_no}
    )

    with timer() as t:
        try:
            async with BedestenClient(base_url=_base_url()) as client:
                body = await client.search_documents(
                    mevzuat_adi=query,
                    mevzuat_tur_list=[mevzuat_turu] if mevzuat_turu else None,
                    mevzuat_no=mevzuat_no,
                    baslikta_ara=baslikta_ara,
                    page_size=_MAX_SEARCH_RECORDS,
                )
        except Exception as exc:
            audit.log(
                tool="tr_search_legislation",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    total, records = parse_search(body)
    items = [Legislation.model_validate(r) for r in records]
    result = SearchResult(
        query={"query": query, "mevzuat_turu": mevzuat_turu, "mevzuat_no": mevzuat_no},
        total_matched=total,
        returned=len(items),
        items=items,
    )
    audit.log(
        tool="tr_search_legislation",
        input_hash=input_hash,
        output_count_or_size=len(items),
        duration_ms=t.duration_ms,
        status="ok",
    )
    return result


# ---------------------------------------------------------------------------
# tr_get_legislation_content
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def tr_get_legislation_content(mevzuat_id: str) -> LegislationContent:
    """Fetch the full text of a Turkish legislative document by its mevzuat_id.

    Args:
        mevzuat_id: Document id, from a ``tr_search_legislation`` result.

    Returns:
        ``LegislationContent`` with the citation contract and ``content`` (plain text).
    """
    audit = _audit()
    cleaned = mevzuat_id.strip()
    if not cleaned:
        raise ToolError("invalid_arg", "mevzuat_id must be a non-empty string.")
    input_hash = hash_input({"mevzuat_id": cleaned})

    with timer() as t:
        try:
            async with BedestenClient(base_url=_base_url()) as client:
                body = await client.get_document_content(cleaned)
        except Exception as exc:
            audit.log(
                tool="tr_get_legislation_content",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    decoded = decode_document_content(body)
    if decoded is None:
        audit.log(
            tool="tr_get_legislation_content",
            input_hash=input_hash,
            output_count_or_size=0,
            duration_ms=t.duration_ms,
            status="error",
            error="not_found",
        )
        raise ToolError("not_found", f"No content available for mevzuat_id={cleaned!r}.")

    raw_content, mime_type = decoded
    plain_text = strip_html(raw_content) if "html" in mime_type.lower() else raw_content

    result = LegislationContent(
        mevzuat_id=cleaned,
        format="html-to-text" if "html" in mime_type.lower() else mime_type,
        content=plain_text,
        byte_size=len(plain_text.encode("utf-8")),
    )
    audit.log(
        tool="tr_get_legislation_content",
        input_hash=input_hash,
        output_count_or_size=result.byte_size or 0,
        duration_ms=t.duration_ms,
        status="ok",
    )
    return result


# ---------------------------------------------------------------------------
# tr_get_legislation_toc
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def tr_get_legislation_toc(mevzuat_id: str) -> ArticleTree:
    """Fetch the article tree (madde agaci / table of contents) of a document.

    Args:
        mevzuat_id: Document id, from a ``tr_search_legislation`` result.

    Returns:
        ``ArticleTree`` with a nested list of article nodes (madde_no, madde_baslik, children).
    """
    audit = _audit()
    cleaned = mevzuat_id.strip()
    if not cleaned:
        raise ToolError("invalid_arg", "mevzuat_id must be a non-empty string.")
    input_hash = hash_input({"mevzuat_id": cleaned})

    with timer() as t:
        try:
            async with BedestenClient(base_url=_base_url()) as client:
                body = await client.get_article_tree(cleaned)
        except Exception as exc:
            audit.log(
                tool="tr_get_legislation_toc",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    nodes = parse_article_tree(body)
    if not nodes:
        audit.log(
            tool="tr_get_legislation_toc",
            input_hash=input_hash,
            output_count_or_size=0,
            duration_ms=t.duration_ms,
            status="error",
            error="not_found",
        )
        raise ToolError("not_found", f"No article tree available for mevzuat_id={cleaned!r}.")

    result = ArticleTree(
        mevzuat_id=cleaned, nodes=[ArticleNode.model_validate(n) for n in nodes]
    )
    audit.log(
        tool="tr_get_legislation_toc",
        input_hash=input_hash,
        output_count_or_size=len(nodes),
        duration_ms=t.duration_ms,
        status="ok",
    )
    return result


# ---------------------------------------------------------------------------
# tr_list_legislation_types
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def tr_list_legislation_types() -> LegislationTypeList:
    """Enumerate all Turkish legislation types with live document counts.

    Returns:
        ``LegislationTypeList`` with items like KANUN (laws), KHK (decree-laws),
        YONETMELIK (regulations), CB_KARARNAME (presidential decrees), etc.
    """
    audit = _audit()
    input_hash = hash_input({})

    with timer() as t:
        try:
            async with BedestenClient(base_url=_base_url()) as client:
                body = await client.get_mevzuat_types()
        except Exception as exc:
            audit.log(
                tool="tr_list_legislation_types",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    records = parse_mevzuat_types(body)
    items = [LegislationType.model_validate(r) for r in records]
    result = LegislationTypeList(items=items)
    audit.log(
        tool="tr_list_legislation_types",
        input_hash=input_hash,
        output_count_or_size=len(items),
        duration_ms=t.duration_ms,
        status="ok",
    )
    return result


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
