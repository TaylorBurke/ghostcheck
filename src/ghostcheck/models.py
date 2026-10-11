from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class Posting:
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    date_posted: date | None = None
    valid_through: date | None = None
    last_updated: date | None = None  # informational only; not scored
    has_salary: bool = False


@dataclass
class Signal:
    name: str
    # Points added to the ghost score (positive = more ghost-like, negative = less).
    # `None` weight means the signal could not be evaluated.
    points: int | None
    detail: str
    # Supporting links as (label, url), e.g. the headlines behind a company signal.
    links: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Report:
    posting: Posting
    score: int
    verdict: str
    signals: list[Signal] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
