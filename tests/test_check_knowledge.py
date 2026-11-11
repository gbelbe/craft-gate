"""check_knowledge.py: each rule catches the drift it exists for, and this repo's documents hold."""

from __future__ import annotations

import check_knowledge as knowledge
import pytest
from conftest import ROOT

SCRIPTS = "scripts"
ALPHA_NAME = "Alpha"
MENTION_ALPHA = "[[Alpha]]\n"
DOC = "a.md"
OTHER_DOC = "b.md"
HEADER = "::config\ngate: rectangle, #2196F3, 100\n"
ALPHA = "Alpha: type=gate, path=scripts/alpha.py\n"
BETA = "Beta: type=gate, path=scripts/beta.py\n"


def document(*lines: str) -> str:
    return HEADER + "".join(lines) + "::\n"


@pytest.fixture
def project(tmp_path):
    """A repo with two scripts, an installer, and a docs/knowledge folder to fill."""
    (tmp_path / SCRIPTS).mkdir()
    (tmp_path / SCRIPTS / "alpha.py").write_text("import beta\n")
    (tmp_path / SCRIPTS / "beta.py").write_text("")
    (tmp_path / knowledge.INSTALLER).write_text("scripts/alpha.py\n")
    (tmp_path / knowledge.DOCS).mkdir(parents=True)
    return tmp_path


def write(project, name: str, text: str) -> None:
    (project / knowledge.DOCS / name).write_text(text)


def faithful(project) -> None:
    write(project, DOC, document(ALPHA, BETA) + "[[Alpha]] and [[Beta]].\n")


def test_a_faithful_project_has_no_problem(project) -> None:
    faithful(project)

    assert knowledge.problems_in(project) == []


def test_parse_reads_entities_edges_and_mentions_but_not_type_definitions() -> None:
    text = document(ALPHA) + "Prose [[Alpha]].\n::rel Alpha <- Beta [uses] ::\n"

    parsed = knowledge.parse(text, DOC)

    assert parsed.entities == [knowledge.Entity(ALPHA_NAME, DOC, ("scripts/alpha.py",))]
    assert parsed.edges == [knowledge.Edge("Beta", ALPHA_NAME, "uses", DOC)]
    assert parsed.mentions == {ALPHA_NAME}


def test_parse_skips_fenced_examples_of_the_syntax() -> None:
    text = "```\n::config\nGhost: type=gate\n::\n[[Ghost]]\n```\n"

    assert knowledge.parse(text, DOC) == knowledge.Parsed([], [], set())


def test_an_anchor_to_a_missing_path_is_reported(project) -> None:
    write(
        project,
        DOC,
        document(ALPHA, BETA, "Gone: type=gate, path=scripts/gone.py\n")
        + "[[Alpha]] [[Beta]] [[Gone]]\n",
    )

    assert knowledge.problems_in(project) == [
        f"anchor: Gone ({DOC}) points at scripts/gone.py, which does not exist"
    ]


def test_a_file_no_entity_owns_is_reported(project) -> None:
    write(project, DOC, document(ALPHA) + MENTION_ALPHA)

    assert knowledge.problems_in(project) == ["coverage: scripts/beta.py belongs to no entity"]


def test_a_directory_path_owns_the_files_below_it(project) -> None:
    (project / SCRIPTS / "pkg").mkdir()
    (project / SCRIPTS / "pkg" / "mod.py").write_text("")
    write(
        project,
        DOC,
        document(ALPHA, BETA, "Pkg: type=gate, path=scripts/pkg\n")
        + "[[Alpha]] [[Beta]] [[Pkg]]\n",
    )

    assert knowledge.problems_in(project) == []


def test_an_entity_defined_in_two_documents_is_reported(project) -> None:
    write(project, DOC, document(ALPHA, BETA) + "[[Alpha]] [[Beta]]\n")
    write(project, OTHER_DOC, document("Alpha: type=gate\n") + MENTION_ALPHA)

    assert knowledge.problems_in(project) == [
        f"links: Alpha is defined 2 times ({DOC}, {OTHER_DOC})"
    ]


def test_an_entity_defined_twice_in_one_document_is_reported(project) -> None:
    write(project, DOC, document(ALPHA, ALPHA, BETA) + "[[Alpha]] [[Beta]]\n")

    assert knowledge.problems_in(project) == [f"links: Alpha is defined 2 times ({DOC}, {DOC})"]


def test_a_reference_to_an_undefined_entity_is_reported(project) -> None:
    write(project, DOC, document(ALPHA, BETA) + "[[Alpha]] [[Beta]] [[Nowhere]]\n")

    assert knowledge.problems_in(project) == ["links: Nowhere is used but defined nowhere"]


def test_an_edge_to_an_undefined_entity_is_reported(project) -> None:
    write(
        project,
        DOC,
        document(ALPHA, BETA) + "[[Alpha]] [[Beta]]\n::rel Alpha -> Nowhere [uses] ::\n",
    )

    assert knowledge.problems_in(project) == ["links: Nowhere is used but defined nowhere"]


def test_an_entity_nobody_mentions_is_reported(project) -> None:
    write(project, DOC, document(ALPHA, BETA) + MENTION_ALPHA)

    assert knowledge.problems_in(project) == ["links: Beta is defined but never mentioned"]


def test_a_true_imports_edge_passes_and_a_false_one_is_reported(project) -> None:
    write(
        project,
        DOC,
        document(ALPHA, BETA) + "[[Alpha]] [[Beta]]\n::rel Alpha -> Beta [imports] ::\n",
    )
    assert knowledge.problems_in(project) == []

    write(
        project,
        DOC,
        document(ALPHA, BETA) + "[[Alpha]] [[Beta]]\n::rel Beta -> Alpha [imports] ::\n",
    )
    assert knowledge.problems_in(project) == [f"imports: Beta does not import Alpha ({DOC})"]


def test_an_installs_edge_must_name_something_the_installer_lists(project) -> None:
    write(
        project,
        DOC,
        document(ALPHA, BETA, "Boot: type=gate\n")
        + "[[Boot]] [[Alpha]] [[Beta]]\n"
        + "::rel Boot -> Alpha [installs] ::\n"
        + "::rel Boot -> Beta [installs] ::\n",
    )

    assert knowledge.problems_in(project) == [
        f"installs: {knowledge.INSTALLER} does not list Beta ({DOC})"
    ]


def test_main_exits_one_and_prints_each_problem(project, capsys) -> None:
    write(project, DOC, document(ALPHA) + MENTION_ALPHA)

    assert knowledge.main(["--path", str(project)]) == 1
    assert "✗ coverage: scripts/beta.py belongs to no entity" in capsys.readouterr().err


def test_main_exits_zero_when_faithful(project, capsys) -> None:
    faithful(project)

    assert knowledge.main(["--path", str(project)]) == 0
    assert "✓" in capsys.readouterr().out


def test_this_repos_own_documents_match_the_repo() -> None:
    assert knowledge.problems_in(ROOT) == []
