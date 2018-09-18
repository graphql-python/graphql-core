__all__ = ["block_string_value"]


def block_string_value(raw_string: str) -> str:
    """Produce the value of a block string from its parsed raw value.

    Similar to CoffeeScript's block string, Python's docstring trim or
    Ruby's strip_heredoc.

    This implements the GraphQL spec's BlockStringValue() static algorithm.

    """
    lines = raw_string.splitlines()

    common_indent = None
    for line in lines[1:]:
        indent = leading_whitespace(line)
        if indent < len(line) and (common_indent is None or indent < common_indent):
            common_indent = indent
        if common_indent == 0:
            break

    if common_indent:
        lines[1:] = [line[common_indent:] for line in lines[1:]]

    while lines and not lines[0].strip():
        lines = lines[1:]

    while lines and not lines[-1].strip():
        lines = lines[:-1]

    return "\n".join(lines)


def leading_whitespace(s):
    i = 0
    n = len(s)
    while i < n and s[i] in " \t":
        i += 1
    return i
