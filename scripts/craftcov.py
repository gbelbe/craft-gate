#!/usr/bin/env python3
"""craftCov — a coverage-report-style scan of the craftsmanship catalog.

Honest about its limits before anything else: only the entries in
catalog.yaml that carry `detectors` (7 of 31 as of this writing — see
`--list-detectors`) have a real mechanical proxy. Three engines, each
reused rather than reimplemented:

  - `ruff` (Rust, already a dependency in every repo this ships to, ships
    its own fast internal cache) — guard-clauses, dead-code,
    explaining-constant, extract-helper, introduce-parameter-object,
    replace-conditional-with-polymorphism.
  - `pylint`, scoped to exactly two rules (R0902/R0904) — extract-class /
    God Class. ruff hasn't ported these yet (R0904 is preview-only there,
    R0902 doesn't exist in ruff at all); upstream pylint's originals are
    stable, so this is the one entry that needs a second tool on PATH.
  - `vulture` — a second, higher-recall pass for dead-code alongside
    ruff's F401/F811/F841: catches unused module-level functions/classes
    ruff's own-file-scoped checks can't see. Verified on a real, framework-
    heavy codebase (kai-ster: pytest-bdd + Textual) while building this:
    vulture's confidence scores cluster hard into two tiers — unused
    *variables* at 100% (redundant with ruff's own F841, adds nothing) and
    unused functions/classes/methods at 60% (vulture's own "fairly sure but
    could be wrong" floor — decorator-registered step defs and Textual's
    on_* handlers score exactly here without being genuinely dead). That
    60% tier is also where all of vulture's actual unique value lives, so
    craftCov reports it unfiltered by default (`--vulture-min-confidence 0`,
    vulture's own default) rather than quietly discarding the one thing
    ruff can't already tell you — raise the threshold yourself via
    `--vulture-min-confidence` once you've triaged a first pass and know
    your codebase's noise floor. The per-finding confidence is preserved in
    `--verbose`/JSON output for exactly this triage.

Feature Envy, Data Clumps *precisely* (not just "too many params" — the
*same group* repeating), Message Chains, Primitive Obsession, Refused
Bequest, cross-file duplicate code, and every `principle`/`workflow` entry
have no detector on purpose: no maintained, reusable Python tool exists for
any of them (checked against ruff's own open issues, PMD's CPD — Java/JVM,
out of scope here — and the design-smell-detection literature, which is
Java/C#/C++-tooling-only). A regex or AST check confident enough to report
these would cry wolf more than it'd help. Those stay a job for the
procedure in CRAFTSMANSHIP.md (read the code, ask the developer), not this
script. craftCov finds the mechanically-checkable subset; it is not a
replacement for the judgment call the rest of the catalog asks for.

Caching: findings for a file are cached by its content hash, keyed by path
relative to the scan root (so the cache survives the repo moving to a
different absolute path). A re-run only re-scans files whose hash changed
since the last run (or that are new); everything else is read back from
`.craftcov_cache.json`. This is on top of, not instead of, each tool's own
cache where it has one (ruff's `.ruff_cache/`) — craftCov's cache also
stores the class/function attribution none of the three tools track on
their own, so a warm re-run skips re-parsing ASTs too, not just re-linting.

When more than one tool flags the *same* line for the *same* heuristic
(e.g. ruff's F401 and vulture both catch an unused import), it's counted
once, not twice — see `scan_files`'s dedup.

Requires (unlike the other craft-gate scripts, which are plain bash):
PyYAML importable, plus whichever of `ruff` / `pylint` / `vulture` is on
PATH for the detectors catalog.yaml actually uses — only invoked if at
least one entry needs it, so a repo without pylint installed still gets
the other two engines' findings, not a hard failure. `uv sync --extra
craftcov` in this repo installs all three; see README's Requirements.

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
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog.yaml"
DEFAULT_CACHE_PATH = Path(".craftcov_cache.json")
CACHE_VERSION = 4

RULE_BASED_TOOLS = {"ruff", "pylint"}
WHOLE_FILE_TOOLS = {"vulture"}


# ── catalog / detector mapping ────────────────────────────────────────────────


def load_catalog() -> list[dict]:
    return yaml.safe_load(CATALOG_PATH.read_text())


def build_detector_index(catalog: list[dict]) -> tuple[dict[str, dict[str, dict]], dict[str, dict]]:
    """(rule_maps, whole_tool_map).

    rule_maps: tool -> {rule_code: catalog_entry}, for rule-granular tools
    (ruff, pylint). whole_tool_map: tool -> catalog_entry, for tools whose
    findings all mean one specific heuristic regardless of message
    (vulture). Each (tool, rule) or (tool) claims exactly one entry by
    construction — collisions are a catalog.yaml authoring error, not
    something to silently pick a winner for.
    """
    rule_maps: dict[str, dict[str, dict]] = {}
    whole_tool: dict[str, dict] = {}
    for entry in catalog:
        for d in entry.get("detectors", []):
            tool = d["tool"]
            if tool in RULE_BASED_TOOLS:
                bucket = rule_maps.setdefault(tool, {})
                for rule in d["rules"]:
                    if rule in bucket:
                        raise SystemExit(
                            f"✗ {tool} rule {rule} is claimed by both "
                            f"{bucket[rule]['id']} and {entry['id']} in catalog.yaml"
                        )
                    bucket[rule] = entry
            elif tool in WHOLE_FILE_TOOLS:
                if tool in whole_tool:
                    raise SystemExit(
                        f"✗ {tool} (a whole-file detector) is claimed by both "
                        f"{whole_tool[tool]['id']} and {entry['id']} in catalog.yaml"
                    )
                whole_tool[tool] = entry
            else:
                raise SystemExit(f"✗ catalog.yaml: unknown detector tool '{tool}' on {entry['id']}")
    return rule_maps, whole_tool


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


# ── tool runners ──────────────────────────────────────────────────────────────
# Each returns a flat list of {rel, line, col, tool, rule} — normalized
# before anything downstream has to know these are three different tools.


def _normalize_path(root: Path, raw: str) -> str | None:
    p = Path(raw)
    if not p.is_absolute():
        p = (root / p).resolve()
    try:
        return str(p.relative_to(root))
    except ValueError:
        return None  # outside root somehow — caller skips rather than crashes


def run_ruff(root: Path, rel_files: list[str], rules: list[str]) -> list[dict]:
    if not rel_files:
        return []
    try:
        proc = subprocess.run(
            ["ruff", "check", "--select", ",".join(rules), "--output-format=json", *rel_files],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,  # ruff exits 1 when it finds anything — not our error
        )
    except FileNotFoundError:
        raise SystemExit("✗ craftcov needs `ruff` on PATH for this catalog's ruff-mapped entries — pip install ruff.")
    if proc.returncode not in (0, 1):
        raise SystemExit(f"✗ ruff failed:\n{proc.stderr}")
    items = []
    for item in json.loads(proc.stdout or "[]"):
        rel = _normalize_path(root, item["filename"])
        if rel is None:
            continue
        items.append(
            {"rel": rel, "line": item["location"]["row"], "col": item["location"]["column"], "tool": "ruff", "rule": item["code"]}
        )
    return items


def run_pylint(root: Path, rel_files: list[str], rules: list[str]) -> list[dict]:
    if not rel_files:
        return []
    try:
        proc = subprocess.run(
            ["pylint", "--disable=all", f"--enable={','.join(rules)}", "--output-format=json", *rel_files],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,  # pylint's exit code is a findings bitmask, not a crash signal
        )
    except FileNotFoundError:
        raise SystemExit(
            "✗ craftcov needs `pylint` on PATH for this catalog's pylint-mapped entries "
            "(extract-class) — pip install pylint, or drop that entry's detector in catalog.yaml."
        )
    try:
        raw = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        raise SystemExit(f"✗ pylint produced unparseable output:\n{proc.stdout}\n{proc.stderr}")
    items = []
    for item in raw:
        rel = _normalize_path(root, item["path"])
        if rel is None:
            continue
        items.append({"rel": rel, "line": item["line"], "col": item.get("column", 0), "tool": "pylint", "rule": item["message-id"]})
    return items


_VULTURE_LINE = re.compile(r"^(?P<path>.+):(?P<line>\d+): .+ \((?P<pct>\d+)% confidence\)$")


def run_vulture(root: Path, rel_files: list[str], min_confidence: int) -> list[dict]:
    """min_confidence is vulture's own per-finding score, not craftcov's
    invention — on a real codebase (kai-ster, checked while building this)
    it clusters hard into two tiers: unused *variables* at 100% (redundant
    with ruff's own F841 — vulture adds nothing there) and unused
    functions/classes/methods at 60% (vulture's own floor for "fairly sure
    but could be wrong" — decorator-registered pytest-bdd steps and
    Textual's on_* naming-convention handlers are exactly the kind of
    indirect-call pattern that scores here without being genuinely dead).
    Default 0 (vulture's own default: report everything) trades precision
    for recall on purpose — raise it via --vulture-min-confidence once
    you've triaged a first pass and know your codebase's noise floor."""
    if not rel_files:
        return []
    try:
        proc = subprocess.run(
            ["vulture", f"--min-confidence={min_confidence}", *rel_files],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,  # vulture exits non-zero when it finds anything — not our error
        )
    except FileNotFoundError:
        raise SystemExit(
            "✗ craftcov needs `vulture` on PATH for this catalog's vulture-mapped entries "
            "(dead-code) — pip install vulture, or drop that entry's vulture detector in catalog.yaml."
        )
    items = []
    for line in proc.stdout.splitlines():
        m = _VULTURE_LINE.match(line)
        if not m:
            continue  # vulture has no machine-readable format; skip anything that doesn't parse rather than crash
        rel = _normalize_path(root, m.group("path"))
        if rel is None:
            continue
        items.append(
            {
                "rel": rel,
                "line": int(m.group("line")),
                "col": 0,
                "tool": "vulture",
                "rule": None,
                "confidence": int(m.group("pct")),
            }
        )
    return items


# ── scanning ──────────────────────────────────────────────────────────────────


def scan_files(
    root: Path,
    rel_files: list[str],
    rule_maps: dict[str, dict[str, dict]],
    whole_tool: dict[str, dict],
    vulture_min_confidence: int = 0,
) -> dict[str, list[dict]]:
    """relative path -> list of finding dicts, for exactly these files."""
    raw_items: list[dict] = []
    if "ruff" in rule_maps:
        raw_items += run_ruff(root, rel_files, sorted(rule_maps["ruff"]))
    if "pylint" in rule_maps:
        raw_items += run_pylint(root, rel_files, sorted(rule_maps["pylint"]))
    if "vulture" in whole_tool:
        raw_items += run_vulture(root, rel_files, vulture_min_confidence)

    by_file: dict[str, list[dict]] = {rel: [] for rel in rel_files}
    scopes_cache: dict[str, list[tuple[int, int, str, str]]] = {}
    seen: set[tuple[str, int, str]] = set()  # (rel, line, heuristic_id) — dedup across tools

    for item in raw_items:
        rel = item["rel"]
        if rel not in by_file:
            continue  # not one of the files we were asked to scan this run
        if item["tool"] in RULE_BASED_TOOLS:
            entry = rule_maps.get(item["tool"], {}).get(item["rule"])
        else:
            entry = whole_tool.get(item["tool"])
        if entry is None:
            continue  # shouldn't happen (we only ask for mapped rules), but don't crash on it

        dedup_key = (rel, item["line"], entry["id"])
        if dedup_key in seen:
            continue  # another tool already flagged this exact line for this heuristic
        seen.add(dedup_key)

        if rel not in scopes_cache:
            scopes_cache[rel] = build_scope_index((root / rel).read_text())
        cls = enclosing_class(scopes_cache[rel], item["line"])

        by_file[rel].append(
            {
                "line": item["line"],
                "col": item["col"],
                "tool": item["tool"],
                "rule": item["rule"],
                "confidence": item.get("confidence"),  # only vulture sets this
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
                rule = f"{f['tool']}:{f['rule']}" if f["rule"] else f["tool"]
                if f.get("confidence") is not None:
                    rule += f" {f['confidence']}%"
                print(f"  {rel}:{f['line']}  {f['heuristic_code']} {f['heuristic_id']} ({rule}){scope}")

    n_detectable = sum(1 for e in catalog_by_id.values() if e.get("detectors"))
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
        detectors = e.get("detectors")
        if not detectors:
            status = "— (needs judgment, see procedure)"
        else:
            parts = []
            for d in detectors:
                parts.append(f"{d['tool']}: {', '.join(d['rules'])}" if "rules" in d else d["tool"])
            status = " + ".join(parts)
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
    parser.add_argument(
        "--vulture-min-confidence",
        type=int,
        default=0,
        metavar="N",
        help="vulture's own confidence floor (0-100, default 0 = vulture's default: report everything). "
        "On a real codebase this tends to cluster at 60%% (functions/classes/methods, vulture's own "
        "'fairly sure but could be wrong' tier) and 100%% (unused variables, redundant with ruff's own "
        "F841). The cache doesn't know about this flag — changing it between runs needs --no-cache "
        "to actually take effect.",
    )
    args = parser.parse_args()

    catalog = load_catalog()
    catalog_by_id = {e["id"]: e for e in catalog}

    if args.list_detectors:
        print_detector_list(catalog)
        return 0

    rule_maps, whole_tool = build_detector_index(catalog)
    root = Path(args.path).resolve()
    cache_path = Path(args.cache_file)

    t0 = time.monotonic()
    files = discover_python_files(root)  # relative paths
    cache = {"version": CACHE_VERSION, "files": {}} if args.no_cache else load_cache(cache_path)
    cached_files = cache["files"]

    hashes = {rel: file_hash(root, rel) for rel in files}
    changed = [rel for rel in files if cached_files.get(rel, {}).get("hash") != hashes[rel]]
    unchanged = [rel for rel in files if rel not in changed]

    new_findings = scan_files(root, changed, rule_maps, whole_tool, args.vulture_min_confidence) if changed else {}

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
