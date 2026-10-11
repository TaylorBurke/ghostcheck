from __future__ import annotations

from datetime import date

from . import ats, news, signals
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
    if posting is None:
        status, raw = get(url)
        posting = parse_posting(url, raw) if status == 200 else Posting(url=url)
        if status != 200:
            posting.description = ""
    gone = posting.title == "" and posting.description == ""

    lv = None
    if not offline:
        if ref:
            lv = ats.check_live(ref, posting.title)
        elif posting.company:
            lv = ats.find_on_boards(posting.company, posting.title)

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
        signals.company(None if offline else news.layoff_headlines(posting.company)),
    ]
    score = signals.combine(sigs)
    if gone and not offline:
        score = max(score, 60)
        sigs.append(signals.Signal("fetch", None, "page could not be fetched (removed, or blocked)"))
    return Report(posting, score, signals.verdict(score), sigs)
