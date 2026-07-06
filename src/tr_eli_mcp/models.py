"""Pydantic v2 models for the Turkish Bedesten legislation API + tr-eli-mcp."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DATASET_NOTE = (
    "This server covers Turkish legislation (Kanun/laws, KHK/decree-laws, Tuzuk/statutes, "
    "yonetmelik/regulations, Cumhurbaskanligi kararnameleri/presidential decrees, teblig/"
    "communiques and more) via the Adalet Bakanligi (Ministry of Justice) Bedesten API "
    "(bedesten.adalet.gov.tr/mevzuat), the keyless JSON backend behind the mevzuat.adalet.gov.tr "
    "search portal and a mirror of the canonical mevzuat.gov.tr legislation database. Turkey "
    "does NOT publish native ELI (/eli/) URIs - eli_uri carries the canonical, resolvable "
    "mevzuat.gov.tr URL for the document instead. Case law (Yargitay, Anayasa Mahkemesi) is "
    "NOT covered by this server: Yargitay's karararama system was unreachable at build time and "
    "the Anayasa Mahkemesi norm-kararlar-bilgi-bankasi is a client-rendered SPA with no "
    "discovered server API. See DISCOVERY.md."
)


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Legislation(_Tolerant):
    """A Turkish legislative document, parsed from a Bedesten mevzuat record."""

    mevzuat_id: str | None = None
    mevzuat_no: str | None = None
    mevzuat_adi: str | None = None
    mevzuat_tertip: str | None = None
    mevzuat_turu: str | None = None
    mevzuat_tur_id: int | None = None
    resmi_gazete_tarihi: str | None = None
    resmi_gazete_sayisi: str | None = None
    gerekce_id: str | None = None

    # Citation contract (Art. 4 CONSTITUTION).
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None


class SearchResult(_Tolerant):
    """Result of ``tr_search_legislation``."""

    query: dict[str, str | None] = Field(default_factory=dict)
    total_matched: int
    returned: int
    items: list[Legislation] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class LegislationContent(_Tolerant):
    """Result of ``tr_get_legislation_content``."""

    mevzuat_id: str
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None
    format: str = "html-to-text"
    content: str | None = None
    byte_size: int | None = None
    dataset_note: str = DATASET_NOTE


class ArticleNode(_Tolerant):
    """One node in a legislation's article tree (madde agaci / table of contents)."""

    madde_id: str | None = None
    madde_no: int | None = None
    madde_baslik: str | None = None
    parent_madde_id: str | None = None
    children: list[ArticleNode] = Field(default_factory=list)


ArticleNode.model_rebuild()


class ArticleTree(_Tolerant):
    """Result of ``tr_get_legislation_toc``."""

    mevzuat_id: str
    nodes: list[ArticleNode] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class LegislationType(_Tolerant):
    """One legislation type entry from ``mevzuatTypes``."""

    mevzuat_tur_id: int | None = None
    mevzuat_tur: str | None = None
    mevzuat_tur_adi: str | None = None
    count: int | None = None


class LegislationTypeList(_Tolerant):
    """Result of ``tr_list_legislation_types``."""

    items: list[LegislationType] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE
