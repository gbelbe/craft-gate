"""Ground truth: consolidate-duplicate-conditional (CG024) — Martin Fowler,
Refactoring, 2nd ed. (2018). Paired with
consolidate_duplicate_conditional_b.py — the two share an identical 8-line
block below (min_lines default is 8, see catalog.yaml).

Should trigger: dupes (ported rolling-hash line-window match).
"""


def handle_request_a(status: int) -> str:
    if status == 200:
        message = "ok"
    elif status == 404:
        message = "not found"
    elif status == 500:
        message = "server error"
    else:
        message = "unknown"
    return message
