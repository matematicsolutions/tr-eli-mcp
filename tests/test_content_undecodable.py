"""Niedekodowalna tresc z Bedesten to awaria zrodla, nie brak dokumentu (2026-09-24)."""
from __future__ import annotations

import pytest

import tr_eli_mcp.server as srv


def _klient(tresc):
    class Atrapa:
        def __init__(self, base_url=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get_document_content(self, mevzuat_id):
            return {"data": {"content": tresc, "mimeType": "text/html"}}
    return Atrapa


@pytest.mark.asyncio
async def test_zepsuty_base64_to_upstream_error(monkeypatch):
    monkeypatch.setattr(srv, "BedestenClient", _klient("abc"))
    with pytest.raises(srv.ToolError) as e:
        await srv.tr_get_legislation_content("12345")
    assert e.value.code == "upstream_error"


@pytest.mark.asyncio
async def test_brak_tresci_to_nadal_not_found(monkeypatch):
    monkeypatch.setattr(srv, "BedestenClient", _klient(""))
    with pytest.raises(srv.ToolError) as e:
        await srv.tr_get_legislation_content("12345")
    assert e.value.code == "not_found"
