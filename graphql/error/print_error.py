import re
from functools import reduce
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .graphql_error import GraphQLError  # noqa: F401
    from ..language import Source, SourceLocation  # noqa: F401


__all__ = ["print_error"]


def print_error(error: "GraphQLError") -> str:
    """Print a GraphQLError to a string.

    The printed string will contain useful location information about the
    error's position in the source.
    """
    printed_locations: List[str] = []
    print_location = printed_locations.append
    if error.nodes:
        for node in error.nodes:
            if node.loc:
                print_location(
                    highlight_source_at_location(
                        node.loc.source, node.loc.source.get_location(node.loc.start)
                    )
                )
    elif error.source and error.locations:
        source = error.source
        for location in error.locations:
            print_location(highlight_source_at_location(source, location))
    if printed_locations:
        return "\n\n".join([error.message] + printed_locations) + "\n"
    return error.message


_re_newline = re.compile(r"\r\n|[\n\r]")


def highlight_source_at_location(source: "Source", location: "SourceLocation") -> str:
    """Highlight source at given location.

    This renders a helpful description of the location of the error in the GraphQL
    Source document.
    """
    first_line_column_offset = source.location_offset.column - 1
    body = " " * first_line_column_offset + source.body

    line_index = location.line - 1
    line_offset = source.location_offset.line - 1
    line_num = location.line + line_offset

    column_offset = first_line_column_offset if location.line == 1 else 0
    column_num = location.column + column_offset

    lines = _re_newline.split(body)  # works a bit different from splitlines()
    len_lines = len(lines)

    def get_line(index: int) -> Optional[str]:
        return lines[index] if 0 <= index < len_lines else None

    return f"{source.name} ({line_num}:{column_num})\n" + print_prefixed_lines(
        [
            (f"{line_num - 1}: ", get_line(line_index - 1)),
            (f"{line_num}: ", get_line(line_index)),
            ("", " " * (column_num - 1) + "^"),
            (f"{line_num + 1}: ", get_line(line_index + 1)),
        ]
    )


def print_prefixed_lines(lines: List[Tuple[str, Optional[str]]]) -> str:
    """Print lines specified like this: ["prefix", "string"]"""
    existing_lines = [line for line in lines if line[1] is not None]
    pad_len = reduce(lambda pad, line: max(pad, len(line[0])), existing_lines, 0)
    return "\n".join(
        map(
            lambda line: line[0].rjust(pad_len) + line[1], existing_lines  # type:ignore
        )
    )
