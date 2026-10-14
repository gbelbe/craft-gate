"""A consuming repo may import the shipped scripts as a package, not only run them by path.

kai-ster keeps `scripts/__init__.py` and its tests do `from scripts.check_refactor_first import
...`. Run by path, Python puts the script's directory on sys.path, so a sibling imports by bare
name; imported as `scripts.<name>` that is no longer true, and each script has to arrange it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest
from conftest import ROOT

SCRIPTS = "scripts"
MODULES = sorted(p.stem for p in (ROOT / SCRIPTS).glob("*.py") if p.stem != "__init__")


@pytest.fixture(scope="module")
def consumer(tmp_path_factory) -> object:
    """A repo whose scripts/ is a package, with nothing else on the import path."""
    root = tmp_path_factory.mktemp("consumer")
    shutil.copytree(ROOT / SCRIPTS, root / SCRIPTS, ignore=shutil.ignore_patterns("__pycache__"))
    (root / SCRIPTS / "__init__.py").write_text("")
    return root


@pytest.mark.parametrize("module", MODULES)
def test_each_script_imports_as_part_of_a_scripts_package(consumer, module) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {SCRIPTS}.{module}"],
        cwd=consumer,
        capture_output=True,
        text=True,
        env={"PATH": "", "PYTHONPATH": ""},
    )

    assert result.returncode == 0, result.stderr
