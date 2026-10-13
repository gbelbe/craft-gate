#!/usr/bin/env python3
"""craftCov — a coverage-report-style scan of the craftsmanship catalog.

The entry point (and import facade) for the `craftcov_core` package, which holds
the implementation and the full explanation of what is and isn't detected —
`python3 scripts/craftcov.py --help` prints it.

Usage:
    python3 scripts/craftcov.py                  # scan, text report
    python3 scripts/craftcov.py --format json     # machine-readable
    python3 scripts/craftcov.py --verbose         # + every finding, file:line
    python3 scripts/craftcov.py --no-cache        # ignore and overwrite the cache
    python3 scripts/craftcov.py --list-detectors  # which heuristics are detectable, and how
"""

from __future__ import annotations

import sys

from craftcov_core.adapters import run_pylint, run_ruff, run_vulture
from craftcov_core.cache import (
    CACHE_VERSION,
    load_cache,
    load_report_snapshot,
    save_cache,
    save_report_snapshot,
)
from craftcov_core.catalog import CATALOG_PATH, DetectorIndex, build_detector_index, load_catalog
from craftcov_core.cli import main
from craftcov_core.discovery import discover_python_files, file_hash, normalize_path
from craftcov_core.dupes import find_duplicate_blocks, run_dupes, strip_lines_for_dupes
from craftcov_core.models import Finding, ReportOptions, RunContext, ScanResults, Summary, Timing
from craftcov_core.pipeline import ScanSettings, restrict_to_file, scan_repository
from craftcov_core.render import (
    format_sarif,
    print_detector_list,
    print_report,
    print_text_report,
)
from craftcov_core.scan import merge_corpus_findings, scan_files
from craftcov_core.scopes import build_scope_index, enclosing_class
from craftcov_core.summary import aggregate, diff_by_heuristic

__all__ = [
    "CACHE_VERSION",
    "CATALOG_PATH",
    "DetectorIndex",
    "Finding",
    "ReportOptions",
    "RunContext",
    "ScanResults",
    "ScanSettings",
    "Summary",
    "Timing",
    "aggregate",
    "build_detector_index",
    "build_scope_index",
    "diff_by_heuristic",
    "discover_python_files",
    "enclosing_class",
    "file_hash",
    "find_duplicate_blocks",
    "format_sarif",
    "load_cache",
    "load_catalog",
    "load_report_snapshot",
    "main",
    "merge_corpus_findings",
    "normalize_path",
    "print_detector_list",
    "print_report",
    "print_text_report",
    "restrict_to_file",
    "run_dupes",
    "run_pylint",
    "run_ruff",
    "run_vulture",
    "save_cache",
    "save_report_snapshot",
    "scan_files",
    "scan_repository",
    "strip_lines_for_dupes",
]

if __name__ == "__main__":
    sys.exit(main())
