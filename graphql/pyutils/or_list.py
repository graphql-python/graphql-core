from typing import Optional, Sequence

__all__ = ["or_list"]


MAX_LENGTH = 5


def or_list(items: Sequence[str]) -> Optional[str]:
    """Given [A, B, C] return 'A, B, or C'."""
    if not items:
        raise ValueError

    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + " or " + items[1]

    *selected, last_item = items[:MAX_LENGTH]
    return ", ".join(selected) + " or " + last_item
