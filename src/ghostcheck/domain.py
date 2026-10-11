"""Find the company's website and look up how old its domain is (RDAP, the JSON successor to WHOIS)."""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlparse

from .http import get, get_json
from .parse import parse_date

# Hosts that are job boards / ATS vendors, not the company's own site.
_NOT_COMPANY = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "applytojob.com", "breezy.hr",
    "smartrecruiters.com", "myworkdayjobs.com", "icims.com", "jobvite.com", "bamboohr.com",
    "recruitee.com", "teamtailor.com", "linkedin.com", "indeed.com", "glassdoor.com",
    "wellfound.com", "angel.co", "ziprecruiter.com", "monster.com", "dice.com", "simplyhired.com",
    "builtin.com", "remoteok.com", "weworkremotely.com", "ycombinator.com", "google.com",
)
_TWO_LEVEL = {"co.uk", "org.uk", "com.au", "co.nz", "co.jp", "com.br", "co.in", "com.mx", "co.za"}


def registrable(host: str) -> str:
    """Approximate registrable domain (last two labels; three for common two-level suffixes)."""
    parts = host.lower().split(":")[0].strip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _is_vendor(domain: str) -> bool:
    return any(domain == v or domain.endswith("." + v) for v in _NOT_COMPANY)


def company_domain(job_url: str, company_url: str = "", company: str = "") -> tuple[str, str] | None:
    """Return (domain, how) or None. how: 'posting' | 'job link' | 'guessed from name'."""
    if company_url:
        d = registrable(urlparse(company_url).netloc)
        if d and not _is_vendor(d):
            return d, "posting"
    d = registrable(urlparse(job_url).netloc)
    if d and not _is_vendor(d):
        return d, "job link"
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    if slug:
        guess = f"{slug}.com"
        status, body = get(f"https://{guess}", timeout=8)
        first = company.lower().split()[0]
        if status == 200 and first in body.lower()[:20000]:
            return guess, "guessed from name"
    return None


def registration_date(domain: str) -> date | None:
    _, data = get_json(f"https://rdap.org/domain/{domain}", timeout=15)
    for e in (data or {}).get("events", []):
        if e.get("eventAction") == "registration":
            return parse_date(e.get("eventDate"))
    return None
