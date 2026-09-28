"""Ground truth: explaining-constant (CG009) — Kent Beck, Tidy First? (2023).

Should trigger: ruff PLR2004 (magic-value-comparison).
"""


def is_not_found(status_code: int) -> bool:
    return status_code == 404
