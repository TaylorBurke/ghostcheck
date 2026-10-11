from datetime import date

from ghostcheck import signals
from ghostcheck.ats import Liveness, detect
from ghostcheck.history import History
from ghostcheck.models import Posting
from ghostcheck.parse import parse_posting

TODAY = date(2026, 10, 10)


def test_age_buckets():
    assert signals.age(Posting("u", date_posted=date(2026, 10, 1)), TODAY).points < 0
    assert signals.age(Posting("u", date_posted=date(2026, 5, 1)), TODAY).points == 25
    assert signals.age(Posting("u"), TODAY).points is None


def test_age_detail_shows_last_updated():
    p = Posting("u", date_posted=date(2026, 5, 1), last_updated=date(2026, 10, 1))
    assert "last updated 9 days ago" in signals.age(p, TODAY).detail


def test_expired_valid_through():
    p = Posting("u", valid_through=date(2026, 9, 1))
    assert signals.age(p, TODAY).points == 25


def test_pipeline_language_flagged():
    p = Posting("u", description="Join our talent pipeline for future opportunities. " * 5)
    s = signals.quality(p)
    assert s.points >= 20 and "pipeline" in s.detail


def test_liveness():
    assert signals.liveness(Liveness(False, "gone")).points == 30
    assert signals.liveness(Liveness(True, "ok")).points < 0
    assert signals.liveness(Liveness(None, "?")).points is None


def test_combine_clamps_and_skips_unknown():
    from ghostcheck.models import Signal
    assert signals.combine([Signal("a", None, ""), Signal("b", 500, "")]) == 100
    assert signals.combine([Signal("a", -500, "")]) == 0


def test_detect_ats():
    assert detect("https://boards.greenhouse.io/acme/jobs/123").vendor == "greenhouse"
    assert detect("https://jobs.lever.co/acme/abc-def").board == "acme"
    assert detect("https://jobs.ashbyhq.com/acme/uuid").job_id == "uuid"
    assert detect("https://www.linkedin.com/jobs/view/1") is None


def test_parse_jsonld():
    html = '''<script type="application/ld+json">{"@type":"JobPosting","title":"Dev",
    "datePosted":"2026-01-02","hiringOrganization":{"name":"Acme"},"description":"<p>Hi</p>",
    "baseSalary":{"value":1}}</script>'''
    p = parse_posting("u", html)
    assert (p.title, p.company, p.date_posted, p.has_salary) == ("Dev", "Acme", date(2026, 1, 2), True)


def test_history_repost_detection():
    h = History.__new__(History)
    import sqlite3
    h.path = ":memory:"
    h.db = sqlite3.connect(":memory:")
    h.db.execute("CREATE TABLE seen (fp TEXT, url TEXT, seen_on TEXT, date_posted TEXT, PRIMARY KEY (fp, url, seen_on))")
    p1, p2 = Posting("a", title="Dev", company="Acme"), Posting("b", title="Dev", company="Acme")
    h.record(p1, date(2026, 8, 1))
    h.record(p2, TODAY)
    assert h.distinct_urls(p1) == 2
    s = signals.reposts(h.first_seen(p1), h.distinct_urls(p1), TODAY)
    assert s.points == 25


def test_news_headline_proximity():
    import re
    from ghostcheck import news
    assert news.layoff_headlines("") is None


def test_domain_age_buckets():
    s = signals.domain_age("acme.io", "job link", date(2026, 9, 1), TODAY)
    assert s.points == 20 and "acme.io" in s.detail
    assert signals.domain_age("acme.io", "x", date(2015, 1, 1), TODAY).points == -3
    assert signals.domain_age(None, "", None, TODAY).points is None
    assert signals.domain_age("a.com", "x", None, TODAY).points is None


def test_company_domain_resolution():
    from ghostcheck.domain import company_domain, registrable
    assert registrable("careers.acme.co.uk") == "acme.co.uk"
    assert company_domain("https://jobs.lever.co/acme/1", "https://www.acme.com/about") == ("acme.com", "posting")
    assert company_domain("https://careers.acme.com/job/1") == ("acme.com", "job link")
    assert company_domain("https://www.linkedin.com/jobs/view/1") is None


def test_company_signal_keeps_links():
    s = signals.company([("Acme lays off 200", "http://n/1")])
    assert s.links == [("Acme lays off 200", "http://n/1")]
    assert signals.company([]).links == []


def test_csv_urls(tmp_path):
    from ghostcheck.cli import _csv_urls
    f = tmp_path / "a.csv"
    f.write_text("Employer,Job Title,Job Posting Link\nAcme,Dev,http://x\nBeta,QA,\n")
    assert _csv_urls(str(f)) == [("Acme / Dev", "http://x")]
