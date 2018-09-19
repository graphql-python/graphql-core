from typing import Optional, Sequence

__all__ = ["or_list"]


MAX_LENGTH = 5


def or_list(items: Sequence[str]) -> Optional[str]:
    """Given [A, B, C] return 'A, B, or C'."""
    if not items:
        raise TypeError("List must not be empty")
    if len(items) == 1:
        return items[0]
    selected = items[:MAX_LENGTH]
    return ", ".join(selected[:-1]) + " or " + selected[-1]
