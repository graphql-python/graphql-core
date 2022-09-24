from typing import Optional, Sequence

from .format_list import or_list


__all__ = ["did_you_mean"]

MAX_LENGTH = 5


def did_you_mean(suggestions: Sequence[str], sub_message: Optional[str] = None) -> str:
    """Given [ A, B, C ] return ' Did you mean A, B, or C?'"""
    if not suggestions or not MAX_LENGTH:
        return ""
    message = " Did you mean "
    if sub_message:
        message += sub_message + " "
    suggestions = suggestions[:MAX_LENGTH]
    suggestion_list = or_list(
        [f"'{suggestion}'" for suggestion in suggestions[:MAX_LENGTH]]
    )
    return message + suggestion_list + "?"
