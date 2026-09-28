"""Ground truth: replace-conditional-with-polymorphism (CG021) --
Martin Fowler, Refactoring, 2nd ed. (2018).

Should trigger: ruff PLR0912 (too-many-branches, default max 12).
"""


def classify(n: int) -> str:
    if n == 0:
        return "zero"
    elif n == 1:
        return "1"
    elif n == 2:
        return "2"
    elif n == 3:
        return "3"
    elif n == 4:
        return "4"
    elif n == 5:
        return "5"
    elif n == 6:
        return "6"
    elif n == 7:
        return "7"
    elif n == 8:
        return "8"
    elif n == 9:
        return "9"
    elif n == 10:
        return "10"
    elif n == 11:
        return "11"
    elif n == 12:
        return "12"
    elif n == 13:
        return "13"
    else:
        return "many"
