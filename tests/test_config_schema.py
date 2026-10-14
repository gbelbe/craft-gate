"""craft-gate.toml: where the values come from, what is rejected, and that none is decorative."""

from __future__ import annotations

import re

import gate_config as cfg
import pytest
from conftest import ROOT

FEATURE = (ROOT / "tests" / "features" / "config_effects.feature").read_text()
COMPLEXITY, CYCLOMATIC, COGNITIVE = "complexity", "cyclomatic", "cognitive"
NINE, SEVEN, FIFTEEN = 9, 7, 15
NINE_TOML = f"[{COMPLEXITY}]\n{CYCLOMATIC} = {NINE}\n"
SCENARIO_KEYS = set(re.findall(r"@key:([\w.-]+)", FEATURE))
SCHEMA_KEYS = {f"{section}.{key}" for section, keys in cfg.DEFAULTS.items() for key in keys}


# -- no value without a scenario that proves it ------------------------------------------------


def test_every_value_in_the_schema_has_a_scenario_proving_it_changes_behaviour() -> None:
    assert sorted(SCHEMA_KEYS - SCENARIO_KEYS) == []


def test_no_scenario_claims_a_value_the_schema_does_not_have() -> None:
    assert sorted(SCENARIO_KEYS - SCHEMA_KEYS) == []


# -- where the values come from ----------------------------------------------------------------


def test_an_empty_repo_gets_every_default(tmp_path) -> None:
    settings = cfg.load_settings(tmp_path)

    assert settings == cfg.DEFAULTS
    assert settings[COMPLEXITY][CYCLOMATIC] == FIFTEEN


def test_craft_gate_toml_is_read(tmp_path) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text(NINE_TOML)

    assert cfg.load_settings(tmp_path)[COMPLEXITY][CYCLOMATIC] == NINE


def test_pyproject_is_the_fallback(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.craft-gate.{COMPLEXITY}]\n{COGNITIVE} = {SEVEN}\n"
    )

    assert cfg.load_settings(tmp_path)[COMPLEXITY][COGNITIVE] == SEVEN


def test_craft_gate_toml_wins_over_pyproject(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.craft-gate.{COMPLEXITY}]\n{CYCLOMATIC} = {SEVEN}\n"
    )
    (tmp_path / cfg.CONFIG_FILE).write_text(NINE_TOML)

    assert cfg.load_settings(tmp_path)[COMPLEXITY][CYCLOMATIC] == NINE


def test_a_value_not_given_keeps_its_default(tmp_path) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text(NINE_TOML)

    assert cfg.load_settings(tmp_path)[COMPLEXITY][COGNITIVE] == FIFTEEN


def test_find_root_walks_up_to_the_config(tmp_path) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text("")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)

    assert cfg.find_root(deep) == tmp_path.resolve()


# -- what is rejected --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("toml", "needle"),
    [
        (f"[{COMPLEXITY}]\n{CYCLOMATIC} = 0\n", CYCLOMATIC),
        (f"[{COMPLEXITY}]\n{CYCLOMATIC} = true\n", CYCLOMATIC),
        (f'[{COMPLEXITY}]\n{CYCLOMATIC} = "high"\n', CYCLOMATIC),
        ("[complexity]\nduplicated-literal-occurrences = 1\n", "duplicated-literal-occurrences"),
        ("[complexity]\ncyclometric = 9\n", "cyclometric"),
        ('[refactor-first]\nper-file = "decrease"\n', "per-file"),
        ("[design-review]\nmax-parameters = -1\n", "max-parameters"),
        ("[design-review]\nmax-lines = 0\n", "max-lines"),
        ('[exemptions]\nnew-code = "yes"\n', "new-code"),
        ("[exemptions]\nlegacy = true\n", "legacy"),
        (f"[{COMPLEXITY}.{CYCLOMATIC}]\nvalue = 3\n", CYCLOMATIC),
        ("[mystery]\nx = 1\n", "mystery"),
    ],
)
def test_a_bad_value_or_a_typo_is_an_error_naming_it(tmp_path, toml, needle) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text(toml)

    with pytest.raises(cfg.ConfigError, match=needle):
        cfg.load_settings(tmp_path)


def test_an_unparseable_file_is_an_error(tmp_path) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text("[complexity\n")

    with pytest.raises(cfg.ConfigError, match="craft-gate.toml does not parse"):
        cfg.load_settings(tmp_path)


def test_a_percentage_above_100_is_rejected(tmp_path) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text("[mutation]\nthreshold = 101\n")

    with pytest.raises(cfg.ConfigError, match="threshold"):
        cfg.load_settings(tmp_path)


def test_the_error_names_both_places_the_value_could_live(tmp_path) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text("[complexity]\ncyclomatic = 0\n")

    with pytest.raises(cfg.ConfigError) as caught:
        cfg.load_settings(tmp_path)

    assert "craft-gate.toml" in str(caught.value)
    assert "[tool.craft-gate.complexity]" in str(caught.value)


# -- what a Tidy-Exempt trailer waives, from the config ----------------------------------------


def test_without_a_trailer_nothing_is_waived() -> None:
    assert cfg.waive_from(cfg.DEFAULTS, exempt=False) == cfg.Waive(False, False)


def test_by_default_a_trailer_waives_the_debt_rules_only() -> None:
    assert cfg.waive_from(cfg.DEFAULTS, exempt=True) == cfg.Waive(legacy_debt=True, new_code=False)


def test_the_exemptions_section_decides_what_a_trailer_waives() -> None:
    settings = {cfg.EXEMPTIONS: {"legacy-debt": False, "new-code": True}}

    assert cfg.waive_from(settings, exempt=True) == cfg.Waive(legacy_debt=False, new_code=True)


# -- the sample file ships every value, at its default ---------------------------------------------


def test_the_sample_config_is_every_default_so_adding_it_changes_nothing(tmp_path) -> None:
    (tmp_path / cfg.CONFIG_FILE).write_text((ROOT / "templates" / cfg.CONFIG_FILE).read_text())

    assert cfg.load_settings(tmp_path) == cfg.DEFAULTS


def test_the_sample_config_mentions_every_key_so_it_cannot_fall_behind() -> None:
    text = (ROOT / "templates" / cfg.CONFIG_FILE).read_text()

    keys = [k.split(".")[1] for k in SCHEMA_KEYS]
    missing = [k for k in keys if not re.search(rf"^{k}\s*=", text, re.M)]
    assert missing == []
