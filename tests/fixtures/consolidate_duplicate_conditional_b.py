"""Ground truth: consolidate-duplicate-conditional (CG024) — Martin Fowler,
Refactoring, 2nd ed. (2018). Paired with
consolidate_duplicate_conditional_a.py — see that file's docstring.
"""


def handle_request_b(status: int) -> str:
    if status == 200:
        message = "ok"
    elif status == 404:
        message = "not found"
    elif status == 500:
        message = "server error"
    else:
        message = "unknown"
    return message
