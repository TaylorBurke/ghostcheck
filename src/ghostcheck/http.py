from __future__ import annotations

import json
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) ghostcheck/0.1"


def get(url: str, timeout: float = 15) -> tuple[int, str]:
    """Return (status, body). Status 0 means a network failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""  # 403/429 usually mean "blocked", not "removed"; callers decide
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def get_json(url: str, timeout: float = 15):
    status, body = get(url, timeout)
    if status != 200:
        return status, None
    try:
        return status, json.loads(body)
    except ValueError:
        return status, None
