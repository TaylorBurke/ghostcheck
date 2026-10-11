# ghostcheck

A free, no-API-key estimator for ghost job postings: listings that are stale, never
going to be filled, or kept up to farm resumes. Python library + CLI, standard library only.

It gives a 0-100 ghost score, a verdict (`likely real`, `suspicious`, `likely ghost`),
and the evidence behind each signal, so you can judge for yourself.

## Install & run

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone <this repo> && cd ghostcheck
uv run ghostcheck https://job-boards.greenhouse.io/acme/jobs/123456
```

```
Account Executive @ Acme
ghost score: 41/100  ->  suspicious

    +6  age        posted 34 days ago
    ?   repost     no local history yet (re-check later to detect age/reposts)
   -15  liveness   posting is listed on greenhouse board 'acme'
    +0  duplicates 1 role(s) with this title among 645 open
    +5  quality    no salary range
   -3  domain     acme.com registered 2012-03-04 (14.5 years old; guessed from name)
   +10  company    1 layoff/hiring-freeze headline(s)
                   - Acme lays off 200 staff - Example News
                     https://news.google.com/rss/articles/...
```

Headlines behind the company signal are listed with links so you can read them and decide whether they apply.

Options: `--json` (machine-readable), `--offline` (skip network lookups beyond the page fetch),
`--no-history` (don't record the check).

### Batch mode

Pass a CSV instead of a URL. The link column is the first header containing `link` or `url`;
rows without a link are skipped. Output is sorted with the most ghost-like first.

```sh
uv run ghostcheck applications.csv
```

### As a library

```python
from ghostcheck import check

report = check("https://jobs.lever.co/acme/abc-123")
report.score, report.verdict
for s in report.signals:
    print(s.name, s.points, s.detail)
```

## How it scores

The score starts at a prior of 30. Each signal adds or subtracts points; a signal that can't be
evaluated (shown as `?`) contributes nothing. The result is clamped to 0-100.
60+ is `likely ghost`, 35-59 is `suspicious`, below 35 is `likely real`.

| Signal | What it checks | Source |
|---|---|---|
| age | Posted date and expiry | schema.org `JobPosting` JSON-LD, or the ATS API |
| repost | First time you saw the role, and whether it appears under several links | local SQLite history |
| liveness | Is the role still listed on the company's own board | Greenhouse, Lever and Ashby public APIs. For LinkedIn/Indeed-style links it searches the company's board by name |
| duplicates | Many open roles with the identical title | ATS board listing |
| quality | No salary, talent-pipeline/evergreen wording, buzzwords, thin text | heuristics on the description |
| domain | How old the company website is. Under 90 days is a strong red flag, under a year a mild one | RDAP (the JSON successor to WHOIS, via rdap.org). The site comes from the posting data, then the job link, then a guess from the company name checked against that site's homepage |
| company | Recent layoff or hiring-freeze headlines naming the company | Google News RSS (last 180 days) |

History lives in `~/.local/share/ghostcheck/history.db` (respects `XDG_DATA_HOME`). The
`repost` signal gets better the more you re-check the same postings over time.

## Limitations

- Scores are heuristics, not proof. The weights are hand-picked and untuned.
- LinkedIn, Indeed and similar sites block scraping. For those links, ghostcheck relies on
  matching the company name to a Greenhouse/Lever/Ashby board, which fails for companies using other systems.
- Age is not proof: big companies keep roles open for months. Age is the first-published date (Greenhouse, Lever, Ashby) or `datePosted`; the last-updated date is shown for context but not scored.
- Domain age is weak evidence: domains get bought and companies rebrand (anthropic.com dates to 2001), so an old domain only subtracts a few points. Some country TLDs have no RDAP data, and for LinkedIn/Indeed links with no company website the domain is skipped.
- The news check matches headlines by pattern and can miss or mislabel stories.
- It makes requests to the job site, ATS APIs and Google News from your machine. Be considerate with large batches.

## Development

```sh
uv run pytest
```

Scoring lives in `src/ghostcheck/signals.py` as pure functions with no network access, so adding or
re-weighting a signal is easy to test. Network code is in `ats.py`, `news.py` and `http.py`.

## License

MIT
