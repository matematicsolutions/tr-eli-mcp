# tr-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/tr-eli-mcp -->

An MCP server for **Turkish legislation** (Kanun/laws, KHK/decree-laws, Tuzuk/statutes,
Yonetmelik/regulations, Cumhurbaskanligi Kararnamesi/presidential decrees, Teblig/communiques
and more), served as a keyless JSON API by the **Adalet Bakanligi** (Ministry of Justice) at
`bedesten.adalet.gov.tr/mevzuat`. It gives an AI agent legislation text and metadata with a
verifiable citation: a resolvable identifier, a human-readable citation, and a link to the
official source.

Part of the **eu-legal-mcp** line by [MateMatic](https://matematic.co) — one connector per
country, the same citation contract everywhere. Turkey is included under this line's broader
"Europe" framing (Council of Europe member, EU accession candidate), alongside connectors that
map strictly to EU-27 membership.

> **On ELI.** Turkey does **not** publish native ELI (`/eli/`) URIs. To keep the line's
> contract honest, `eli_uri` carries the canonical, resolvable `mevzuat.gov.tr` URL instead —
> e.g. `https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5237&MevzuatTur=1&MevzuatTertip=5` — which
> every Bedesten search record already supplies. The connector never fabricates an `/eli/` URI
> and says so in its tool instructions. See `DISCOVERY.md`.
>
> **On case law.** This connector covers **legislation only**. Yargitay (Court of Cassation)
> decision search was unreachable (TCP timeout) from the build network, and Anayasa Mahkemesi
> (Constitutional Court) exposes only a client-rendered SPA with no discovered server API.
> Neither is wired up here — see `DISCOVERY.md` for what was actually checked.

## Tools

| Tool | What it does |
|---|---|
| `tr_search_legislation(query, mevzuat_turu=None, mevzuat_no=None, baslikta_ara=True)` | Search Turkish legislation by title and/or full text, optionally filtered by type and number. |
| `tr_get_legislation_content(mevzuat_id)` | The full text of one document (HTML converted to plain text). |
| `tr_get_legislation_toc(mevzuat_id)` | The article tree (madde agaci / table of contents) of one document. |
| `tr_list_legislation_types()` | Enumerate all legislation types with live document counts (KANUN, KHK, YONETMELIK, ...). |
| `tr_coverage()` | Declare what this connector covers, when each family was captured, and - explicitly - what it does NOT cover. Every gap carries a fallback. |

Every response carries the **citation contract**:

- `eli_uri` — the canonical, resolvable `mevzuat.gov.tr` identifier (see the ELI note above).
- `human_readable_citation` — the Turkish citation convention: law number + name + Official
  Gazette (Resmi Gazete) date/number, e.g. *5237 sayili Turk Ceza Kanunu (Resmi Gazete:
  12/10/2004, Sayi: 25611)*.
- `source_url` — the same canonical `mevzuat.gov.tr` page.

## Install

```bash
pip install -e ".[dev]"
```

Register it with your MCP client (see `.mcp.json.example`):

```json
{
  "mcpServers": {
    "tr-eli-mcp": {
      "command": "tr-eli-mcp",
      "env": {
        "TR_ELI_BASE_URL": "https://bedesten.adalet.gov.tr/mevzuat",
        "TR_ELI_CACHE_DIR": "~/.matematic/cache/tr-eli",
        "TR_ELI_AUDIT_DIR": "~/.matematic/audit"
      }
    }
  }
}
```

### Windows 11 with Smart App Control

Smart App Control blocks unsigned executables, which covers `uvx.exe`, `pip.exe`
and the `tr-eli-mcp.exe` launcher that pip writes at install time. The `python.exe` and
`py.exe` from the python.org installer are signed by the Python Software
Foundation, so running the module through the interpreter works:

```bash
python -m pip install tr-eli-mcp
python -m tr_eli_mcp
```

`pip.exe` is blocked for the same reason, so install with `python -m pip`, not
`pip install`. If `python` is not on PATH, use the Windows launcher: `py -3 -m tr_eli_mcp`.

```json
{ "mcpServers": { "tr-eli-mcp": { "command": "python", "args": ["-m", "tr_eli_mcp"] } } }
```

Do not turn Smart App Control off to work around this - it cannot be re-enabled
without reinstalling Windows.

## Design

- **Public data only.** Read-only against the keyless Adalet Bakanligi Bedesten API; nothing is
  sent beyond the query / document id.
- **Audit log.** Every call appends one JSON line to `~/.matematic/audit/tr-eli-mcp.jsonl`
  (AI Act art. 12 record-keeping).
- **Vendor-neutral.** No LLM provider, no telemetry; own backoff + on-disk cache.
- **No fabrication.** Identifiers and titles are parsed from the source record. If Bedesten's
  schema changes, the connector fails loudly rather than returning stale or invented data.

See `CONSTITUTION.md` (the 4 principles) and `DISCOVERY.md` (how the source was mapped, and
what was ruled out).

## Tests

```bash
pytest tests/test_instructions_drift.py   # offline
pytest tests/test_smoke.py                # live Bedesten API
```

## Licence

Apache-2.0. The Turkish legislation served is official public data of the Republic of Turkey;
this connector adds no rights over it.
