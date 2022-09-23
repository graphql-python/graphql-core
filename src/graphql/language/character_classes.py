__all__ = ["is_digit", "is_letter", "is_name_start", "is_name_continue"]


def is_digit(char: str) -> bool:
    """Check whether char is a digit

    For internal use by the lexer only.
    """
    return char.isascii() and char.isdigit()


def is_letter(char: str) -> bool:
    """Check whether char is a plain ASCII letter

    For internal use by the lexer only.
    """
    return char.isascii() and char.isalpha()


def is_name_start(char: str) -> bool:
    """Check whether char is allowed at the beginning of a GraphQL name

    For internal use by the lexer only.
    """
    return char.isascii() and (char.isalpha() or char == "_")


def is_name_continue(char: str) -> bool:
    """Check whether char is allowed in the continuation of a GraphQL name

    For internal use by the lexer only.
    """
    return char.isascii() and (char.isalnum() or char == "_")
