from textwrap import dedent as _dedent

__all__ = ["dedent"]


def dedent(text: str) -> str:
    """Fix indentation and also trim given text string."""
    return _dedent(text.lstrip("\n").rstrip(" \t\n"))
