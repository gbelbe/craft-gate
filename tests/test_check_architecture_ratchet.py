"""check_architecture_ratchet.py: module names, breach counts, and which touched files owe one."""

from __future__ import annotations

import check_architecture_ratchet as gate
import pytest

BAD = "shop.domain.bad -> shop.adapters.db"
OTHER = "shop.domain.bad -> shop.adapters.web"
ELSEWHERE = "shop.domain.pricing -> shop.adapters.db"
BAD_PATH = "shop/domain/bad.py"
BAD_MODULE = "shop.domain.bad"
SRC_BAD_PATH = "src/shop/domain/bad.py"


def declared(*violations: str, **extra) -> dict:
    return {gate.KNOWN_KEY: list(violations), **extra}


@pytest.mark.parametrize(
    ("path", "root", "module"),
    [
        (BAD_PATH, ".", BAD_MODULE),
        ("shop/domain/__init__.py", ".", "shop.domain"),
        (SRC_BAD_PATH, "src", BAD_MODULE),
        ("tools/x.py", "src", None),
        ("__init__.py", ".", None),
    ],
)
def test_module_of(path: str, root: str, module: str | None) -> None:
    assert gate.module_of(path, root) == module


def test_breaches_are_counted_per_importing_module() -> None:
    counts = gate.breaches_by_importer(declared(BAD, OTHER, ELSEWHERE))

    assert counts == {BAD_MODULE: 2, "shop.domain.pricing": 1}


def test_a_declaration_without_a_baseline_owns_nothing() -> None:
    assert gate.breaches_by_importer({}) == {}
    assert gate.breaches_by_importer({gate.KNOWN_KEY: None}) == {}


def test_a_touched_file_that_kept_all_its_breaches_owes_one() -> None:
    both = declared(BAD, OTHER)

    assert gate.unpaid([(BAD_PATH, BAD_PATH)], both, both) == [(BAD_PATH, 2, 2)]


def test_losing_one_breach_is_enough() -> None:
    assert gate.unpaid([(BAD_PATH, BAD_PATH)], declared(BAD, OTHER), declared(OTHER)) == []


def test_swapping_a_breach_for_another_pays_nothing_down() -> None:
    assert gate.unpaid([(BAD_PATH, BAD_PATH)], declared(BAD), declared(OTHER)) == [(BAD_PATH, 1, 1)]


def test_a_file_that_owned_none_owes_nothing() -> None:
    assert (
        gate.unpaid(
            [("shop/domain/clean.py", "shop/domain/clean.py")], declared(BAD), declared(BAD)
        )
        == []
    )


def test_a_renamed_file_is_judged_by_its_old_and_its_new_module() -> None:
    moved = "shop/domain/moved.py"
    renamed = "shop.domain.moved -> shop.adapters.db"

    assert gate.unpaid([(BAD_PATH, moved)], declared(BAD), declared(renamed)) == [(moved, 1, 1)]
    assert gate.unpaid([(BAD_PATH, moved)], declared(BAD), declared()) == []


def test_each_end_uses_its_own_source_root() -> None:
    before = declared(BAD)
    after = declared(BAD, **{gate.SOURCE_ROOT_KEY: "src"})

    assert gate.unpaid([(BAD_PATH, SRC_BAD_PATH)], before, after) == [(SRC_BAD_PATH, 1, 1)]
