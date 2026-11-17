"""check_knowledge.py: each rule catches the drift it exists for, and this repo's bundle holds."""

from __future__ import annotations

import posixpath

import check_knowledge as knowledge
import pytest
import yaml
from conftest import ROOT

SCRIPTS = "scripts"
ALPHA, BETA = "/g/alpha.md", "/g/beta.md"
HUB = "/g/index.md"
ALPHA_CODE, BETA_CODE = "scripts/alpha.py", "scripts/beta.py"
TYPE_GATE = "Gate"
FORMAT, LINKS, IMPORTS = "format", "links", "imports"
INSTALLER = "bootstrap.sh"
LAYOUT = f"covered: [scripts]\ninstaller: {INSTALLER}\nimport-roots: [scripts]\n"


def concept(code: str | None, relations: dict[str, list[str]] | None = None, text: str = "") -> str:
    lines = ["---", f"type: {TYPE_GATE}"]
    if code:
        lines += ["code:", f"- {code}"]
    for kind, targets in (relations or {}).items():
        lines += ["relations:", f"  {kind}:", *(f"  - {t}" for t in targets)]
    return "\n".join([*lines, "---", text, ""])


def link(target: str, start: str = "/g") -> str:
    return f"[x]({posixpath.relpath(target, start)})"


@pytest.fixture
def project(tmp_path):
    """A repo with two scripts (alpha imports beta), an installer, and an empty bundle."""
    (tmp_path / SCRIPTS).mkdir()
    (tmp_path / ALPHA_CODE).write_text("import beta\n")
    (tmp_path / BETA_CODE).write_text("")
    (tmp_path / INSTALLER).write_text(f"{ALPHA_CODE}\n")
    (tmp_path / knowledge.DOCS / "g").mkdir(parents=True)
    (tmp_path / knowledge.DOCS / knowledge.CONFIG).write_text(LAYOUT)
    return tmp_path


def write(project, path: str, text: str) -> None:
    (project / knowledge.DOCS / path.lstrip("/")).write_text(text)


def faithful(project, alpha: str | None = None) -> None:
    write(project, ALPHA, alpha or concept(ALPHA_CODE))
    write(project, BETA, concept(BETA_CODE))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)}\n")


def test_a_faithful_bundle_has_no_problem(project) -> None:
    faithful(project)

    assert knowledge.problems_in(project) == []


def test_parse_reads_the_frontmatter_and_the_links_of_the_text() -> None:
    text = concept(ALPHA_CODE, {IMPORTS: [BETA]}, text=f"See {link(BETA)}.")

    doc = knowledge.parse(text, ALPHA)

    assert doc.code == (ALPHA_CODE,)
    assert doc.relations == {IMPORTS: (BETA,)}
    assert doc.links == {BETA}
    assert doc.targets == {BETA}


def test_a_link_is_read_relative_to_its_file_and_an_external_one_is_not_a_link() -> None:
    text = "[a](../t/x.md) [b](y.md) [c](https://example.com/z.md)"

    assert knowledge.parse(text, "/g/a.md").links == {"/t/x.md", "/g/y.md"}


def test_parse_ignores_links_in_fenced_examples_and_reads_a_file_with_no_frontmatter() -> None:
    doc = knowledge.parse(f"```\n{link(BETA)}\n```\n", HUB)

    assert doc.meta == {}
    assert doc.links == frozenset()


def test_only_index_files_are_not_concepts() -> None:
    assert knowledge.parse("", HUB).is_concept is False
    assert knowledge.parse("", ALPHA).is_concept is True


def test_a_concept_without_a_type_is_reported(project) -> None:
    faithful(project)
    write(project, ALPHA, "---\ncode:\n- scripts/alpha.py\n---\n")

    assert knowledge.problems_in(project) == [f"{FORMAT}: {ALPHA} has no type"]


def test_frontmatter_that_is_not_valid_yaml_is_reported_not_raised(project) -> None:
    faithful(project)
    write(project, ALPHA, "---\ntype: Gate\ndescription: a: b\n---\n")

    assert knowledge.problems_in(project) == [
        f"{FORMAT}: {ALPHA} has frontmatter that is not valid YAML",
        "coverage: scripts/alpha.py belongs to no concept",  # its `code` could not be read
    ]


def test_a_concept_with_the_placeholder_description_is_reported(project) -> None:
    faithful(project)
    write(
        project,
        ALPHA,
        concept(ALPHA_CODE).replace("---\n\n", f"description: {knowledge.PLACEHOLDER!r}\n---\n\n"),
    )

    assert knowledge.problems_in(project) == [
        f"todo: {ALPHA} still has the placeholder description"
    ]


def test_an_unknown_relation_is_reported(project) -> None:
    faithful(project, concept(ALPHA_CODE, {"befriends": [BETA]}, text=link(BETA)))

    assert knowledge.problems_in(project) == [
        f"{FORMAT}: {ALPHA} uses the unknown relation 'befriends'"
    ]


def test_relations_that_are_not_a_mapping_are_reported(project) -> None:
    faithful(project)
    write(project, ALPHA, f"---\ntype: {TYPE_GATE}\ncode:\n- {ALPHA_CODE}\nrelations: [x]\n---\n")

    assert knowledge.problems_in(project) == [
        f"{FORMAT}: {ALPHA} relations must map a relation to a list"
    ]


def test_an_anchor_to_a_missing_path_is_reported(project) -> None:
    faithful(project)
    write(project, "/g/gone.md", concept("scripts/gone.py"))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link('/g/gone.md')}\n")

    assert knowledge.problems_in(project) == [
        "anchor: /g/gone.md points at scripts/gone.py, which does not exist"
    ]


def test_a_file_no_concept_owns_is_reported(project) -> None:
    faithful(project)
    (project / SCRIPTS / "new.py").write_text("")

    assert knowledge.problems_in(project) == ["coverage: scripts/new.py belongs to no concept"]


def test_a_directory_in_code_owns_the_files_below_it(project) -> None:
    faithful(project)
    (project / SCRIPTS / "pkg").mkdir()
    (project / SCRIPTS / "pkg" / "mod.py").write_text("")
    write(project, "/g/pkg.md", concept("scripts/pkg"))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link('/g/pkg.md')}\n")

    assert knowledge.problems_in(project) == []


def test_a_link_to_a_missing_file_is_reported(project) -> None:
    faithful(project)
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link('/g/nowhere.md')}\n")

    assert knowledge.problems_in(project) == [
        f"{LINKS}: {HUB} links to /g/nowhere.md, which does not exist"
    ]


def test_a_concept_nothing_links_to_is_reported(project) -> None:
    faithful(project)
    write(project, HUB, f"{link(ALPHA)}\n")

    assert knowledge.problems_in(project) == [f"{LINKS}: {BETA} is linked from nowhere"]


def test_a_concept_that_only_links_to_itself_is_still_an_orphan(project) -> None:
    faithful(project)
    write(project, BETA, concept(BETA_CODE, text=link(BETA)))
    write(project, HUB, f"{link(ALPHA)}\n")

    assert knowledge.problems_in(project) == [f"{LINKS}: {BETA} is linked from nowhere"]


def test_a_relation_the_text_never_links_to_is_reported(project) -> None:
    faithful(project, concept(ALPHA_CODE, {IMPORTS: [BETA]}))

    assert knowledge.problems_in(project) == [
        f"prose: {ALPHA} declares imports {BETA} but its text never links to it"
    ]


def test_a_true_imports_relation_passes_and_a_false_one_is_reported(project) -> None:
    faithful(project, concept(ALPHA_CODE, {IMPORTS: [BETA]}, text=link(BETA)))
    assert knowledge.problems_in(project) == []

    faithful(project, concept(ALPHA_CODE))
    write(project, BETA, concept(BETA_CODE, {IMPORTS: [ALPHA]}, text=link(ALPHA)))
    assert knowledge.problems_in(project) == [f"{IMPORTS}: {BETA} does not import {ALPHA}"]


def test_an_installs_relation_must_name_something_the_installer_lists(project) -> None:
    boot = "/g/boot.md"
    faithful(project)
    write(project, boot, concept(None, {"installs": [ALPHA, BETA]}, text=link(ALPHA) + link(BETA)))
    write(project, HUB, f"{link(ALPHA)} {link(BETA)} {link(boot)}\n")

    assert knowledge.problems_in(project) == [
        f"installs: {INSTALLER} does not list {BETA} (from {boot})"
    ]


def test_main_exits_one_and_prints_each_problem(project, capsys) -> None:
    faithful(project)
    (project / SCRIPTS / "new.py").write_text("")

    assert knowledge.main(["--path", str(project)]) == 1
    assert "✗ coverage: scripts/new.py belongs to no concept" in capsys.readouterr().err


def test_main_exits_zero_when_faithful(project, capsys) -> None:
    faithful(project)

    assert knowledge.main(["--path", str(project)]) == 0
    assert "✓" in capsys.readouterr().out


def test_this_repos_own_bundle_matches_the_repo() -> None:
    assert knowledge.problems_in(ROOT) == []


CHECK_COMMAND = "python3 scripts/check_knowledge.py"
SYNC_COMMAND = "python3 scripts/sync_knowledge.py --check"
TOUCH_COMMAND = "python3 scripts/check_knowledge_touch.py"
WORKFLOW = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())


def steps_of(job: dict) -> list[dict]:
    return job["steps"]


def runs_of(job: dict) -> list[str]:
    return [step["run"] for step in steps_of(job) if "run" in step]


def test_ci_runs_the_checker_in_this_repo() -> None:
    runs = [run for job in WORKFLOW["jobs"].values() for run in runs_of(job)]

    assert CHECK_COMMAND in runs


def test_ci_checks_that_the_relations_are_in_sync() -> None:
    runs = [run for job in WORKFLOW["jobs"].values() for run in runs_of(job)]

    assert SYNC_COMMAND in runs


def test_the_agents_guidance_lists_both_commands_among_those_to_run_before_a_commit() -> None:
    guidance = (ROOT / "AGENTS.md").read_text()

    assert CHECK_COMMAND in guidance
    assert SYNC_COMMAND in guidance


def test_ci_warns_on_a_modified_file_whose_page_was_not_touched_and_only_for_pull_requests() -> (
    None
):
    job = WORKFLOW["jobs"]["knowledge-touch"]
    (run,) = runs_of(job)

    assert run.startswith(TOUCH_COMMAND)
    assert "--warn-only" in run
    assert "github.base_ref" in run
    assert "pull_request" in job["if"]
    assert {"fetch-depth": 0} in [step.get("with") for step in steps_of(job)]


def test_the_agents_guidance_tells_the_author_to_update_the_page_or_say_why_not() -> None:
    guidance = (ROOT / "AGENTS.md").read_text()

    assert TOUCH_COMMAND in guidance
    assert "Docs-Exempt:" in guidance
    assert "Before you propose or design a change, read `docs/knowledge/index.md`" in guidance


DOMAIN, ADAPTERS = "/s/domain.md", "/s/adapters.md"
NOT_IMPORTED = f"{IMPORTS}: {ADAPTERS} does not import {DOMAIN}"
SCRIPT_ROOTS = (SCRIPTS, "tools")


@pytest.fixture
def packages(tmp_path):
    """A package repo: adapters import domain, rooted at the repo, with a layout file."""
    for folder in ("shop/domain", "shop/adapters"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "__init__.py").write_text("")
    (tmp_path / "shop/domain/rules.py").write_text("")
    (tmp_path / "shop/adapters/db.py").write_text("from shop.domain import rules\n")
    base = tmp_path / knowledge.DOCS
    (base / "s").mkdir(parents=True)
    (base / knowledge.CONFIG).write_text("covered: [shop]\n")
    (base / "s/domain.md").write_text(concept("shop/domain"))
    (base / "s/adapters.md").write_text(
        concept("shop/adapters", {IMPORTS: [DOMAIN]}, link(DOMAIN, "/s"))
    )
    (base / "s/index.md").write_text(f"{link(DOMAIN, '/s')} {link(ADAPTERS, '/s')}\n")
    return tmp_path


def rewrite_db(packages, code: str) -> None:
    (packages / "shop/adapters/db.py").write_text(code)


def test_a_folder_concept_imports_another_when_a_module_below_it_does(packages) -> None:
    assert knowledge.problems_in(packages) == []


@pytest.mark.parametrize(
    "code",
    [
        "import shop.domain.rules\n",
        "from shop.domain.rules import x\n",
        "from shop import domain\n",
    ],
)
def test_each_way_to_import_a_module_counts(packages, code) -> None:
    rewrite_db(packages, code)

    assert knowledge.problems_in(packages) == []


def test_a_relative_import_is_resolved_against_the_package(packages) -> None:
    rewrite_db(packages, "from ..domain import rules\n")

    assert knowledge.problems_in(packages) == []


def test_an_import_of_something_else_does_not_count(packages) -> None:
    rewrite_db(packages, "import os\nfrom shop.adapters import db\nfrom . import db\n")

    assert knowledge.problems_in(packages) == [NOT_IMPORTED]


def test_a_relative_import_that_climbs_above_the_root_reaches_nothing(packages) -> None:
    rewrite_db(packages, "from ...... import domain\n")

    assert knowledge.problems_in(packages) == [NOT_IMPORTED]


def test_without_a_layout_file_nothing_has_to_be_covered_and_installs_are_not_checked(
    project,
) -> None:
    faithful(project)
    (project / knowledge.DOCS / knowledge.CONFIG).unlink()
    (project / SCRIPTS / "new.py").write_text("")

    assert knowledge.load_layout(project) == knowledge.Layout()
    assert knowledge.problems_in(project) == []


def test_a_layout_key_nothing_reads_and_a_layout_that_is_not_yaml_are_reported(project) -> None:
    faithful(project)
    path = project / knowledge.DOCS / knowledge.CONFIG

    path.write_text(LAYOUT + "colour: red\n")
    assert knowledge.problems_in(project) == [f"{FORMAT}: bundle.yaml has the unknown key 'colour'"]

    path.write_text("covered: [a: b\n")
    assert knowledge.problems_in(project) == [f"{FORMAT}: bundle.yaml is not valid YAML"]
    assert knowledge.load_layout(project) == knowledge.Layout()


def test_a_relation_the_layout_names_is_allowed_and_not_verified(project) -> None:
    faithful(project, concept(ALPHA_CODE, {"owns": [BETA]}, text=link(BETA)))
    assert knowledge.problems_in(project) == [f"{FORMAT}: {ALPHA} uses the unknown relation 'owns'"]

    path = project / knowledge.DOCS / knowledge.CONFIG
    path.write_text(LAYOUT + "relations: [owns]\n")
    assert knowledge.problems_in(project) == []


@pytest.mark.parametrize(
    ("path", "roots", "name"),
    [
        ("scripts/a.py", SCRIPT_ROOTS, "a"),
        ("tools/a.py", SCRIPT_ROOTS, "a"),
        ("shop/domain/__init__.py", (".",), "shop.domain"),
        ("shop/domain/rules.py", (".",), "shop.domain.rules"),
        ("docs/a.py", (SCRIPTS,), None),
        ("__init__.py", (".",), None),
    ],
)
def test_a_file_is_named_by_the_import_root_that_holds_it(path, roots, name) -> None:
    assert knowledge.module_name(path, roots) == name


def test_the_features_folder_defaults_to_tests_features_and_the_layout_can_move_it(project) -> None:
    faithful(project)
    path = project / knowledge.DOCS / knowledge.CONFIG

    assert knowledge.load_layout(project).features == "tests/features"

    path.write_text(LAYOUT + "features: spec\n")
    assert knowledge.load_layout(project).features == "spec"
    assert knowledge.problems_in(project) == []

    path.write_text(LAYOUT + "features: 3\n")
    assert knowledge.load_layout(project).features == "tests/features"


def test_pages_per_file_is_the_default_and_only_child_changes_it(project) -> None:
    faithful(project)
    path = project / knowledge.DOCS / knowledge.CONFIG

    assert knowledge.load_layout(project).pages == "file"
    path.write_text(LAYOUT + "pages: child\n")
    assert knowledge.load_layout(project).pages == "child"
    path.write_text(LAYOUT + "pages: folder\n")
    assert knowledge.load_layout(project).pages == "file"
    assert knowledge.problems_in(project) == []
