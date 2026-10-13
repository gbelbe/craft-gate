"""Shared pytest setup: the shipped scripts importable by name, and a throwaway git repo."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


class GitRepo:
    """A real repository in a tmp dir, with helpers to write files and commit them."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=self.path, capture_output=True, text=True, check=True
        )
        return proc.stdout.strip()

    def sha(self, ref: str = "HEAD") -> str:
        return self.git("rev-parse", ref)

    def branch(self, name: str, *, reset: bool = False) -> None:
        """Switch to a new branch `name` (or, with `reset`, point it at HEAD)."""
        self.git("checkout", "-q", "-B" if reset else "-b", name)

    def commit_staged(self, message: str) -> None:
        self.git("commit", "-q", "-m", message)

    def write(self, rel: str, content: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self, message: str, **files: str) -> str:
        """Write `files` (keys use `__` for `/`, e.g. `pkg__mod_py`), commit, return the SHA."""
        for key, content in files.items():
            self.write(key.replace("__", "/").replace("_py", ".py"), content)
        self.git("add", "-A")
        self.commit_staged(message)
        return self.sha()


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    root = tmp_path.resolve() / "repo"  # resolved: macOS /tmp is a symlink
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True)
    return GitRepo(root)


@pytest.fixture
def run_main(monkeypatch: pytest.MonkeyPatch) -> Callable[..., int]:
    """Call a script's argv-less `main()` with the given command line."""

    def run(module, *argv: str) -> int:
        monkeypatch.setattr(sys, "argv", [module.__name__, *argv])
        return module.main()

    return run
