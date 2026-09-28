#!/usr/bin/env python3
"""craftCov — a coverage-report-style scan of the craftsmanship catalog.

Honest about its limits before anything else: only the entries in
catalog.yaml that carry a `detector` (6 of 31 as of this writing — see
`--list-detectors`) have a real mechanical proxy. Reusing `ruff` (Rust,
already a dependency in every repo this ships to, ships its own fast
internal cache) as the detection engine gets guard-clauses, dead-code,
explaining-constant, extract-helper, introduce-parameter-object, and
replace-conditional-with-polymorphism — the subset where a lint rule is a
decent proxy for the smell (extract-class/God Class has no detector: ruff's
candidate rules are either preview-only or don't exist in stable form — see
catalog.yaml). Feature Envy, Data Clumps *precisely* (not just "too many
params" — the same group repeating), Message Chains, Primitive Obsession,
Refused Bequest, and every `principle`/`workflow` entry have no detector on
purpose: a regex or AST check confident enough to report them would cry
wolf more than it'd help. Those stay a job for the procedure in
CRAFTSMANSHIP.md (read the code, ask the developer), not this script.
craftCov finds the mechanically-checkable subset; it is not a replacement
for the judgment call the rest of the catalog asks for.

Caching: findings for a file are cached by its content hash, keyed by path
relative to the scan root (so the cache survives the repo moving to a
different absolute path). A re-run only re-scans files whose hash changed
since the last run (or that are new); everything else is read back from
`.craftcov_cache.json`. This is on top of, not instead of, ruff's own
per-file cache (`.ruff_cache/`) — craftCov's cache also stores the
class/function attribution (see below), which ruff doesn't know about, so
re-running still avoids re-parsing unchanged files' ASTs.

Requires (unlike the other craft-gate scripts, which are plain bash):
`ruff` on PATH, and PyYAML importable (`pip install pyyaml` — every repo
this ships to already has it via ruff/render_catalog.py's own CI use, but
it isn't otherwise assumed anywhere else in craft-gate; see README's
Requirements section).

Usage:
    python3 scripts/craftcov.py                  # scan, text report
    python3 scripts/craftcov.py --format json     # machine-readable
    python3 scripts/craftcov.py --verbose         # + every finding, file:line
    python3 scripts/craftcov.py --no-cache        # ignore and overwrite the cache
    python3 scripts/craftcov.py --list-detectors  # which heuristics are detectable, and how
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog.yaml"
DEFAULT_CACHE_PATH = Path(".craftcov_cache.json")
CACHE_VERSION = 2


# ── catalog / rule mapping ───────────────────────────────────────────────────


def load_catalog() -> list[dict]:
    return yaml.safe_load(CATALOG_PATH.read_text())


def rule_to_heuristic_map(catalog: list[dict]) -> dict[str, dict]:
    """ruff rule code -> the catalog entry it's a proxy for.

    Each rule maps to exactly one entry by construction (see catalog.yaml's
    detector fields) — if that ever needs to change, this is where a rule
    winning over another would be decided, and it should be a deliberate
    choice, not silent.
    """
    mapping: dict[str, dict] = {}
    for entry in catalog:
        detector = entry.get("detector")
        if not detector or detector.get("tool") != "ruff":
            continue
        for rule in detector["rules"]:
            if rule in mapping:
                raise SystemExit(
                    f"✗ ruff rule {rule} is claimed by both "
                    f"{mapping[rule]['id']} and {entry['id']} in catalog.yaml"
                )
            mapping[rule] = entry
    return mapping


# ── file discovery ───────────────────────────────────────────────────────────


def discover_python_files(root: Path) -> list[str]:
    """Paths, relative to root, of every tracked .py file. Via git when
    possible (git already knows what to ignore — venvs, build artefacts —
    so this avoids reinventing that); falls back to a plain glob outside a
    git repo."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return sorted(line for line in out.splitlines() if line)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(str(p.relative_to(root)) for p in root.rglob("*.py"))


def file_hash(root: Path, rel: str) -> str:
    return hashlib.sha256((root / rel).read_bytes()).hexdigest()


# ── class/function attribution ───────────────────────────────────────────────


def build_scope_index(source: str) -> list[tuple[int, int, str, str]]:
    """(start_line, end_line, kind, qualified_name) for every class/function
    in the file. Callers pick the smallest enclosing span themselves, so
    order here doesn't matter."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    scopes: list[tuple[int, int, str, str]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "class" if isinstance(child, ast.ClassDef) else "function"
                qualname = f"{prefix}{child.name}" if not prefix else f"{prefix}.{child.name}"
                end = getattr(child, "end_lineno", child.lineno)
                scopes.append((child.lineno, end, kind, qualname))
                walk(child, qualname + ("." if kind == "class" else ""))
            else:
                walk(child, prefix)

    walk(tree, "")
    return scopes


def enclosing_class(scopes: list[tuple[int, int, str, str]], line: int) -> str | None:
    best: tuple[int, int, str, str] | None = None
    for start, end, kind, qualname in scopes:
        if kind != "class" or not (start <= line <= end):
            continue
        if best is None or (end - start) < (best[1] - best[0]):
            best = (start, end, kind, qualname)
    return best[3] if best else None


# ── scanning ──────────────────────────────────────────────────────────────────


def run_ruff(root: Path, rel_files: list[str], rules: list[str]) -> list[dict]:
    if not rel_files:
        return []
    try:
        proc = subprocess.run(
            ["ruff", "check", "--select", ",".join(rules), "--output-format=json", *rel_files],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,  # ruff exits 1 when it finds anything — that's not our error
        )
    except FileNotFoundError:
        raise SystemExit("✗ craftcov needs `ruff` on PATH — pip install ruff, or use your project's existing one.")
    if proc.returncode not in (0, 1):
        raise SystemExit(f"✗ ruff failed:\n{proc.stderr}")
    return json.loads(proc.stdout or "[]")


def scan_files(root: Path, rel_files: list[str], rule_map: dict[str, dict]) -> dict[str, list[dict]]:
    """relative path -> list of finding dicts, for exactly these files."""
    raw = run_ruff(root, rel_files, sorted(rule_map))
    by_file: dict[str, list[dict]] = {rel: [] for rel in rel_files}
    scopes_cache: dict[str, list[tuple[int, int, str, str]]] = {}

    for item in raw:
        abs_path = Path(item["filename"])
        if not abs_path.is_absolute():
            abs_path = (root / abs_path).resolve()
        try:
            rel = str(abs_path.relative_to(root))
        except ValueError:
            continue  # outside root somehow — skip rather than crash
        code = item["code"]
        entry = rule_map.get(code)
        if entry is None:
            continue  # shouldn't happen (we only --select mapped rules), but don't crash on it
        line = item["location"]["row"]

        if rel not in scopes_cache:
            scopes_cache[rel] = build_scope_index((root / rel).read_text())
        cls = enclosing_class(scopes_cache[rel], line)

        by_file.setdefault(rel, []).append(
            {
                "line": line,
                "col": item["location"]["column"],
                "rule": code,
                "heuristic_id": entry["id"],
                "heuristic_code": entry.get("code", ""),
                "class": cls,
            }
        )
    return by_file


# ── cache ─────────────────────────────────────────────────────────────────────


def load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {"version": CACHE_VERSION, "files": {}}
    try:
        data = json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"version": CACHE_VERSION, "files": {}}
    if data.get("version") != CACHE_VERSION:
        return {"version": CACHE_VERSION, "files": {}}  # schema changed — start fresh, don't crash
    return data


def save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.write_text(json.dumps(cache, indent=0))


# ── aggregation + report ─────────────────────────────────────────────────────


def aggregate(by_file: dict[str, list[dict]]) -> dict:
    by_heuristic: dict[str, int] = {}
    by_file_count: dict[str, int] = {}
    by_class: dict[str, int] = {}
    by_library: dict[str, int] = {}
    total = 0

    for rel, findings in by_file.items():
        if not findings:
            continue
        by_file_count[rel] = len(findings)
        parts = Path(rel).parts
        library = parts[0] if len(parts) > 1 else "(root)"
        for f in findings:
            total += 1
            by_heuristic[f["heuristic_id"]] = by_heuristic.get(f["heuristic_id"], 0) + 1
            by_library[library] = by_library.get(library, 0) + 1
            key = f"{rel}::{f['class']}" if f["class"] else rel
            by_class[key] = by_class.get(key, 0) + 1

    return {
        "total": total,
        "by_heuristic": by_heuristic,
        "by_file": by_file_count,
        "by_class": by_class,
        "by_library": by_library,
    }


def print_text_report(agg: dict, catalog_by_id: dict[str, dict], by_file: dict[str, list[dict]], verbose: bool, timing: dict) -> None:
    print("craftCov — craftsmanship heuristic scan")
    print(
        f"Scanned {timing['total_files']} files "
        f"({timing['changed']} changed, {timing['cached']} from cache) in {timing['elapsed']:.2f}s"
    )
    print()

    if agg["total"] == 0:
        print("No findings for the detectable heuristics. ✓")
    else:
        print("By heuristic")
        print(f"{'CODE':7s} {'ID':38s} {'COUNT':>6s}  SOURCE")
        rows = sorted(agg["by_heuristic"].items(), key=lambda kv: -kv[1])
        for hid, count in rows:
            entry = catalog_by_id[hid]
            print(f"{entry.get('code',''):7s} {hid:38s} {count:6d}  {entry['source']}")
        print(f"{'':7s} {'TOTAL':38s} {agg['total']:6d}")
        print()

        print("By file (top 15)")
        for rel, count in sorted(agg["by_file"].items(), key=lambda kv: -kv[1])[:15]:
            print(f"  {count:5d}  {rel}")
        print()

        print("By class (top 15, module-level findings excluded)")
        class_only = {k: v for k, v in agg["by_class"].items() if "::" in k}
        for key, count in sorted(class_only.items(), key=lambda kv: -kv[1])[:15]:
            print(f"  {count:5d}  {key}")
        print()

        print("By library (top-level directory)")
        for lib, count in sorted(agg["by_library"].items(), key=lambda kv: -kv[1]):
            print(f"  {count:5d}  {lib}")

    if verbose and agg["total"] > 0:
        print()
        print("Every finding")
        for rel, findings in sorted(by_file.items()):
            for f in sorted(findings, key=lambda x: x["line"]):
                scope = f" [{f['class']}]" if f["class"] else ""
                print(f"  {rel}:{f['line']}  {f['heuristic_code']} {f['heuristic_id']}{scope}")

    n_detectable = sum(1 for e in catalog_by_id.values() if e.get("detector"))
    n_total = len(catalog_by_id)
    print()
    print(
        f"{n_detectable}/{n_total} heuristics have an automatic detector "
        f"({100 * n_detectable // n_total}%) — the rest need the procedure in "
        f"CRAFTSMANSHIP.md (ask the developer), not a scan. Run with "
        f"--list-detectors to see which is which."
    )


def print_detector_list(catalog: list[dict]) -> None:
    for e in catalog:
        detector = e.get("detector")
        status = f"ruff: {', '.join(detector['rules'])}" if detector else "— (needs judgment, see procedure)"
        print(f"{e.get('code',''):7s} {e['id']:38s} {status}")


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=".", help="repo root to scan (default: .)")
    parser.add_argument("--cache-file", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--no-cache", action="store_true", help="ignore and overwrite the existing cache")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--verbose", "-v", action="store_true", help="list every finding, not just the summary")
    parser.add_argument("--list-detectors", action="store_true", help="print which heuristics are detectable and how, then exit")
    args = parser.parse_args()

    catalog = load_catalog()
    catalog_by_id = {e["id"]: e for e in catalog}

    if args.list_detectors:
        print_detector_list(catalog)
        return 0

    rule_map = rule_to_heuristic_map(catalog)
    root = Path(args.path).resolve()
    cache_path = Path(args.cache_file)

    t0 = time.monotonic()
    files = discover_python_files(root)  # relative paths
    cache = {"version": CACHE_VERSION, "files": {}} if args.no_cache else load_cache(cache_path)
    cached_files = cache["files"]

    hashes = {rel: file_hash(root, rel) for rel in files}
    changed = [rel for rel in files if cached_files.get(rel, {}).get("hash") != hashes[rel]]
    unchanged = [rel for rel in files if rel not in changed]

    new_findings = scan_files(root, changed, rule_map) if changed else {}

    by_file: dict[str, list[dict]] = {}
    for rel in unchanged:
        by_file[rel] = cached_files[rel]["findings"]
    for rel in changed:
        entry = new_findings.get(rel, [])
        by_file[rel] = entry
        cached_files[rel] = {"hash": hashes[rel], "findings": entry}

    # drop cache entries for files that no longer exist
    for stale in set(cached_files) - set(hashes):
        del cached_files[stale]

    save_cache(cache_path, cache)

    agg = aggregate(by_file)
    timing = {
        "total_files": len(files),
        "changed": len(changed),
        "cached": len(unchanged),
        "elapsed": time.monotonic() - t0,
    }

    if args.format == "json":
        print(json.dumps({"summary": agg, "findings": by_file, "timing": timing}, indent=2))
    else:
        print_text_report(agg, catalog_by_id, by_file, args.verbose, timing)

    return 0


if __name__ == "__main__":
    sys.exit(main())
