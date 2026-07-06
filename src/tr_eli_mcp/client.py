"""Async httpx client for the Turkish Adalet Bakanligi (Ministry of Justice) Bedesten API,
with cache.

Bedesten serves Turkish legislation as a keyless JSON REST API at
``bedesten.adalet.gov.tr/mevzuat`` (the backend of the ``mevzuat.adalet.gov.tr`` search
portal, which is itself a mirror/frontend of the canonical ``mevzuat.gov.tr`` legislation
database). Live-verified endpoints used here:

- ``POST /mevzuat/searchDocuments`` - search legislation (title / full text / number / date).
- ``POST /mevzuat/getDocumentContent`` - full text of a document or a single article
  (base64-encoded HTML, decoded here).
- ``POST /mevzuat/mevzuatMaddeTree`` - article tree / table of contents.
- ``POST /mevzuat/mevzuatTypes`` - enumeration of legislation types with live counts.

Every request is wrapped ``{"data": {...}, "applicationName": "UyapMevzuat"}``
(``searchDocuments`` additionally sets ``"paging": true``). Every response is wrapped
``{"data": ..., "metadata": {"FMTY": "SUCCESS"|"ERROR", "FMTE": "..."}}``.

We keep our own backoff + cache; no API key or session cookie is required.
"""

from __future__ import annotations

import anyio
import httpx

from .cache import HttpCache

DEFAULT_BASE_URL = "https://bedesten.adalet.gov.tr/mevzuat"
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
USER_AGENT = "tr-eli-mcp/0.1.0 (+https://github.com/matematicsolutions/tr-eli-mcp)"
APPLICATION_NAME = "UyapMevzuat"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3


class TrError(Exception):
    """Raised when the Bedesten response cannot be retrieved or is invalid."""


def _wrap(data: dict[str, object]) -> dict[str, object]:
    return {"data": data, "applicationName": APPLICATION_NAME}


def _wrap_paging(data: dict[str, object]) -> dict[str, object]:
    return {"data": data, "applicationName": APPLICATION_NAME, "paging": True}


class BedestenClient:
    """Async client for the Adalet Bakanligi Bedesten legislation API.

    Use as ``async with BedestenClient() as c: ...``.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        cache: HttpCache | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._cache = cache or HttpCache()
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json; charset=utf-8",
                "AdaletApplicationName": APPLICATION_NAME,
                "Origin": "https://mevzuat.adalet.gov.tr",
                "Referer": "https://mevzuat.adalet.gov.tr/",
            },
            follow_redirects=True,
        )

    async def __aenter__(self) -> BedestenClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    async def _post(
        self, path: str, payload: dict[str, object], *, category: str, cache_key: str
    ) -> dict[str, object]:
        cached = self._cache.get(cache_key)
        if cached is not None and isinstance(cached, dict):
            return cached
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                resp = await self._http.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                if not isinstance(body, dict):
                    raise TrError(f"Unexpected non-object response from {path}")
                meta = body.get("metadata") or {}
                if isinstance(meta, dict) and meta.get("FMTY") not in (None, "SUCCESS"):
                    raise TrError(
                        f"Bedesten API error at {path}: {meta.get('FMTE', 'unknown error')}"
                    )
                self._cache.set(cache_key, body, ttl=HttpCache.ttl_for(category))
                return body
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
            await anyio.sleep(0.5 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def search_documents(
        self,
        *,
        phrase: str = "",
        mevzuat_adi: str = "",
        mevzuat_no: str | None = None,
        mevzuat_tur_list: list[str] | None = None,
        baslikta_ara: bool = True,
        tam_cumle: bool = False,
        page: int = 1,
        page_size: int = 20,
        sort_field: str = "RESMI_GAZETE_TARIHI",
        sort_direction: str = "desc",
    ) -> dict[str, object]:
        """Search Turkish legislation by title and/or full text."""
        inner: dict[str, object] = {
            "pageSize": page_size,
            "pageNumber": page,
            "sortFields": [sort_field],
            "sortDirection": sort_direction,
        }
        if phrase:
            inner["phrase"] = phrase
        if mevzuat_adi:
            inner["mevzuatAdi"] = mevzuat_adi
        if mevzuat_no:
            inner["mevzuatNo"] = mevzuat_no
        if mevzuat_tur_list:
            inner["mevzuatTurList"] = mevzuat_tur_list
        if not baslikta_ara:
            inner["basliktaAra"] = False
        if tam_cumle:
            inner["tamCumle"] = True
        cache_key = "search:" + repr(sorted(inner.items()))
        return await self._post(
            "/searchDocuments", _wrap_paging(inner), category="search", cache_key=cache_key
        )

    async def get_document_content(self, mevzuat_id: str) -> dict[str, object]:
        """Fetch full document content (base64 HTML, decoded by caller)."""
        inner: dict[str, object] = {"documentType": "MEVZUAT", "id": mevzuat_id}
        return await self._post(
            "/getDocumentContent",
            _wrap(inner),
            category="act",
            cache_key=f"doc:{mevzuat_id}",
        )

    async def get_article_content(self, madde_id: str) -> dict[str, object]:
        """Fetch a single article's content by maddeId (base64 HTML, decoded by caller)."""
        inner: dict[str, object] = {"documentType": "MADDE", "id": madde_id}
        return await self._post(
            "/getDocumentContent",
            _wrap(inner),
            category="act",
            cache_key=f"madde:{madde_id}",
        )

    async def get_article_tree(self, mevzuat_id: str) -> dict[str, object]:
        """Fetch the article tree (madde agaci / table of contents) for a document."""
        inner: dict[str, object] = {"mevzuatId": mevzuat_id}
        return await self._post(
            "/mevzuatMaddeTree",
            _wrap(inner),
            category="dict",
            cache_key=f"tree:{mevzuat_id}",
        )

    async def get_mevzuat_types(self) -> dict[str, object]:
        """Fetch the enumeration of legislation types with live document counts."""
        return await self._post(
            "/mevzuatTypes", _wrap({}), category="dict", cache_key="types:all"
        )
