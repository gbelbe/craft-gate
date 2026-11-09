"""render_architecture.py: architecture.yaml in, import-linter contracts out."""

from __future__ import annotations

import pytest
import render_architecture as arch

ROOT, LAYERS, PATH, CHECK = "root_package", "layers", "--path", "--check"
MINIMAL = {ROOT: "shop", LAYERS: ["adapters", "application", "domain"]}


def with_(**extra) -> dict:
    return {**MINIMAL, **extra}


# -- validate ---------------------------------------------------------------------


def test_a_minimal_declaration_is_valid() -> None:
    arch.validate(MINIMAL)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({LAYERS: ["a"]}, "'root_package' is required"),
        ({ROOT: 3, LAYERS: ["a"]}, "'root_package' is required"),
        ({ROOT: "s"}, "'layers' must name at least one layer"),
        ({ROOT: "s", LAYERS: []}, "'layers' must name at least one layer"),
        ({ROOT: "s", LAYERS: ["a", "a"]}, "'layers' lists a layer twice"),
        ({ROOT: "s", LAYERS: "a"}, "'layers' must be a list of names"),
        ({ROOT: "s", LAYERS: [1]}, "'layers' must be a list of names"),
        (
            {ROOT: "s", LAYERS: ["a"], "independent": ["other.x"]},
            "'independent' module 'other.x' is not under 's'",
        ),
        (
            {ROOT: "s", LAYERS: ["a"], "shared": "u"},
            "'shared' must be a list of names",
        ),
        (
            {ROOT: "s", LAYERS: ["a"], "known_violations": [1]},
            "'known_violations' must be a list of names",
        ),
    ],
)
def test_an_incoherent_declaration_is_refused_with_the_reason(data, message) -> None:
    with pytest.raises(arch.ArchitectureError) as error:
        arch.validate(data)

    assert str(error.value) == message


# -- render -----------------------------------------------------------------------


def test_the_layers_contract_lists_layers_outermost_first_and_is_exhaustive() -> None:
    text = arch.render(MINIMAL)

    assert "root_package = shop\n" in text
    assert "containers = shop\n" in text
    assert "layers =\n    adapters\n    application\n    domain\n" in text
    assert "exhaustive = true\n" in text
    assert text.startswith(arch.HEADER)


def test_without_optional_sections_no_empty_options_are_written() -> None:
    text = arch.render(MINIMAL)

    for option in ("exhaustive_ignores", "ignore_imports", "independence"):
        assert option not in text


def test_shared_modules_become_exhaustive_ignores() -> None:
    assert "exhaustive_ignores =\n    utils\n" in arch.render(with_(shared=["utils"]))


def test_known_violations_become_ignored_imports() -> None:
    text = arch.render(with_(known_violations=["shop.domain.a -> shop.adapters.b"]))

    assert "ignore_imports =\n    shop.domain.a -> shop.adapters.b\n" in text


def test_independent_adapters_get_their_own_contract() -> None:
    text = arch.render(with_(independent=["shop.adapters.web", "shop.adapters.db"]))

    assert "[importlinter:contract:independence]\n" in text
    assert "type = independence\n" in text
    assert "modules =\n    shop.adapters.web\n    shop.adapters.db\n" in text


def test_render_refuses_an_invalid_declaration() -> None:
    with pytest.raises(arch.ArchitectureError):
        arch.render({})


# -- load and the command line ----------------------------------------------------


def test_loading_a_missing_file_says_which_one(tmp_path) -> None:
    with pytest.raises(arch.ArchitectureError) as error:
        arch.load(tmp_path / arch.SOURCE)

    assert str(error.value).endswith("architecture.yaml not found")


def test_an_empty_file_loads_as_an_empty_declaration(tmp_path) -> None:
    (tmp_path / arch.SOURCE).write_text("")

    assert arch.load(tmp_path / arch.SOURCE) == {}


def write_source(root, text: str = f"{ROOT}: shop\n{LAYERS}: [adapters, domain]\n") -> None:
    (root / arch.SOURCE).write_text(text)


def test_main_writes_the_contracts_file(tmp_path, capsys) -> None:
    write_source(tmp_path)

    assert arch.main([PATH, str(tmp_path)]) == 0

    assert (tmp_path / arch.TARGET).read_text() == arch.render(arch.load(tmp_path / arch.SOURCE))
    assert capsys.readouterr().out == "✓ wrote .importlinter\n"


def test_check_passes_when_the_file_is_current(tmp_path, capsys) -> None:
    write_source(tmp_path)
    arch.main([PATH, str(tmp_path)])
    capsys.readouterr()

    assert arch.main([PATH, str(tmp_path), CHECK]) == 0
    assert capsys.readouterr().out == "✓ .importlinter matches architecture.yaml\n"


def test_check_fails_when_the_declaration_moved_on(tmp_path, capsys) -> None:
    write_source(tmp_path)
    arch.main([PATH, str(tmp_path)])
    write_source(tmp_path, "root_package: shop\nlayers: [adapters, application, domain]\n")
    capsys.readouterr()

    assert arch.main([PATH, str(tmp_path), CHECK]) == 1
    assert "out of date" in capsys.readouterr().out


def test_check_fails_when_the_file_was_never_generated(tmp_path) -> None:
    write_source(tmp_path)

    assert arch.main([PATH, str(tmp_path), CHECK]) == 1


def test_main_reports_a_bad_declaration_and_exits_2(tmp_path, capsys) -> None:
    write_source(tmp_path, "layers: [a]\n")

    assert arch.main([PATH, str(tmp_path)]) == arch.ERROR_EXIT
    assert capsys.readouterr().err == "✗ 'root_package' is required\n"
