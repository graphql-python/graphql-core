__all__ = [
    "dedent_block_string_value",
    "print_block_string",
    "get_block_string_indentation",
]


def dedent_block_string_value(raw_string: str) -> str:
    """Produce the value of a block string from its parsed raw value.

    Similar to CoffeeScript's block string, Python's docstring trim or Ruby's
    strip_heredoc.

    This implements the GraphQL spec's BlockStringValue() static algorithm.

    Note that this is very similar to Python's inspect.cleandoc() function.
    The differences is that the latter also expands tabs to spaces and
    removes whitespace at the beginning of the first line. Python also has
    textwrap.dedent() which uses a completely different algorithm.

    For internal use only.
    """
    # Expand a block string's raw value into independent lines.
    lines = raw_string.splitlines()

    # Remove common indentation from all lines but first.
    common_indent = get_block_string_indentation(raw_string)

    if common_indent:
        lines[1:] = [line[common_indent:] for line in lines[1:]]

    # Remove leading and trailing blank lines.
    start_line = 0
    end_line = len(lines)
    while start_line < end_line and is_blank(lines[start_line]):
        start_line += 1
    while end_line > start_line and is_blank(lines[end_line - 1]):
        end_line -= 1

    # Return a string of the lines joined with U+000A.
    return "\n".join(lines[start_line:end_line])


def is_blank(s: str) -> bool:
    """Check whether string contains only space or tab characters."""
    return all(c == " " or c == "\t" for c in s)


def get_block_string_indentation(value: str) -> int:
    """Get the amount of indentation for the given block string.

    For internal use only.
    """
    is_first_line = is_empty_line = True
    indent = 0
    common_indent = None

    for c in value:
        if c in "\r\n":
            is_first_line = False
            is_empty_line = True
            indent = 0
        elif c in "\t ":
            indent += 1
        else:
            if (
                is_empty_line
                and not is_first_line
                and (common_indent is None or indent < common_indent)
            ):
                common_indent = indent
            is_empty_line = False

    return common_indent or 0


def print_block_string(value: str, prefer_multiple_lines: bool = False) -> str:
    """Print a block string in the indented block form.

    Prints a block string in the indented block form by adding a leading and
    trailing blank line. However, if a block string starts with whitespace and
    is a single-line, adding a leading blank line would strip that whitespace.

    For internal use only.
    """
    is_single_line = "\n" not in value
    has_leading_space = value.startswith(" ") or value.startswith("\t")
    has_trailing_quote = value.endswith('"')
    has_trailing_slash = value.endswith("\\")
    print_as_multiple_lines = (
        not is_single_line
        or has_trailing_quote
        or has_trailing_slash
        or prefer_multiple_lines
    )

    # Format a multi-line block quote to account for leading space.
    result = (
        "\n"
        if print_as_multiple_lines and not (is_single_line and has_leading_space)
        else ""
    ) + value
    if print_as_multiple_lines:
        result += "\n"

    return '"""' + result.replace('"""', '\\"""') + '"""'
