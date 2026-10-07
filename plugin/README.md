# tr-eli-mcp - Claude plugin

Turkish law with verifiable citations, as a Claude plugin. It runs the
[tr-eli-mcp](https://github.com/matematicsolutions/tr-eli-mcp) MCP server, version 0.3.4
from PyPI. `server/uv.lock` pins that package and every dependency with hashes, and the
plugin starts it with `uv run --frozen`, so it runs exactly what was reviewed. Every
answer carries the official source, so a citation can be checked instead of trusted.

What it covers: Turkish legislation through the Ministry of Justice's Bedesten API (the service behind mevzuat.gov.tr): search by text, type and number, the table of contents and the content of an act, and the list of legislation types. The full tool list is in the
[main README](https://github.com/matematicsolutions/tr-eli-mcp#readme).

## Requirements

Claude Code or the Claude desktop app, and [uv](https://docs.astral.sh/uv/) on your
machine (it installs the locked packages on first start and runs the server).

## Install

```
/plugin marketplace add matematicsolutions/tr-eli-mcp
/plugin install tr-eli-mcp@tr-eli-mcp
```

## Data

The server runs on your machine. Each tool call sends your query to the Turkish Ministry of Justice's legislation service (bedesten.adalet.gov.tr)
and to nothing else; nothing goes to MateMatic. Your query and the results also pass
through whatever model you use, the same way as any other message.

The standalone server can fetch a small configuration file (updated source addresses) from
this repository's GitHub Releases on first use. The plugin turns that off
(`TR_ELI_RUNTIME_URL` set to empty in `plugin.json`), so it runs only the reviewed code with
its built-in source addresses and makes no request other than the tool calls above.

Two things are written locally, in your home directory:

- a response cache (`~/.matematic/cache/tr-eli`), so a repeated lookup does not hit
  the source again. The sources are published legislation.
- an audit log (`~/.matematic/audit/tr-eli-mcp.jsonl`), one line per tool call: the
  tool name, a SHA-256 hash of the input (not the input itself), result size, time
  and status.

Delete either folder at any time; `TR_ELI_CACHE_DIR` and `TR_ELI_AUDIT_DIR` move them.

## Licence

Apache-2.0, see the repository's [LICENSE](https://github.com/matematicsolutions/tr-eli-mcp/blob/main/LICENSE).
