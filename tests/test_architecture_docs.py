"""architecture_docs.py: the layers table, the two diagrams, and the import counts."""

from __future__ import annotations

import architecture_docs as docs
import grimp
import pytest

ADAPTERS, APPLICATION, DOMAIN, UTILS = "adapters", "application", "domain", "utils"
ADAPTER_MODULE, DOMAIN_MODULE = "shop.adapters.a", "shop.domain.m"
ROOT_KEY, LAYERS_KEY = "root_package", "layers"
LAYERS = [ADAPTERS, APPLICATION, DOMAIN]
DATA = {ROOT_KEY: "shop", LAYERS_KEY: LAYERS, "shared": [UTILS], "docs": "docs/architecture"}


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

    imports = docs.cross_layer_imports(docs.build_graph(DATA, tmp_path), DATA)
    edges = docs.layer_edges(imports)

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
    text = docs.render_overview({**DATA, "purposes": {DOMAIN: "business rules"}}, [])

    assert text.startswith(docs.HEADER)
    assert "    adapters --> application --> domain\n" in text
    assert "| **adapters** | - | `shop.adapters` | `application`, `domain` |" in text
    assert "| **application** | - | `shop.application` | `domain` |" in text
    assert "| **domain** | business rules | `shop.domain` | nothing |" in text


def test_the_overview_draws_inward_imports_solid_and_outward_ones_dashed() -> None:
    imports = [docs.CrossImport(ADAPTER_MODULE, DOMAIN_MODULE, ADAPTERS, DOMAIN)] * 3
    imports.append(docs.CrossImport(DOMAIN_MODULE, ADAPTER_MODULE, DOMAIN, ADAPTERS))

    text = docs.render_overview(DATA, imports)

    assert "    adapters -->|3| domain\n" in text
    assert "    domain -.->|1 against the rule| adapters\n" in text


def test_the_overview_says_so_when_layers_do_not_import_each_other() -> None:
    assert "    none[no imports between layers]\n" in docs.render_overview(DATA, [])


def test_render_docs_keys_the_overview_by_its_path(tmp_path) -> None:
    package(tmp_path, {"shop/domain/__init__.py": ""})

    rendered = docs.render_docs(DATA, tmp_path)

    assert list(rendered) == ["docs/architecture/overview.md"]


def test_the_overview_lists_each_import_that_breaks_the_rule_by_module() -> None:
    imports = [docs.CrossImport(DOMAIN_MODULE, "shop.adapters.db", DOMAIN, ADAPTERS)]

    text = docs.render_overview(DATA, imports)

    assert "- `shop.domain.m` (domain) imports `shop.adapters.db` (adapters)\n" in text


def test_the_overview_says_none_when_every_import_points_inward() -> None:
    imports = [docs.CrossImport(ADAPTER_MODULE, DOMAIN_MODULE, ADAPTERS, DOMAIN)]

    text = docs.render_overview(DATA, imports)

    assert "None: every import between layers points inward." in text


# -- layers that own several modules ----------------------------------------------

MULTI = {
    ROOT_KEY: "shop",
    LAYERS_KEY: [{"name": "edge", "modules": ["cli", "api"]}, DOMAIN],
    "shared": [UTILS],
}


def test_a_layer_may_own_several_modules_and_a_bare_name_owns_the_module_of_that_name() -> None:
    assert docs.layer_modules(MULTI) == {"edge": ["cli", "api"], DOMAIN: [DOMAIN]}
    assert docs.layer_names(MULTI) == ["edge", DOMAIN]


@pytest.mark.parametrize(
    ("module", "layer"),
    [
        ("shop.cli", "edge"),
        ("shop.api.routes", "edge"),
        (DOMAIN_MODULE, DOMAIN),
        ("shop.utils", UTILS),
        ("shop.other", None),
    ],
)
def test_a_module_belongs_to_the_layer_that_owns_its_package(module, layer) -> None:
    assert docs.layer_of(module, MULTI) == layer


def test_the_table_lists_every_module_a_layer_owns() -> None:
    text = docs.render_overview(MULTI, [])

    assert "| **edge** | - | `shop.cli`, `shop.api` | `domain` |" in text
