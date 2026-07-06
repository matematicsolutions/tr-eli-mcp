"""Live smoke tests against the Adalet Bakanligi Bedesten API.

These hit the network (bedesten.adalet.gov.tr). They are skipped automatically if the host is
unreachable. Run explicitly with:

    pytest tests/test_smoke.py
"""

from __future__ import annotations

import httpx
import pytest

from tr_eli_mcp.server import (
    tr_get_legislation_content,
    tr_get_legislation_toc,
    tr_list_legislation_types,
    tr_search_legislation,
)

# Turkish Penal Code (Turk Ceza Kanunu) - well-known, stable law number.
TCK_QUERY = "ceza kanunu"


def _live_or_skip() -> None:
    try:
        r = httpx.post(
            "https://bedesten.adalet.gov.tr/mevzuat/mevzuatTypes",
            json={"data": {}, "applicationName": "UyapMevzuat"},
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "AdaletApplicationName": "UyapMevzuat",
                "Origin": "https://mevzuat.adalet.gov.tr",
                "Referer": "https://mevzuat.adalet.gov.tr/",
            },
            timeout=20.0,
        )
        r.raise_for_status()
    except Exception as exc:  # pragma: no cover - network gate
        pytest.skip(f"Bedesten API not reachable: {exc}")


@pytest.mark.asyncio
async def test_smoke_list_types():
    _live_or_skip()
    result = await tr_list_legislation_types()
    assert result.items
    kanun = [i for i in result.items if i.mevzuat_tur == "KANUN"]
    assert kanun, "expected a KANUN (laws) type entry"
    assert kanun[0].count and kanun[0].count > 0


@pytest.mark.asyncio
async def test_smoke_search():
    _live_or_skip()
    result = await tr_search_legislation(TCK_QUERY, mevzuat_turu="KANUN")
    assert result.returned >= 1
    for item in result.items:
        assert item.eli_uri and item.human_readable_citation and item.source_url
        assert "mevzuat.gov.tr" in item.eli_uri or "bedesten.adalet.gov.tr" in item.eli_uri
        assert "/eli/" not in item.eli_uri


@pytest.mark.asyncio
async def test_smoke_get_content_and_toc():
    _live_or_skip()
    search_result = await tr_search_legislation(TCK_QUERY, mevzuat_turu="KANUN")
    assert search_result.items, "need at least one search hit to fetch content"
    mevzuat_id = search_result.items[0].mevzuat_id
    assert mevzuat_id

    content = await tr_get_legislation_content(mevzuat_id)
    assert content.content and content.byte_size and content.byte_size > 500
    assert content.mevzuat_id == mevzuat_id

    toc = await tr_get_legislation_toc(mevzuat_id)
    assert toc.nodes
    assert toc.mevzuat_id == mevzuat_id
