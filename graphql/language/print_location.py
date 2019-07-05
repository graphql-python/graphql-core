import re
from typing import List, Optional, Tuple, cast

from .ast import Location
from .location import SourceLocation, get_location
from .source import Source


__all__ = ["print_location", "print_source_location"]


def print_location(location: Location) -> str:
    """Render a helpful description of the location in the GraphQL Source document."""
    return print_source_location(
        location.source, get_location(location.source, location.start)
    )


_re_newline = re.compile(r"\r\n|[\n\r]")


def print_source_location(source: Source, source_location: SourceLocation) -> str:
    """Render a helpful description of the location in the GraphQL Source document."""
    first_line_column_offset = source.location_offset.column - 1
    body = " " * first_line_column_offset + source.body

    line_index = source_location.line - 1
    line_offset = source.location_offset.line - 1
    line_num = source_location.line + line_offset

    column_offset = first_line_column_offset if source_location.line == 1 else 0
    column_num = source_location.column + column_offset

    lines = _re_newline.split(body)  # works a bit different from splitlines()
    len_lines = len(lines)

    def get_line(index: int) -> Optional[str]:
        return lines[index] if 0 <= index < len_lines else None

    return f"{source.name}:{line_num}:{column_num}\n" + print_prefixed_lines(
        [
            (f"{line_num - 1}", get_line(line_index - 1)),
            (f"{line_num}", get_line(line_index)),
            ("", " " * (column_num - 1) + "^"),
            (f"{line_num + 1}", get_line(line_index + 1)),
        ]
    )


def print_prefixed_lines(lines: List[Tuple[str, Optional[str]]]) -> str:
    """Print lines specified like this: ("prefix", "string")"""
    existing_lines = [
        cast(Tuple[str, str], line) for line in lines if line[1] is not None
    ]
    pad_len = max(len(line[0]) for line in existing_lines)
    return "\n".join(
        map(lambda line: line[0].rjust(pad_len) + " | " + line[1], existing_lines)
    )
