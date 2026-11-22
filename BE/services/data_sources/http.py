from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_HEADERS = {
    "User-Agent": "KOWR-Water-Assistant/1.0",
    "Accept": "application/json, text/plain, */*",
}

CACHE_DIR = Path(".cache/http")


def _build_cache_key(method: str, url: str, data: Optional[bytes]) -> Path:
    digest = hashlib.sha256()
    digest.update(method.encode("utf-8"))
    digest.update(b"\n")
    digest.update(url.encode("utf-8"))
    digest.update(b"\n")
    if data:
        digest.update(data)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{digest.hexdigest()}.json"


def _load_cached(path: Path, ttl_seconds: int) -> Optional[str]:
    if not path.exists():
        return None
    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > ttl_seconds:
        return None
    return path.read_text(encoding="utf-8")


def _load_stale_cached(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _read_response_text(response, limit: int = 8_000_000) -> str:
    chunks = []
    total = 0
    while total < limit:
        chunk = response.read(min(65536, limit - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks).decode("utf-8")


def fetch_text(
    url: str,
    *,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    cache_ttl_seconds: int = 0,
) -> str:
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"

    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)

    cache_path = _build_cache_key(method, url, data)
    if cache_ttl_seconds > 0:
        cached = _load_cached(cache_path, cache_ttl_seconds)
        if cached is not None:
            return cached

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    context = ssl.create_default_context()
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                payload = _read_response_text(response)
                if cache_ttl_seconds > 0:
                    cache_path.write_text(payload, encoding="utf-8")
                return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            should_retry = exc.code in {429, 500, 502, 503, 504} and attempt == 0
            if should_retry:
                time.sleep(2)
                continue
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1)
                continue
            break

    if cache_ttl_seconds > 0:
        stale = _load_stale_cached(cache_path)
        if stale is not None:
            return stale
    if last_error:
        raise last_error
    raise RuntimeError("Unreachable fetch state")


def fetch_json(
    url: str,
    *,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    cache_ttl_seconds: int = 0,
) -> Any:
    data = None
    merged_headers = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        merged_headers.setdefault("Content-Type", "application/json")

    payload = fetch_text(
        url,
        method=method,
        params=params,
        data=data,
        headers=merged_headers,
        timeout=timeout,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return json.loads(payload)


def fetch_form_json(url: str, form_data: Dict[str, Any], timeout: int = 30, cache_ttl_seconds: int = 0) -> Any:
    encoded = urllib.parse.urlencode(form_data).encode("utf-8")
    payload = fetch_text(
        url,
        method="POST",
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return json.loads(payload)


def safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs), None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, KeyError, OverflowError) as exc:
        return None, str(exc)
