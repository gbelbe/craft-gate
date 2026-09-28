"""Ground truth: guard-clauses (CG001) — Kent Beck, Tidy First? (2023).

Should trigger: ruff RET505 (superfluous-else-return).
"""


def classify(x: int) -> str:
    if x > 0:
        return "positive"
    else:
        return "non-positive"
