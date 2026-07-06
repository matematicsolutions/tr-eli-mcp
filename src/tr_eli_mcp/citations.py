"""Turkish legislation record parsing + citation helpers.

The Adalet Bakanligi Bedesten API (``bedesten.adalet.gov.tr/mevzuat``) returns JSON. A search
(``searchDocuments``) wraps a list of document stubs under ``data.mevzuatList``; each stub
carries the same key fields needed for the citation contract.

Citation contract (Art. 4 CONSTITUTION):
- ``eli_uri``: **Turkey does not publish native ELI (/eli/) URIs.** This field carries the
  equivalent stable, resolvable identifier instead - the canonical browsable URL on
  ``www.mevzuat.gov.tr`` that every Bedesten search result already supplies
  (``https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=<no>&MevzuatTur=<tur>&MevzuatTertip=<tertip>``).
  It is parsed from the source record, never fabricated. If a record has no such URL (rare),
  the Bedesten document id is used to build a resolvable fallback instead of inventing a URI.
- ``human_readable_citation``: built from the Turkish citation convention - law number + name +
  Official Gazette (Resmi Gazete) date/number, e.g.
  "5237 sayili Turk Ceza Kanunu (Resmi Gazete: 12/10/2004, Sayi: 25611)".
- ``source_url``: the same canonical mevzuat.gov.tr URL (falls back to the Bedesten API URL for
  the raw record if no mevzuat.gov.tr URL is present).
"""

from __future__ import annotations

from typing import Any

MEVZUAT_GOV_TR_BASE = "https://www.mevzuat.gov.tr"
BEDESTEN_BASE = "https://bedesten.adalet.gov.tr/mevzuat"


def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _date_only(value: Any) -> str | None:
    if not value:
        return None
    return str(value).split("T")[0].strip() or None


def _format_gazette_date(value: Any) -> str | None:
    """Convert an ISO date like 2004-10-12 to Turkish DD/MM/YYYY citation form."""
    date_only = _date_only(value)
    if not date_only:
        return None
    parts = date_only.split("-")
    if len(parts) != 3:
        return date_only
    year, month, day = parts
    return f"{day}/{month}/{year}"


def _tur_name(dok: dict[str, Any]) -> str | None:
    tur = dok.get("mevzuatTur")
    if isinstance(tur, dict):
        return _first(tur, "description", "name")
    return None


def build_human_readable_citation(dok: dict[str, Any]) -> str | None:
    """Build the Turkish citation convention: number + name + Official Gazette date/number."""
    mevzuat_no = _first(dok, "mevzuatNo")
    mevzuat_adi = _first(dok, "mevzuatAdi")
    if not mevzuat_adi:
        return None

    prefix = f"{mevzuat_no} sayili {mevzuat_adi}" if mevzuat_no else str(mevzuat_adi)

    gazette_date = _format_gazette_date(_first(dok, "resmiGazeteTarihi"))
    gazette_no = _first(dok, "resmiGazeteSayisi")
    details: list[str] = []
    if gazette_date:
        details.append(f"Resmi Gazete: {gazette_date}")
    if gazette_no:
        details.append(f"Sayi: {gazette_no}")

    if details:
        return f"{prefix} ({', '.join(details)})"
    return prefix


def build_source_url(dok: dict[str, Any]) -> str | None:
    """Return the canonical mevzuat.gov.tr URL, or a Bedesten fallback if absent."""
    url = _first(dok, "url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    mevzuat_id = _first(dok, "mevzuatId", "id")
    if mevzuat_id:
        return f"{BEDESTEN_BASE}/getDocumentContent?id={mevzuat_id}"
    return None


def parse_document(dok: dict[str, Any]) -> dict[str, Any]:
    """Build the citation contract from a Bedesten mevzuat document record."""
    out: dict[str, Any] = {}

    mevzuat_id = _first(dok, "mevzuatId", "id")
    mevzuat_no = _first(dok, "mevzuatNo")
    mevzuat_adi = _first(dok, "mevzuatAdi")
    mevzuat_tertip = _first(dok, "mevzuatTertip")
    tur_name = _tur_name(dok)
    tur_id = None
    tur = dok.get("mevzuatTur")
    if isinstance(tur, dict):
        tur_id = tur.get("id")
    gazette_date = _date_only(_first(dok, "resmiGazeteTarihi"))
    gazette_no = _first(dok, "resmiGazeteSayisi")
    gerekce_id = _first(dok, "gerekceId")

    if mevzuat_id:
        out["mevzuat_id"] = str(mevzuat_id)
    if mevzuat_no is not None:
        out["mevzuat_no"] = str(mevzuat_no)
    if mevzuat_adi:
        out["mevzuat_adi"] = mevzuat_adi
    if mevzuat_tertip is not None:
        out["mevzuat_tertip"] = str(mevzuat_tertip)
    if tur_name:
        out["mevzuat_turu"] = tur_name
    if tur_id is not None:
        out["mevzuat_tur_id"] = tur_id
    if gazette_date:
        out["resmi_gazete_tarihi"] = gazette_date
    if gazette_no:
        out["resmi_gazete_sayisi"] = str(gazette_no)
    if gerekce_id:
        out["gerekce_id"] = str(gerekce_id)

    # Citation contract (Art. 4). Turkey has no native ELI: the canonical mevzuat.gov.tr URL
    # (or a Bedesten fallback) is the stable resolvable identifier carried in eli_uri.
    source_url = build_source_url(dok)
    if source_url:
        out["eli_uri"] = source_url
        out["source_url"] = source_url

    citation = build_human_readable_citation(dok)
    if citation:
        out["human_readable_citation"] = citation

    return out


def parse_search(body: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    """Parse a ``searchDocuments`` response body -> (total_hits, [contract dicts])."""
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return 0, []
    total_raw = data.get("total", 0)
    try:
        total = int(total_raw)
    except (ValueError, TypeError):
        total = 0
    docs = data.get("mevzuatList") or []
    if not isinstance(docs, list):
        return total, []
    return total, [parse_document(d) for d in docs if isinstance(d, dict)]


def decode_document_content(body: dict[str, Any]) -> tuple[str, str] | None:
    """Decode base64 HTML/text content from a ``getDocumentContent`` response.

    Returns (decoded_content, mime_type) or None if absent/invalid.
    """
    import base64

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return None
    raw = data.get("content")
    if not isinstance(raw, str) or not raw:
        return None
    mime_type = _first(data, "mimeType", "mimetype") or "text/html"
    try:
        decoded = base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return None
    return decoded, str(mime_type)


def strip_html(html_text: str) -> str:
    """Remove HTML tags and decode entities, returning plain text."""
    import html
    import re

    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def parse_article_tree(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a ``mevzuatMaddeTree`` response body -> list of article-tree nodes."""
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return []
    children = data.get("children")
    if not isinstance(children, list):
        return []

    def _node(n: dict[str, Any]) -> dict[str, Any]:
        return {
            "madde_id": str(n.get("maddeId")) if n.get("maddeId") is not None else None,
            "madde_no": n.get("maddeNo"),
            "madde_baslik": n.get("maddeBaslik"),
            "parent_madde_id": (
                str(n.get("parentMaddeId")) if n.get("parentMaddeId") is not None else None
            ),
            "children": [_node(c) for c in (n.get("children") or []) if isinstance(c, dict)],
        }

    return [_node(n) for n in children if isinstance(n, dict)]


def parse_mevzuat_types(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a ``mevzuatTypes`` response body -> list of {type, name, count}."""
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "mevzuat_tur_id": item.get("mevzuatTurId"),
                "mevzuat_tur": item.get("mevzuatTur"),
                "mevzuat_tur_adi": item.get("mevzuatTurAdi"),
                "count": item.get("count"),
            }
        )
    return out
