"""Every relative link in the repository's markdown points at a file that exists."""

from __future__ import annotations

import re
import subprocess

import pytest
from conftest import ROOT

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
EXTERNAL = ("http://", "https://", "mailto:")


def markdown_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return out.split()


def relative_links(text: str) -> list[str]:
    links: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            links += [t for t in LINK.findall(line) if not t.startswith(EXTERNAL)]
    return links


@pytest.mark.parametrize("name", markdown_files())
def test_relative_links_resolve(name) -> None:
    path = ROOT / name
    missing = [t for t in relative_links(path.read_text()) if not (path.parent / t).exists()]

    assert missing == []


def test_links_inside_code_fences_and_external_urls_are_ignored() -> None:
    text = "[a](x.md)\n```\n[b](y.md)\n```\n[c](https://example.com/z)\n"

    assert relative_links(text) == ["x.md"]
