"""Every relative link in the repository's markdown points at a file that exists."""

from __future__ import annotations

import re
import subprocess

import pytest
from conftest import ROOT

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
EXTERNAL = ("http://", "https://", "mailto:")
BUNDLE = "docs/knowledge"  # an OKF bundle: links start at its root, `/gates/x.md`


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


def resolve(name: str, target: str):
    if name.startswith(BUNDLE + "/") and target.startswith("/"):
        return ROOT / BUNDLE / target.lstrip("/")
    return (ROOT / name).parent / target


@pytest.mark.parametrize("name", markdown_files())
def test_relative_links_resolve(name) -> None:
    missing = [
        t for t in relative_links((ROOT / name).read_text()) if not resolve(name, t).exists()
    ]

    assert missing == []


def test_links_inside_code_fences_and_external_urls_are_ignored() -> None:
    text = "[a](x.md)\n```\n[b](y.md)\n```\n[c](https://example.com/z)\n"

    assert relative_links(text) == ["x.md"]


def test_a_bundle_link_starts_at_the_bundle_root_and_any_other_leading_slash_is_absolute() -> None:
    assert resolve(f"{BUNDLE}/gates/a.md", "/tooling/b.md") == ROOT / BUNDLE / "tooling" / "b.md"
    assert resolve("README.md", "/x.md").as_posix() == "/x.md"
    assert resolve("docs/a.md", "b.md") == ROOT / "docs" / "b.md"
