from typing import Sequence, List

__all__ = ["did_you_mean"]

MAX_LENGTH = 5


def did_you_mean(suggestions: Sequence[str], sub_message: str = None) -> str:
    """Given [ A, B, C ] return ' Did you mean A, B, or C?'"""
    parts: List[str] = []
    if suggestions:
        append = parts.append
        append(" Did you mean")
        if sub_message:
            append(sub_message)
        suggestions = suggestions[:MAX_LENGTH]
        if len(suggestions) > 1:
            append(", ".join(suggestions[:-1]))
            append("or")
        append(suggestions[-1] + "?")
    return " ".join(parts)
