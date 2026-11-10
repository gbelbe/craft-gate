"""architecture_docs.py: the layers table, the two diagrams, and the import counts."""

from __future__ import annotations

import architecture_docs as docs
import grimp
import pytest

ADAPTERS, APPLICATION, DOMAIN, UTILS = "adapters", "application", "domain", "utils"
LAYERS = [ADAPTERS, APPLICATION, DOMAIN]
DATA = {"root_package": "shop", "layers": LAYERS, "shared": [UTILS], "docs": "docs/architecture"}


# -- layer_of ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module", "layer"),
    [
        ("shop.domain", DOMAIN),
        ("shop.domain.model", DOMAIN),
        ("shop.utils.text", UTILS),
        ("shop.domainx", None),
        ("shop.other", None),
        ("shop", None),
        ("requests.api", None),
    ],
)
def test_a_module_belongs_to_the_layer_whose_package_contains_it(module, layer) -> None:
    assert docs.layer_of(module, DATA) == layer


def test_layer_of_works_without_shared_modules() -> None:
    assert docs.layer_of("shop.domain", {"root_package": "shop", "layers": LAYERS}) == DOMAIN


# -- points_outward ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "target", "outward"),
    [
        (DOMAIN, ADAPTERS, True),
        (DOMAIN, APPLICATION, True),
        (APPLICATION, ADAPTERS, True),
        (ADAPTERS, DOMAIN, False),
        (APPLICATION, DOMAIN, False),
        (DOMAIN, UTILS, False),
        (UTILS, ADAPTERS, False),
    ],
)
def test_only_an_import_of_a_layer_stacked_above_points_outward(source, target, outward) -> None:
    assert docs.points_outward(source, target, LAYERS) is outward


# -- layer_edges (a real grimp graph) ---------------------------------------------


def package(root, files: dict[str, str]) -> None:
    for rel, text in {"shop/__init__.py": "", **files}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def test_edges_count_imports_between_layers_and_ignore_the_rest(tmp_path) -> None:
    package(
        tmp_path,
        {
            "shop/adapters/__init__.py": "",
            "shop/adapters/web.py": (
                "from shop.application import a\nfrom shop.application import b\nimport os\n"
            ),
            "shop/application/__init__.py": "",
            "shop/application/a.py": "from shop.domain import m\nfrom shop.application import b\n",
            "shop/application/b.py": "",
            "shop/domain/__init__.py": "",
            "shop/domain/m.py": "from shop.utils import u\n",
            "shop/utils/__init__.py": "",
            "shop/utils/u.py": "",
        },
    )

    edges = docs.layer_edges(docs.build_graph(DATA, tmp_path), DATA)

    assert edges == {
        (ADAPTERS, APPLICATION): 2,
        (APPLICATION, DOMAIN): 1,
        (DOMAIN, UTILS): 1,
    }


def test_build_graph_honours_the_source_root_and_leaves_no_cache(tmp_path, monkeypatch) -> None:
    package(tmp_path / "src", {"shop/mod.py": ""})
    monkeypatch.chdir(tmp_path)

    graph = docs.build_graph({**DATA, "source_root": "src"}, tmp_path)

    assert isinstance(graph, grimp.ImportGraph)
    assert "shop.mod" in graph.modules
    assert not (tmp_path / ".grimp_cache").exists()


# -- render_overview --------------------------------------------------------------


def test_the_overview_declares_the_stack_and_a_purpose_per_layer() -> None:
    text = docs.render_overview({**DATA, "purposes": {DOMAIN: "business rules"}}, {})

    assert text.startswith(docs.HEADER)
    assert "    adapters --> application --> domain\n" in text
    assert "| `shop.adapters` | - | `application`, `domain` |" in text
    assert "| `shop.application` | - | `domain` |" in text
    assert "| `shop.domain` | business rules | nothing |" in text


def test_the_overview_draws_inward_imports_solid_and_outward_ones_dashed() -> None:
    edges = {(ADAPTERS, DOMAIN): 3, (DOMAIN, ADAPTERS): 1}

    text = docs.render_overview(DATA, edges)

    assert "    adapters -->|3| domain\n" in text
    assert "    domain -.->|1 against the rule| adapters\n" in text


def test_the_overview_says_so_when_layers_do_not_import_each_other() -> None:
    assert "    none[no imports between layers]\n" in docs.render_overview(DATA, {})


def test_render_docs_keys_the_overview_by_its_path(tmp_path) -> None:
    package(tmp_path, {"shop/domain/__init__.py": ""})

    rendered = docs.render_docs(DATA, tmp_path)

    assert list(rendered) == ["docs/architecture/overview.md"]
