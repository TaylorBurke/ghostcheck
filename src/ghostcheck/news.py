from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

from .http import get

_BAD = re.compile(r"layoff|lays off|laid off|job cuts|cuts jobs|hiring freeze|workforce reduction", re.I)


def layoff_headlines(company: str) -> list[str] | None:
    """Recent Google News RSS headlines mentioning layoffs. None if the lookup failed."""
    if not company:
        return None
    q = quote(f'"{company}" layoffs OR "hiring freeze" when:180d')
    status, body = get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
    if status != 200:
        return None
    try:
        items = ET.fromstring(body).iter("item")
    except ET.ParseError:
        return None
    name = re.escape(company.lower())
    near = re.compile(
        rf"{name}\W+(?:\w+\W+){{0,3}}?(?:lays? off|laid off|layoffs?|cuts?|freez\w*|slash\w*)|"
        rf"(?:layoffs?|job cuts|hiring freeze|cuts \d+\S* jobs?)\W+(?:\w+\W+){{0,2}}?(?:at|by|from)\W+{name}"
    )
    out = []
    for it in items:
        title = (it.findtext("title") or "").strip()
        if _BAD.search(title) and near.search(title.lower()):
            out.append(title)
    return out[:5]
