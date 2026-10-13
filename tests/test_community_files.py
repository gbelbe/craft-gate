"""The files a visitor to the repository meets first are well-formed and point at real things."""

from __future__ import annotations

import pytest
import yaml
from conftest import ROOT

FORMS = sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*_*.yml"))
SECURITY = (ROOT / "SECURITY.md").read_text()


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_each_issue_form_has_the_fields_github_requires(path) -> None:
    form = yaml.safe_load(path.read_text())

    assert form["name"]
    assert form["description"]
    assert form["body"]
    assert all("type" in field for field in form["body"])


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_issue_form_field_ids_are_unique(path) -> None:
    ids = [f["id"] for f in yaml.safe_load(path.read_text())["body"] if "id" in f]

    assert len(ids) == len(set(ids))


def test_the_issue_chooser_routes_vulnerabilities_to_a_private_report() -> None:
    config = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text())

    urls = [link["url"] for link in config["contact_links"]]
    assert any(url.endswith("/security/advisories/new") for url in urls)


def test_security_policy_names_a_private_channel_and_the_supported_version() -> None:
    assert "security/advisories/new" in SECURITY
    assert "do not open a public issue" in SECURITY
    assert "latest release" in SECURITY
