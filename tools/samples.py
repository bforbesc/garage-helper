from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import settings

FREESOUND_BASE = "https://freesound.org/apiv2"


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^\w.-]+", "_", name.strip())
    return name or "sample"


def _is_host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    allowed = [h.strip().lower() for h in settings.allowed_download_hosts.split(",") if h.strip()]
    return any(host == h or host.endswith(f".{h}") for h in allowed)


def search_freesound(query: str, page_size: int = 12) -> dict:
    if not settings.freesound_api_key:
        return {"ok": False, "error": "FREESOUND_API_KEY not set"}
    params = {
        "query": query,
        "page_size": max(1, min(page_size, 50)),
        "fields": "id,name,previews,license,duration,type,tags,url",
        "token": settings.freesound_api_key,
    }
    resp = requests.get(f"{FREESOUND_BASE}/search/text/", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("results", []):
        preview = item.get("previews", {}).get("preview-hq-mp3") or item.get("previews", {}).get("preview-lq-mp3")
        results.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "duration": item.get("duration"),
                "license": item.get("license"),
                "type": item.get("type"),
                "tags": item.get("tags", []),
                "preview_url": preview,
                "source_url": item.get("url"),
            }
        )
    return {"ok": True, "query": query, "results": results}


def download_file(url: str, filename: str | None = None) -> dict:
    if not _is_host_allowed(url):
        return {"ok": False, "error": "Download host is not allowed by ALLOWED_DOWNLOAD_HOSTS"}

    out_dir = Path(settings.downloads_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    basename = filename or Path(urlparse(url).path).name or "sample.bin"
    target = out_dir / _safe_filename(basename)
    total_bytes = 0
    max_bytes = settings.max_download_mb * 1024 * 1024
    with requests.get(url, timeout=60, stream=True) as r:
        r.raise_for_status()
        with open(target, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        f.close()
                        target.unlink(missing_ok=True)
                        return {"ok": False, "error": f"File exceeds MAX_DOWNLOAD_MB={settings.max_download_mb}"}
                    f.write(chunk)
    return {"ok": True, "path": str(target), "url": url}
