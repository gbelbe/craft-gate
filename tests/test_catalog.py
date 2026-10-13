"""catalog.yaml and CRAFTSMANSHIP.md agree on which entries exist.

The tables are generated, so they cannot drift; the principle and workflow entries are prose
written by hand, and nothing else checks that they were written.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest
import yaml
from conftest import ROOT

CODE = re.compile(r"\bCG\d{3}\b")
CATALOG = yaml.safe_load((ROOT / "catalog.yaml").read_text())
DOC = (ROOT / "CRAFTSMANSHIP.md").read_text()


def test_every_entry_has_a_unique_code() -> None:
    counts = Counter(entry["code"] for entry in CATALOG)

    assert [code for code, n in counts.items() if n > 1] == []


@pytest.mark.parametrize("entry", CATALOG, ids=lambda e: e["code"])
def test_each_entry_code_appears_in_the_doc(entry) -> None:
    assert entry["code"] in DOC, f"{entry['id']} ({entry['kind']}) is missing from CRAFTSMANSHIP.md"


def test_the_doc_cites_no_code_the_catalog_lacks() -> None:
    known = {entry["code"] for entry in CATALOG}

    assert sorted(set(CODE.findall(DOC)) - known) == []
