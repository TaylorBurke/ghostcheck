"""Liveness checks against the public job-board APIs of common ATS vendors."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .http import get_json


@dataclass
class AtsRef:
    vendor: str  # greenhouse | lever | ashby
    board: str
    job_id: str


def detect(url: str) -> AtsRef | None:
    u = urlparse(url)
    host, parts = u.netloc.lower(), [p for p in u.path.split("/") if p]
    if host.endswith("greenhouse.io"):
        if m := re.search(r"[?&]gh_jid=(\d+)", url):
            return AtsRef("greenhouse", parts[0] if parts else "", m.group(1))
        if "jobs" in parts and parts.index("jobs") + 1 < len(parts) and parts:
            return AtsRef("greenhouse", parts[0], parts[parts.index("jobs") + 1])
    if host == "jobs.lever.co" and len(parts) >= 2:
        return AtsRef("lever", parts[0], parts[1])
    if host == "jobs.ashbyhq.com" and len(parts) >= 2:
        return AtsRef("ashby", parts[0], parts[1])
    return None


@dataclass
class Liveness:
    live: bool | None  # None = could not determine
    detail: str
    open_same_title: int = 0  # how many open roles share the title (duplicate signal)
    board_size: int = 0


def _count_same_title(titles: list[str], title: str) -> int:
    t = title.strip().lower()
    return sum(1 for x in titles if x.strip().lower() == t) if t else 0


def check_live(ref: AtsRef, title: str = "") -> Liveness:
    if ref.vendor == "greenhouse":
        status, data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{ref.board}/jobs?content=false")
        if data is None:
            return Liveness(None, f"Greenhouse board '{ref.board}' unreachable (HTTP {status})")
        jobs = data.get("jobs", [])
        live = any(str(j.get("id")) == ref.job_id for j in jobs)
        titles = [j.get("title", "") for j in jobs]
    elif ref.vendor == "lever":
        status, data = get_json(f"https://api.lever.co/v0/postings/{ref.board}?mode=json")
        if data is None:
            return Liveness(None, f"Lever board '{ref.board}' unreachable (HTTP {status})")
        live = any(j.get("id") == ref.job_id for j in data)
        titles = [j.get("text", "") for j in data]
    elif ref.vendor == "ashby":
        status, data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{ref.board}")
        if data is None:
            return Liveness(None, f"Ashby board '{ref.board}' unreachable (HTTP {status})")
        jobs = data.get("jobs", [])
        live = any(j.get("id") == ref.job_id for j in jobs)
        titles = [j.get("title", "") for j in jobs]
    else:
        return Liveness(None, "unsupported ATS")

    where = f"{ref.vendor} board '{ref.board}'"
    return Liveness(
        live,
        f"posting {'is' if live else 'is NOT'} listed on {where}",
        _count_same_title(titles, title),
        len(titles),
    )


def find_on_boards(company: str, title: str) -> Liveness:
    """For aggregator links (LinkedIn/Indeed): look for the role on the company's own ATS board."""
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    if not slug or not title:
        return Liveness(None, "no company/title to search the company's own boards")
    t = title.strip().lower()
    reached = False
    for vendor, url, key in (
        ("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", "title"),
        ("lever", f"https://api.lever.co/v0/postings/{slug}?mode=json", "text"),
        ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}", "title"),
    ):
        _, data = get_json(url)
        if data is None:
            continue
        reached = True
        jobs = data.get("jobs", []) if isinstance(data, dict) else data
        titles = [j.get(key, "") for j in jobs]
        n = _count_same_title(titles, title)
        if n:
            return Liveness(True, f"'{title}' found on {company}'s {vendor} board", n, len(titles))
        if any(t in x.lower() or x.lower() in t for x in titles if x):
            return Liveness(True, f"similar title found on {company}'s {vendor} board", 0, len(titles))
        return Liveness(False, f"'{title}' not on {company}'s {vendor} board ({len(titles)} open roles)", 0, len(titles))
    return Liveness(None, "company board not found on Greenhouse/Lever/Ashby" if not reached else "")


def _ms_date(ms):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date() if ms else None


def fetch_posting(ref: AtsRef, url: str):
    """Structured posting details straight from the ATS API (richer than scraping the page)."""
    from .parse import html_to_text, parse_date
    from .models import Posting

    if ref.vendor == "greenhouse":
        _, d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{ref.board}/jobs/{ref.job_id}?pay_transparency=true")
        if not d:
            return None
        return Posting(
            url=url,
            title=d.get("title", ""),
            company=d.get("company_name") or ref.board,
            location=(d.get("location") or {}).get("name", ""),
            description=html_to_text(d.get("content", "")),
            date_posted=parse_date(d.get("first_published") or d.get("updated_at")),
            last_updated=parse_date(d.get("updated_at")),
            has_salary=bool(d.get("pay_input_ranges")),
        )
    if ref.vendor == "lever":
        _, d = get_json(f"https://api.lever.co/v0/postings/{ref.board}/{ref.job_id}")
        if not d:
            return None
        return Posting(
            url=url,
            title=d.get("text", ""),
            company=ref.board,
            location=(d.get("categories") or {}).get("location", ""),
            description=d.get("descriptionPlain", ""),
            date_posted=_ms_date(d.get("createdAt")),
            has_salary=bool(d.get("salaryRange")),
        )
    if ref.vendor == "ashby":
        _, d = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{ref.board}?includeCompensation=true")
        for j in (d or {}).get("jobs", []):
            if j.get("id") == ref.job_id:
                return Posting(
                    url=url,
                    title=j.get("title", ""),
                    company=ref.board,
                    location=j.get("location", ""),
                    description=j.get("descriptionPlain", ""),
                    date_posted=parse_date(j.get("publishedAt")),
                    has_salary=bool(j.get("compensation")),
                )
    return None
