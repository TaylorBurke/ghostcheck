from __future__ import annotations

from datetime import date

from . import ats, domain, news, signals
from .history import History
from .http import get
from .models import Posting, Report
from .parse import parse_posting


def check(
    url: str,
    *,
    today: date | None = None,
    history: History | None = None,
    posting: Posting | None = None,
    offline: bool = False,
) -> Report:
    today = today or date.today()
    ref = ats.detect(url)
    if posting is None and ref and not offline:
        posting = ats.fetch_posting(ref, url)
    gone = False
    if posting is None:
        status, raw = get(url)
        posting = parse_posting(url, raw) if status == 200 else Posting(url=url)
        # Only 404/410 mean the posting was removed; 403/429/timeouts are just blocked or flaky.
        gone = status in (404, 410)

    lv = None
    if not offline:
        if ref:
            lv = ats.check_live(ref, posting.title)
        elif posting.company:
            lv = ats.find_on_boards(posting.company, posting.title)

    dom, how, registered = None, "", None
    if not offline and (found := domain.company_domain(url, posting.company_url, posting.company)):
        dom, how = found
        registered = domain.registration_date(dom)

    # Aggregator link matched to a company board entry: borrow its real date/salary/description.
    if lv and lv.match and (rich := ats.fetch_posting(lv.match, url)):
        posting.date_posted = posting.date_posted or rich.date_posted
        posting.last_updated = posting.last_updated or rich.last_updated
        posting.has_salary = posting.has_salary or rich.has_salary
        posting.description = posting.description or rich.description

    first_seen, urls = None, 0
    if history:
        history.record(posting, today)
        first_seen, urls = history.first_seen(posting), history.distinct_urls(posting)
        if first_seen == today:
            first_seen = None  # only just recorded; nothing to compare against yet

    sigs = [
        signals.age(posting, today),
        signals.reposts(first_seen, urls, today) if history else signals.reposts(None, 0, today),
        signals.liveness(lv),
        signals.duplicates(lv),
        signals.quality(posting),
        signals.domain_age(dom, how, registered, today),
        signals.company(None if offline else news.layoff_headlines(posting.company)),
    ]
    score = signals.combine(sigs)
    if gone and not offline:
        score = max(score, 60)
        sigs.append(signals.Signal("fetch", None, "page returned 404/410 (removed)"))
    return Report(posting, score, signals.verdict(score), sigs)
