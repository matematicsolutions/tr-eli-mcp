# Constitution of tr-eli-mcp

Version: 0.1.0
Date: 2026-07-06
Licence: Apache-2.0

`tr-eli-mcp` is an MCP server for Turkish legislation (Kanun, KHK, Tuzuk, Yonetmelik,
Cumhurbaskanligi Kararnamesi, Teblig and more), served as a keyless JSON API by the Adalet
Bakanligi (Ministry of Justice) at `bedesten.adalet.gov.tr/mevzuat` (the backend of the
`mevzuat.adalet.gov.tr` search portal, itself a mirror of the canonical `mevzuat.gov.tr`
legislation database). It fetches legislation text and metadata with a verifiable citation.
The MVP covers legislation search, full-text retrieval and the article tree; case law
(Yargitay, Anayasa Mahkemesi) is out of scope (see DISCOVERY.md for why).

The 4 principles below are inherited from the `eu-legal-mcp` line Constitution (Article IV).

---

## Art. 1. Public data only

The Adalet Bakanligi Bedesten API is an official Ministry of Justice source of Turkish
legislation (keyless, no authentication). The server is read-only and sends nothing beyond the
search terms / document id.

## Art. 2. Mandatory audit log

Every tool call MUST append one JSON line to `~/.matematic/audit/tr-eli-mcp.jsonl`
(ts / tool / input_hash SHA-256 / output_count_or_size / duration_ms / status). Inability to
write = the tool returns an error, it does not silently skip.

## Art. 3. Vendor neutrality

No tool hardcodes an LLM provider, assumes a model, or adds commercial telemetry. The server
talks only to `bedesten.adalet.gov.tr` and the local filesystem. Authentication: none; own
backoff + cache.

## Art. 4. A persistent identifier and a human-readable citation are mandatory

Every response MUST carry three fields:
- `eli_uri`: a stable, resolvable identifier for the document. **Turkey does not publish
  native ELI (`/eli/`) URIs**, so this field carries the equivalent stable identifier - the
  canonical `https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=...&MevzuatTur=...&MevzuatTertip=...`
  URL, which every Bedesten search record already supplies. It is derived from the source
  record, never fabricated; if a record has no such URL, a resolvable Bedesten API fallback is
  used instead and the fallback is never invented data (it is built purely from the record's
  own document id).
- `human_readable_citation`: the Turkish legislative citation convention - law number + name +
  Official Gazette (Resmi Gazete) date/number, e.g. "5237 sayili Turk Ceza Kanunu (Resmi
  Gazete: 12/10/2004, Sayi: 25611)".
- `source_url`: the same canonical mevzuat.gov.tr URL (or the Bedesten fallback).

---

## Open points

1. **Native ELI** - if/when Turkey exposes `/eli/` URIs (e.g. as part of a future EU-alignment
   legal-data-openness initiative), `eli_uri` should switch to them.
2. **Case law** (Yargitay, Anayasa Mahkemesi) - out of scope for this MVP. `karararama.yargitay
   .gov.tr` (Court of Cassation decision search) was unreachable (TCP connection timeout) from
   the build network; `normkararlarbilgibankasi.anayasa.gov.tr` (Constitutional Court) is a
   client-rendered React SPA with no discovered server API. Neither is wired up here; see
   DISCOVERY.md.
3. **mevzuat.gov.tr direct search** - the canonical portal's own search
   (`/aramasonuc`, `/Anasayfa/MevzuatDatatable`) is antiforgery-token-gated server-rendered
   HTML/JSON requiring session cookies; Bedesten is used instead as the more robust, genuinely
   keyless machine interface. The mevzuat.gov.tr URLs it returns remain the canonical citation
   target.

## Evolution of the constitution

Changes to art. 1-4 follow SEMVER + an entry in `CHANGELOG.md` + a `pyproject.toml` bump.

First version: 2026-07-06. Author: Wieslaw Mazur / MateMatic.
