"""The values that travel from the scan to the report."""

from __future__ import annotations

from dataclasses import dataclass

# Keys of the plain-dict shapes that are also the JSON on disk and on stdout
# (summary, snapshot, findings, catalog entries) — named once so modules agree.
TOTAL = "total"
BY_HEURISTIC = "by_heuristic"
HEURISTIC_ID = "heuristic_id"
CONFIDENCE = "confidence"


@dataclass
class Timing:
    """How much work this run did; serialized as the report's "timing" object."""

    total_files: int
    changed: int
    cached: int
    elapsed: float
    dupes_elapsed: float = 0.0


@dataclass
class ScanResults:
    """What the scan *found*. Split from RunContext on purpose, not just to
    satisfy extract-class (CG016): these are what got found, RunContext is
    how *this run* differs from the last one. Genuinely two concerns."""

    agg: dict
    by_file: dict[str, list[dict]]
    catalog: list[dict]

    @property
    def catalog_by_id(self) -> dict[str, dict]:
        return {e["id"]: e for e in self.catalog}


@dataclass
class RunContext:
    """How this run relates to the one before it — see ScanResults above."""

    timing: Timing
    prev_snapshot: dict | None
    diff_active: bool
    scope_label: str | None


@dataclass
class ReportOptions:
    """How the report should be rendered."""

    fmt: str = "text"
    verbose: bool = False
