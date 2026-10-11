from __future__ import annotations

import argparse
import csv
import json
import sys

from .core import check
from .history import History


def _csv_urls(path: str) -> list[tuple[str, str]]:
    """(label, url) for each row with a link; the link column is the first header containing 'link' or 'url'."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    cols = list(rows[0])
    link = next((c for c in cols if any(k in c.lower() for k in ("link", "url"))), None)
    if link is None:
        raise SystemExit(f"{path}: no column with 'link' or 'url' in its header")
    label = next((c for c in cols if c != link), link)
    name = lambda r: " / ".join(filter(None, (r.get(cols[0]), r.get(cols[1]) if len(cols) > 1 else "")))
    return [(name(r) or r.get(label, ""), r[link].strip()) for r in rows if (r.get(link) or "").strip()]


def _batch(path: str, a) -> int:
    hist = None if a.no_history else History()
    out = []
    for label, url in _csv_urls(path):
        try:
            r = check(url, offline=a.offline, history=hist)
            out.append((label, url, r))
        except Exception as e:  # one bad row shouldn't stop the batch
            print(f"skip {label}: {e}", file=sys.stderr)
    out.sort(key=lambda t: -t[2].score)
    if a.json:
        print(json.dumps([{"label": l, "url": u, **r.to_dict()} for l, u, r in out], default=str, indent=2))
        return 0
    for label, url, r in out:
        known = [s for s in r.signals if s.points is not None]
        top = max(known, key=lambda s: abs(s.points), default=None)
        why = f"{top.name}: {top.detail}" if top else "no signals"
        print(f"{r.score:3d}  {r.verdict:<12} {label[:42]:<42} {why[:70]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ghostcheck", description="Estimate whether a job posting is a ghost job.")
    ap.add_argument("url", help="job posting URL, or a .csv file with a link column")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--offline", action="store_true", help="skip ATS and news lookups")
    ap.add_argument("--no-history", action="store_true", help="don't record this check locally")
    a = ap.parse_args(argv)

    if a.url.lower().endswith(".csv"):
        return _batch(a.url, a)

    r = check(a.url, offline=a.offline, history=None if a.no_history else History())
    if a.json:
        print(json.dumps(r.to_dict(), default=str, indent=2))
        return 0

    p = r.posting
    print(f"{p.title or '(untitled)'} @ {p.company or '(unknown company)'}")
    print(f"ghost score: {r.score}/100  ->  {r.verdict}\n")
    for s in r.signals:
        pts = "  ?  " if s.points is None else f"{s.points:+d}".rjust(5)
        print(f"  {pts}  {s.name:<10} {s.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
