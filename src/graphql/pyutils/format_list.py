from typing import Sequence


__all__ = ["or_list", "and_list"]


def or_list(items: Sequence[str]) -> str:
    """Given [ A, B, C ] return 'A, B, or C'."""
    return format_list("or", items)


def and_list(items: Sequence[str]) -> str:
    """Given [ A, B, C ] return 'A, B, and C'."""
    return format_list("and", items)


def format_list(conjunction: str, items: Sequence[str]) -> str:
    """Given [ A, B, C ] return 'A, B, (conjunction) C'"""
    if not items:
        raise ValueError("Missing list items to be formatted.")

    n = len(items)
    if n == 1:
        return items[0]
    if n == 2:
        return f"{items[0]} {conjunction} {items[1]}"

    *all_but_last, last_item = items
    return f"{', '.join(all_but_last)}, {conjunction} {last_item}"
