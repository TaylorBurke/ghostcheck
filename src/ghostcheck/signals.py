"""Pure scoring functions. Each returns a Signal; none do network I/O."""
from __future__ import annotations

import re
from datetime import date

from .ats import Liveness
from .models import Posting, Signal

_PIPELINE = re.compile(
    r"talent (pipeline|community|network|pool)|"
    r"(keep|retain|hold) (your )?(resume|application|cv) (on file|for future)|"
    r"evergreen|general application|ongoing recruit|continuously (hiring|accepting)|"
    r"we(?:'| a)re always (hiring|looking)|not (currently )?hiring for a specific",
    re.I,
)
_BUZZ = re.compile(
    r"fast[- ]paced|rockstar|ninja|wear many hats|dynamic environment|self[- ]starter|"
    r"passionate|synerg|competitive (salary|compensation)|team player",
    re.I,
)


def age(p: Posting, today: date) -> Signal:
    if p.valid_through and p.valid_through < today:
        return Signal("age", 25, f"listing expired on {p.valid_through}")
    if not p.date_posted:
        return Signal("age", None, "no posting date available")
    days = (today - p.date_posted).days
    if days > 90:
        return Signal("age", 25, f"posted {days} days ago")
    if days > 60:
        return Signal("age", 15, f"posted {days} days ago")
    if days > 30:
        return Signal("age", 6, f"posted {days} days ago")
    return Signal("age", -5, f"posted {days} days ago")


def reposts(first_seen: date | None, urls: int, today: date) -> Signal:
    if first_seen is None:
        return Signal("repost", None, "no local history yet (re-check later to detect age/reposts)")
    pts, notes = 0, []
    seen_days = (today - first_seen).days
    if seen_days > 45:
        pts += 15
        notes.append(f"first seen by you {seen_days} days ago")
    if urls > 1:
        pts += 10
        notes.append(f"same role seen under {urls} different links")
    return Signal("repost", pts, "; ".join(notes) or "no repost pattern in your history")


def liveness(lv: Liveness | None) -> Signal:
    if lv is None or lv.live is None:
        return Signal("liveness", None, lv.detail if lv else "no company board checked")
    if lv.live:
        return Signal("liveness", -15, lv.detail)
    return Signal("liveness", 30, lv.detail)


def duplicates(lv: Liveness | None) -> Signal:
    if lv is None or not lv.board_size:
        return Signal("duplicates", None, "board size unknown")
    if lv.open_same_title >= 3:
        return Signal("duplicates", 8, f"{lv.open_same_title} open roles with the same title")
    return Signal("duplicates", 0, f"{lv.open_same_title} role(s) with this title among {lv.board_size} open")


def quality(p: Posting) -> Signal:
    text = p.description
    if len(text) < 80:
        return Signal("quality", None, "description too short to judge")
    pts, notes = 0, []
    if not p.has_salary:
        pts += 5
        notes.append("no salary range")
    if m := _PIPELINE.search(text):
        pts += 20
        notes.append(f"pipeline language ('{m.group(0)}')")
    buzz = len(_BUZZ.findall(text))
    if buzz >= 3:
        pts += 6
        notes.append(f"{buzz} buzzwords")
    if len(text) < 600:
        pts += 4
        notes.append("very thin description")
    return Signal("quality", pts, "; ".join(notes) or "description looks specific")


def company(layoff_headlines: list[str] | None) -> Signal:
    if layoff_headlines is None:
        return Signal("company", None, "news lookup unavailable")
    if not layoff_headlines:
        return Signal("company", 0, "no recent layoff/hiring-freeze headlines")
    pts = min(5 + 5 * len(layoff_headlines), 15)
    return Signal("company", pts, f"{len(layoff_headlines)} headline(s), e.g. \"{layoff_headlines[0]}\"")


def verdict(score: int) -> str:
    if score >= 60:
        return "likely ghost"
    if score >= 35:
        return "suspicious"
    return "likely real"


def combine(signals: list[Signal]) -> int:
    """Base 30 (prior) plus signal points, clamped to 0-100. Unevaluated signals add nothing."""
    return max(0, min(100, 30 + sum(s.points for s in signals if s.points is not None)))
