# DISCOVERY - Turkey (legislation via Adalet Bakanligi Bedesten API)

Date: 2026-07-06. Status: **BUILD** (4-tool grounding MVP shipped, legislation only).

## Sources investigated, live-verified

### 1. `mevzuat.gov.tr` (Mevzuat Bilgi Sistemi, canonical consolidated-legislation database)

Live, healthy ASP.NET Core server (HTTP 200, full server-rendered HTML). Its search endpoint
(`POST /aramasonuc`, form-post) and its internal DataTables endpoint
(`POST /Anasayfa/MevzuatDatatable`) both require an `.AspNetCore.Antiforgery.*` session cookie
and a matching `__RequestVerificationToken` / `antiforgerytoken` field obtained from a prior
page load. This is workable but fragile (token rotates per session, requires a real browser
context or cookie-jar dance) - not a stable machine interface. Document pages
(`/mevzuat?MevzuatNo=...&MevzuatTur=...&MevzuatTertip=...`) are plain server-rendered HTML and
DO resolve reliably without a session - these URLs are used as the citation target
(`eli_uri`/`source_url`) even though the search itself is not built against this host directly.

### 2. `resmigazete.gov.tr` (Official Gazette)

Live ASP.NET Core server, HTML only, no JSON/XML API discovered. Not used as a build target;
useful only as a citation cross-reference (gazette date/number, already present in Bedesten
records).

### 3. `bedesten.adalet.gov.tr/mevzuat` - THE BUILD TARGET

A genuine, keyless JSON REST API run by the Adalet Bakanligi (Ministry of Justice), serving as
the backend for the `mevzuat.adalet.gov.tr` search portal. Confirmed live via direct `curl`
(no browser, no cookies, no antiforgery token, no API key):

- `POST /searchDocuments` - body
  `{"data":{"pageSize":3,"pageNumber":1,"sortFields":["RESMI_GAZETE_TARIHI"],
  "sortDirection":"desc","mevzuatAdi":"vergi","mevzuatTurList":["KANUN"]},
  "applicationName":"UyapMevzuat","paging":true}` with headers
  `Content-Type: application/json; charset=utf-8`, `AdaletApplicationName: UyapMevzuat`,
  `Origin: https://mevzuat.adalet.gov.tr`, `Referer: https://mevzuat.adalet.gov.tr/` returned
  HTTP 200 with clean structured JSON: real law records (e.g. mevzuatId 329497, mevzuatNo 7524,
  "VERGI KANUNLARI ILE BAZI KANUNLARDA ...", resmiGazeteTarihi 2024-08-02, resmiGazeteSayisi
  32620, and the canonical `mevzuat.gov.tr` URL for the record).
- `POST /getDocumentContent` - body `{"data":{"documentType":"MEVZUAT","id":"104289"},
  "applicationName":"UyapMevzuat"}` returned a 135 KB response with base64-encoded HTML
  (decodes to the actual Word-exported full text of Law No. 7103).
- `POST /mevzuatMaddeTree` - body `{"data":{"mevzuatId":"104289"},
  "applicationName":"UyapMevzuat"}` returned an 11 KB nested JSON article tree (madde_id,
  madde_no, madde_baslik, children) for the same law.
- `POST /mevzuatTypes` - body `{"data":{},"applicationName":"UyapMevzuat"}` returned a live
  enumeration of legislation types with counts (e.g. KANUN: 916 documents, live update
  timestamps through July 2026).

No WAF challenge, no Cloudflare block, no rate-limit hit during probing. Response envelope:
`{"data": ..., "metadata": {"FMTY": "SUCCESS"|"ERROR", "FMTE": "..."}}`; all requests wrapped
`{"data": {...}, "applicationName": "UyapMevzuat"}`.

An existing open-source project, `saidsurucu/mevzuat-mcp` (MIT), independently reverse-engineered
this same API and was used only to cross-check endpoint/payload shapes after our own live
verification - not copied wholesale; this connector's client/citation/model code is a fresh
implementation matching the matematicsolutions factory conventions.

### 4. Case law - Yargitay and Anayasa Mahkemesi (out of scope)

- `karararama.yargitay.gov.tr` (Court of Cassation decision search): DNS resolves, but the TCP
  connection to port 443 timed out from the build network. Not usable; not attempted further.
- `normkararlarbilgibankasi.anayasa.gov.tr` (Constitutional Court decision database): resolves
  and responds, but serves a client-rendered React SPA shell (`<title>` tag reads "Metronic
  React Demo 5", ~2 KB HTML with no inline data) behind an F5/BIG-IP-style `TS...` cookie. No
  server-side JSON API was discovered in the time available. Not usable; not attempted further.
- No ELI-conformant or EU-alignment legal-open-data initiative was found for Turkey. Turkey is
  not listed among ELI Task Force member states/participants as of this search.

## Identifiers

- **mevzuat_id** (Bedesten's internal document id, e.g. `104289`) - the primary key used to
  fetch content and the article tree.
- **mevzuat_no** (the legislation number, e.g. `5237` for the Turkish Penal Code) - the
  human-facing number; combined with the legislation type + tertip to build the canonical
  `mevzuat.gov.tr` URL: `?MevzuatNo=<no>&MevzuatTur=<tur_id>&MevzuatTertip=<tertip>`.

## Citation contract (Art. IV)

| Field | Source | Example |
|---|---|---|
| `eli_uri` | canonical `mevzuat.gov.tr` URL from the Bedesten record's `url` field | `https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=7103&MevzuatTur=1&MevzuatTertip=5` |
| `human_readable_citation` | built from `mevzuatNo` + `mevzuatAdi` + `resmiGazeteTarihi` + `resmiGazeteSayisi` | `7103 sayili VERGI KANUNLARI ILE BAZI KANUN VE KANUN HUKMUNDE KARARNAMELERDE DEGISIKLIK YAPILMASI HAKKINDA KANUN (Resmi Gazete: 27/03/2018, Sayi: 30373 (Mukerrer))` |
| `source_url` | same as `eli_uri` | as above |

**ELI note (decisive).** Turkey has **not deployed native ELI (`/eli/`) URIs**. None of the
machine sources (Bedesten search/content/tree responses) carries an `/eli/` identifier; the
canonical resolvable identifier is the `mevzuat.gov.tr` document URL, already embedded in every
Bedesten search record as its `url` field. Per the line rule "parse the identifier, never
fabricate it", `eli_uri` carries this equivalent stable identifier, stated plainly in
INSTRUCTIONS, README and CONSTITUTION.

## Tools

- `tr_search_legislation(query, mevzuat_turu=None, mevzuat_no=None, baslikta_ara=True)` -
  `POST /searchDocuments`, return legislation records with the citation contract.
- `tr_get_legislation_content(mevzuat_id)` - `POST /getDocumentContent`
  (`documentType=MEVZUAT`), decode base64 HTML, strip tags to plain text.
- `tr_get_legislation_toc(mevzuat_id)` - `POST /mevzuatMaddeTree`, return the nested article
  tree (chapters/articles hierarchy).
- `tr_list_legislation_types()` - `POST /mevzuatTypes`, enumerate all legislation types with
  live document counts.

## Open points

- Per-article content (`documentType=MADDE`) is implemented in `client.py`
  (`get_article_content`) but not yet exposed as a dedicated tool in this MVP; a future
  `tr_get_article_content(madde_id)` tool can wrap it directly.
- Law rationale (gerekce - amaç, komisyon raporlari, madde gerekçeleri) is out of scope for
  this MVP; `gerekce_id` is already surfaced on search results for a future tool.
- Case law (Yargitay, Anayasa Mahkemesi) out of scope - see above.
