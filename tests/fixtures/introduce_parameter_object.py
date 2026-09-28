"""Ground truth: introduce-parameter-object (CG018) — Martin Fowler,
Refactoring, 2nd ed. (2018).

Should trigger: ruff PLR0913 (too-many-arguments, default max 5).
"""


def render_point(x: int, y: int, z: int, color: str, opacity: float, label: str) -> str:
    return f"{label}: ({x},{y},{z}) {color}@{opacity}"
