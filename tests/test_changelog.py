"""CHANGELOG.md keeps its sections in order, so a release is never filed under the wrong one."""

from __future__ import annotations

import re

from conftest import ROOT

HEADINGS = re.findall(r"^## (.+)$", (ROOT / "CHANGELOG.md").read_text(), re.MULTILINE)
VERSION = re.compile(r"^v(\d+)\.(\d+)(?:\.(\d+))?")


def parse(heading: str) -> tuple[int, ...]:
    major, minor, patch = VERSION.match(heading).groups()
    return int(major), int(minor), int(patch or 0)


def test_unreleased_comes_first_when_it_is_there() -> None:
    assert "Unreleased" not in HEADINGS[1:]


def test_every_other_heading_is_a_version() -> None:
    assert all(VERSION.match(h) for h in HEADINGS if h != "Unreleased")


def test_versions_are_unique_and_newest_first() -> None:
    versions = [parse(h) for h in HEADINGS if h != "Unreleased" and "–" not in h.split(" — ")[0]]

    assert versions == sorted(set(versions), reverse=True)
