"""Ground truth: dead-code (CG002) — Kent Beck, Tidy First? (2023).

Should trigger: ruff F401 (unused import), F811 (redefined while unused),
F841 (unused variable), and vulture (unused function, module-level).
"""

import os  # F401: never used


def compute() -> int:
    unused_local = 42  # F841: never read
    return 1


def compute() -> int:  # F811: redefines 'compute' above, which was never called
    return 2


def never_called_anywhere() -> int:  # vulture: unused function
    return 3
