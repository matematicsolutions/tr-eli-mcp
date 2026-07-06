"""Offline parser tests against committed Bedesten API fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from tr_eli_mcp.citations import (
    build_human_readable_citation,
    build_source_url,
    parse_article_tree,
    parse_document,
    parse_mevzuat_types,
    parse_search,
    strip_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_search_returns_documents():
    total, records = parse_search(_load("search_ceza.json"))
    assert total == 2
    assert len(records) == 2

    tck = next(r for r in records if r["mevzuat_no"] == "5237")
    assert tck["mevzuat_id"] == "103228"
    assert tck["mevzuat_adi"] == "TÜRK CEZA KANUNU"
    assert tck["mevzuat_turu"] == "Kanunlar"
    # eli_uri = canonical mevzuat.gov.tr URL (Turkey has no native /eli/).
    assert tck["eli_uri"] == "https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5237&MevzuatTur=1&MevzuatTertip=5"
    assert "/eli/" not in tck["eli_uri"]
    assert tck["source_url"] == tck["eli_uri"]
    assert "5237" in tck["human_readable_citation"]
    assert "TÜRK CEZA KANUNU" in tck["human_readable_citation"]


def test_human_readable_citation_includes_gazette_when_present():
    _, records = parse_search(_load("search_ceza.json"))
    military = next(r for r in records if r["mevzuat_no"] == "1632")
    assert "Resmi Gazete: 15/06/1930" in military["human_readable_citation"]
    assert "Sayi: 1520" in military["human_readable_citation"]


def test_human_readable_citation_without_gazette_date():
    tck_stub = {
        "mevzuatNo": 5237,
        "mevzuatAdi": "TÜRK CEZA KANUNU",
        "resmiGazeteTarihi": None,
        "resmiGazeteSayisi": "25611",
    }
    citation = build_human_readable_citation(tck_stub)
    assert citation == "5237 sayili TÜRK CEZA KANUNU (Sayi: 25611)"


def test_build_source_url_fallback_without_url_field():
    stub = {"mevzuatId": "999999"}
    url = build_source_url(stub)
    assert url == "https://bedesten.adalet.gov.tr/mevzuat/getDocumentContent?id=999999"


def test_parse_document_missing_title_has_no_citation():
    rec = parse_document({"mevzuatId": "1"})
    assert "human_readable_citation" not in rec


def test_parse_article_tree():
    nodes = parse_article_tree(_load("tree_104289.json"))
    assert nodes
    first = nodes[0]
    assert first["madde_id"]
    assert first["madde_no"] == 1
    assert isinstance(first["children"], list)


def test_parse_garbage_is_empty():
    assert parse_search({"unexpected": True}) == (0, [])
    assert parse_search("not a dict") == (0, [])
    assert parse_article_tree({"data": {}}) == []
    assert parse_mevzuat_types({"data": "nope"}) == []


def test_strip_html_basic():
    html = "<p>Madde 1<br/>Bu kanunun amaci &amp; kapsami.</p>"
    text = strip_html(html)
    assert "Madde 1" in text
    assert "&" in text
    assert "<p>" not in text
