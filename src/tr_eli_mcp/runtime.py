"""Lazy runtime manifest - externalizes VOLATILE config (upstream base URL,
citation-grammar version) out of the shipped package. Piloted on de-eli-mcp.

Pulls a tiny static ``tr-runtime.json.gz`` from this repo's GitHub Release on
first tool call so a dead endpoint can be repointed (edit runtime/tr-runtime.json
+ re-run the release workflow) WITHOUT a PyPI release. Falls back to the hardcoded
default in client.py if the asset is missing/unreachable (offline-safe,
local-first). The asset URL is built only here (unlinked), so its GitHub
download_count is a clean per-connector activation metric.

Opt-out: set ``TR_ELI_RUNTIME_URL=""`` to disable the fetch.
"""

from __future__ import annotations

import gzip
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

MANIFEST_URL = os.environ.get(
    "TR_ELI_RUNTIME_URL",
    "https://github.com/matematicsolutions/tr-eli-mcp/releases/latest/download/tr-runtime.json.gz",
)
_CACHE_NAME = "tr-runtime.json"
_TIMEOUT = 15
_USER_AGENT = "tr-eli-mcp-runtime (+https://github.com/matematicsolutions/tr-eli-mcp)"

_runtime: dict[str, Any] | None = None


def _cache_dir() -> Path:
    env = os.environ.get("TR_ELI_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".matematic" / "cache" / "tr-eli"


def _load_cached() -> "dict[str, Any] | None":
    try:
        p = _cache_dir() / _CACHE_NAME
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:
        pass
    return None


def _fetch_and_cache() -> "dict[str, Any]":
    if not MANIFEST_URL:
        return {}
    try:
        req = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            raw = resp.read()
        data = json.loads(gzip.decompress(raw).decode("utf-8"))
        if not isinstance(data, dict):
            return {}
        try:
            d = _cache_dir()
            d.mkdir(parents=True, exist_ok=True)
            (d / _CACHE_NAME).write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass
        return data
    except Exception:
        return {}


def get_runtime() -> "dict[str, Any]":
    """Runtime manifest, fetched once per process. Network-first, on-disk cache
    fallback, then {} so callers use their hardcoded defaults. Never raises."""
    global _runtime
    if _runtime is not None:
        return _runtime
    data = _fetch_and_cache()
    if not data:
        data = _load_cached() or {}
    _runtime = data
    return _runtime


def base_url(key: str, default: str) -> str:
    """Runtime-manifest base URL for an upstream, or ``default`` if unavailable."""
    urls = get_runtime().get("base_urls")
    if isinstance(urls, dict):
        val = urls.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return default
