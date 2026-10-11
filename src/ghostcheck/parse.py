from __future__ import annotations

import html
import json
import re
from datetime import date, datetime

from .models import Posting

_LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)


def html_to_text(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAGS.sub(" ", raw))).strip()


def parse_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _find_job(node):
    if isinstance(node, list):
        for n in node:
            if (found := _find_job(n)):
                return found
    elif isinstance(node, dict):
        t = node.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            return node
        return _find_job(node.get("@graph"))
    return None


def _location(job: dict) -> str:
    loc = job.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            return ", ".join(filter(None, [addr.get("addressLocality"), addr.get("addressRegion")]))
    return ""


def parse_posting(url: str, raw_html: str) -> Posting:
    """Build a Posting from schema.org JobPosting JSON-LD, falling back to page text."""
    job = None
    for block in _LD.findall(raw_html):
        try:
            job = _find_job(json.loads(block))
        except ValueError:
            continue
        if job:
            break

    if not job:
        title = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.S | re.I)
        return Posting(
            url=url,
            title=html.unescape(title.group(1)).strip() if title else "",
            description=html_to_text(raw_html),
            has_salary=bool(re.search(r"\$\s?\d{2,3}[,.]?\d*\s?[kK]?", raw_html)),
        )

    org = job.get("hiringOrganization")
    company = org.get("name", "") if isinstance(org, dict) else (org or "")
    return Posting(
        url=url,
        title=job.get("title", ""),
        company=company,
        location=_location(job),
        description=html_to_text(job.get("description", "")),
        date_posted=parse_date(job.get("datePosted")),
        valid_through=parse_date(job.get("validThrough")),
        has_salary=bool(job.get("baseSalary")),
    )
