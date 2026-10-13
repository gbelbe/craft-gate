"""next_version.py: which release a set of Conventional Commits earns."""

from __future__ import annotations

import pytest
from next_version import MAJOR, MINOR, PATCH, bump_level, next_version


@pytest.mark.parametrize(
    ("messages", "level"),
    [
        (["feat: x"], MINOR),
        (["fix: x"], PATCH),
        (["docs: x"], None),
        (["feat!: x"], MAJOR),
        (["fix: x\n\nBREAKING CHANGE: y"], MAJOR),
        (["feat: x", "fix: y"], MINOR),  # the highest wins
    ],
)
def test_bump_level(messages, level) -> None:
    assert bump_level(messages) == level


@pytest.mark.parametrize(
    ("current", "level", "expected"),
    [
        (None, MINOR, "0.1.0"),
        ("v0.1.0", MINOR, "0.2.0"),
        ("v0.1.0", PATCH, "0.1.1"),
        ("v0.9.0", MAJOR, "0.10.0"),  # 0.x stays 0.x
        ("v1.2.3", MAJOR, "2.0.0"),
    ],
)
def test_next_version(current, level, expected) -> None:
    assert next_version(current, level) == expected
