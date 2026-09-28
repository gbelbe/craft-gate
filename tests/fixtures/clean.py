"""Negative control — deliberately free of every detectable heuristic here.
craftcov.py should report zero findings for this file. Both functions are
called below so vulture doesn't (correctly, if misleadingly for a fixture)
flag them as unused — a real negative control has to be genuinely used."""

from __future__ import annotations

_HTTP_NOT_FOUND = 404


def classify(status_code: int) -> str:
    if status_code == _HTTP_NOT_FOUND:
        return "not found"
    return "other"


def add(a: int, b: int) -> int:
    return a + b


if __name__ == "__main__":
    print(classify(_HTTP_NOT_FOUND), add(1, 2))
