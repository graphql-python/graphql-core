"""Print AST"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .block_string import print_block_string
from .print_string import print_string
from .reducer import reduce

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from ..language.ast import Node

__all__ = ["print_ast"]


def print_ast(ast: Node) -> str:
    r"""Convert an AST into a string.

    The conversion is done using a set of reasonable formatting rules.

    :param ast: The GraphQL AST node to print.
    :returns: A stable string representation of the AST.

    >>> from graphql import parse, print_ast
    >>> ast = parse('{ hero { name } }')
    >>> print_ast(ast)
    '{\n  hero {\n    name\n  }\n}'
    """
    return render(reduce(ast, print_doc_ast_reducer))


# The wrapping limit applies to total string length, including newlines.
MAX_LINE_LENGTH = 80


class PrintBuffer:
    """A linked list of printed parts that is rendered at the very end."""

    __slots__ = (
        "dedent_after",
        "indent_before",
        "length",
        "lines",
        "newlines",
        "next",
        "tail",
    )

    length: int
    newlines: int
    lines: str | list[str]
    next: PrintBuffer | None
    tail: PrintBuffer
    indent_before: bool
    dedent_after: bool

    def __init__(self, value: str = "") -> None:
        self.length = len(value)
        if "\n" in value:
            lines = value.split("\n")
            self.lines = lines
            self.newlines = len(lines) - 1
        else:
            self.lines = value
            self.newlines = 0
        self.next = None
        self.tail = self
        self.indent_before = False
        self.dedent_after = False

    def append(self, result: str | PrintBuffer) -> PrintBuffer:
        if isinstance(result, str):
            if not result:
                return self
            result = PrintBuffer(result)
        self.tail.next = result
        self.tail = result.tail
        self.length += result.length
        self.newlines += result.newlines
        return self

    def indent(self) -> PrintBuffer:
        if not self.length:
            return self
        self.indent_before = True
        self.tail.dedent_after = True
        self.length += 2 * (self.newlines + 1)
        return self


EMPTY = PrintBuffer()


def render(buffer: PrintBuffer | None) -> str:
    output: list[str] = []
    append = output.append
    indentation = ""
    part = buffer
    while part is not None:
        lines = part.lines
        if part.indent_before:
            indentation += "  "
            append("  ")
        if isinstance(lines, str):
            append(lines)
        else:
            append(f"\n{indentation}".join(lines))
        if part.dedent_after:
            indentation = indentation[:-2]
        part = part.next
    return "".join(output)


def print_operation_definition(node: Any) -> PrintBuffer:
    var_defs = (
        wrap("(\n", join(node.variable_definitions, "\n"), "\n)")
        if has_multiline_items(node.variable_definitions)
        else wrap("(", join(node.variable_definitions, ", "), ")")
    )
    operation = node.operation.value
    prefix = join(
        (
            wrap("", node.description, "\n"),
            join(
                (operation, join((node.name, var_defs)), join(node.directives, " ")),
                " ",
            ),
        )
    )
    # Anonymous queries with no directives or variable definitions can use the
    # query short form.
    return join(
        (
            ""
            if operation == "query" and prefix.length == len(operation)
            else join((prefix, " ")),
            node.selection_set,
        )
    )


def print_field(node: Any) -> PrintBuffer:
    prefix = join((wrap("", node.alias, ": "), node.name))
    return join(
        (
            wrapped_line_and_args(prefix, node.arguments),
            wrap(" ", join(node.directives, " ")),
            wrap(" ", node.selection_set),
        )
    )


def print_fragment_spread(node: Any) -> PrintBuffer:
    prefix = join(("...", node.name))
    return join(
        (
            wrapped_line_and_args(prefix, node.arguments),
            wrap(" ", join(node.directives, " ")),
        )
    )


def print_list_value(node: Any) -> PrintBuffer:
    values = node.values
    if 2 + joined_length(values, ", ") > MAX_LINE_LENGTH:
        return wrap("[\n", join(values, "\n").indent(), "\n]")
    return join(("[", join(values, ", "), "]"))


def print_object_value(node: Any) -> PrintBuffer:
    fields = node.fields
    if 4 + joined_length(fields, ", ") > MAX_LINE_LENGTH:
        return block(fields)
    return join(("{ ", join(fields, ", "), " }"))


def print_string_value(node: Any) -> PrintBuffer:
    return PrintBuffer(
        print_block_string(node.value) if node.block else print_string(node.value)
    )


def print_arguments_definition(args: Collection[PrintBuffer] | None) -> PrintBuffer:
    return (
        wrap("(\n", join(args, "\n").indent(), "\n)")
        if has_multiline_items(args)
        else wrap("(", join(args, ", "), ")")
    )


print_doc_ast_reducer: dict[str, Callable[[Any], PrintBuffer]] = {
    "name": lambda node: PrintBuffer(node.value),
    "variable": lambda node: join(("$", node.name)),
    # Document
    "document": lambda node: join(node.definitions, "\n\n"),
    "operation_definition": print_operation_definition,
    "variable_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            node.variable,
            ": ",
            node.type,
            wrap(" = ", node.default_value),
            wrap(" ", join(node.directives, " ")),
        )
    ),
    "selection_set": lambda node: (
        block(node.selections) if node.selections else PrintBuffer("{}")
    ),
    "field": print_field,
    "argument": lambda node: join((node.name, ": ", node.value)),
    "fragment_argument": lambda node: join((node.name, ": ", node.value)),
    # Fragments
    "fragment_spread": print_fragment_spread,
    "inline_fragment": lambda node: join(
        (
            "...",
            wrap("on ", node.type_condition),
            join(node.directives, " "),
            node.selection_set,
        ),
        " ",
    ),
    "fragment_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            # Note: fragment variable definitions are experimental and may be changed
            # or removed in the future.
            "fragment ",
            node.name,
            wrap("(", join(node.variable_definitions, ", "), ")"),
            " on ",
            node.type_condition,
            " ",
            wrap("", join(node.directives, " "), " "),
            node.selection_set,
        )
    ),
    # Value
    "int_value": lambda node: PrintBuffer(node.value),
    "float_value": lambda node: PrintBuffer(node.value),
    "string_value": print_string_value,
    "boolean_value": lambda node: PrintBuffer("true" if node.value else "false"),
    "null_value": lambda _node: PrintBuffer("null"),
    "enum_value": lambda node: PrintBuffer(node.value),
    "list_value": print_list_value,
    "object_value": print_object_value,
    "object_field": lambda node: join((node.name, ": ", node.value)),
    # Directive
    "directive": lambda node: join(
        ("@", node.name, wrap("(", join(node.arguments, ", "), ")"))
    ),
    # Type
    "named_type": lambda node: node.name,
    "list_type": lambda node: join(("[", node.type, "]")),
    "non_null_type": lambda node: join((node.type, "!")),
    # Type System Definitions
    "schema_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join(
                ("schema", join(node.directives, " "), block(node.operation_types)), " "
            ),
        )
    ),
    "operation_type_definition": lambda node: join(
        (node.operation.value, ": ", node.type)
    ),
    "scalar_type_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join(("scalar", node.name, join(node.directives, " ")), " "),
        )
    ),
    "object_type_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join(
                (
                    "type",
                    node.name,
                    wrap("implements ", join(node.interfaces, " & ")),
                    join(node.directives, " "),
                    block(node.fields),
                ),
                " ",
            ),
        )
    ),
    "field_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            node.name,
            print_arguments_definition(node.arguments),
            ": ",
            node.type,
            wrap(" ", join(node.directives, " ")),
        )
    ),
    "input_value_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            node.name,
            ": ",
            node.type,
            wrap(" = ", node.default_value),
            wrap(" ", join(node.directives, " ")),
        )
    ),
    "interface_type_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join(
                (
                    "interface",
                    node.name,
                    wrap("implements ", join(node.interfaces, " & ")),
                    join(node.directives, " "),
                    block(node.fields),
                ),
                " ",
            ),
        )
    ),
    "union_type_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join(
                (
                    "union",
                    node.name,
                    join(node.directives, " "),
                    wrap("= ", join(node.types, " | ")),
                ),
                " ",
            ),
        )
    ),
    "enum_type_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join(
                ("enum", node.name, join(node.directives, " "), block(node.values)), " "
            ),
        )
    ),
    "enum_value_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join((node.name, join(node.directives, " ")), " "),
        )
    ),
    "input_object_type_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            join(
                ("input", node.name, join(node.directives, " "), block(node.fields)),
                " ",
            ),
        )
    ),
    "directive_definition": lambda node: join(
        (
            wrap("", node.description, "\n"),
            "directive @",
            node.name,
            print_arguments_definition(node.arguments),
            wrap(" ", join(node.directives, " ")),
            " repeatable" if node.repeatable else "",
            " on ",
            join(node.locations, " | "),
        )
    ),
    "schema_extension": lambda node: join(
        ("extend schema", join(node.directives, " "), block(node.operation_types)), " "
    ),
    "scalar_type_extension": lambda node: join(
        ("extend scalar", node.name, join(node.directives, " ")), " "
    ),
    "object_type_extension": lambda node: join(
        (
            "extend type",
            node.name,
            wrap("implements ", join(node.interfaces, " & ")),
            join(node.directives, " "),
            block(node.fields),
        ),
        " ",
    ),
    "interface_type_extension": lambda node: join(
        (
            "extend interface",
            node.name,
            wrap("implements ", join(node.interfaces, " & ")),
            join(node.directives, " "),
            block(node.fields),
        ),
        " ",
    ),
    "union_type_extension": lambda node: join(
        (
            "extend union",
            node.name,
            join(node.directives, " "),
            wrap("= ", join(node.types, " | ")),
        ),
        " ",
    ),
    "enum_type_extension": lambda node: join(
        ("extend enum", node.name, join(node.directives, " "), block(node.values)), " "
    ),
    "input_object_type_extension": lambda node: join(
        ("extend input", node.name, join(node.directives, " "), block(node.fields)), " "
    ),
    "directive_extension": lambda node: join(
        (join(("extend directive @", node.name)), join(node.directives, " ")), " "
    ),
    # Schema Coordinates
    "type_coordinate": lambda node: node.name,
    "member_coordinate": lambda node: join((node.name, wrap(".", node.member_name))),
    "argument_coordinate": lambda node: join(
        (node.name, wrap(".", node.field_name), wrap("(", node.argument_name, ":)"))
    ),
    "directive_coordinate": lambda node: join(("@", node.name)),
    "directive_argument_coordinate": lambda node: join(
        ("@", node.name, wrap("(", node.argument_name, ":)"))
    ),
}


def join(
    items: Collection[str | PrintBuffer | None] | None, separator: str = ""
) -> PrintBuffer:
    """Join the items of a given collection.

    Return an empty buffer if it is None or empty, otherwise join all items together
    separated by separator if provided.
    """
    if not items:
        return EMPTY
    result = EMPTY
    for item in items:
        if not item:
            continue
        buffer = PrintBuffer(item) if isinstance(item, str) else item
        if not buffer.length:
            continue
        if not result.length:
            result = buffer
        else:
            if separator:
                result.append(separator)
            result.append(buffer)
    return result


def joined_length(items: Collection[PrintBuffer], separator: str) -> int:
    """Get the length that the given items would have when joined."""
    length = 0
    for item in items:
        if item.length:
            length += (len(separator) if length else 0) + item.length
    return length


def block(items: Collection[PrintBuffer | None] | None) -> PrintBuffer:
    """Return items inside a block.

    Given a collection of items, return a buffer with each item on its own line,
    wrapped in an indented "{ }" block.
    """
    return wrap("{\n", join(items, "\n").indent(), "\n}")


def wrap(start: str, buffer: PrintBuffer | None, end: str = "") -> PrintBuffer:
    """Wrap buffer inside strings at start and end.

    If the buffer is not None or empty, then wrap with start and end, otherwise return
    an empty buffer.
    """
    if buffer is None or not buffer.length:
        return EMPTY
    return (
        buffer.append(end)
        if not start
        else PrintBuffer(start).append(buffer).append(end)
    )


def has_multiline_items(items: Collection[PrintBuffer] | None) -> bool:
    """Check whether one of the items in the list has multiple lines."""
    return any(item.newlines for item in items) if items else False


def wrapped_line_and_args(
    prefix: PrintBuffer, args: Collection[PrintBuffer] | None
) -> PrintBuffer:
    """Print the given prefix with its arguments, wrapping long argument lists."""
    if not args:
        return prefix
    return join(
        (
            prefix,
            wrap("(\n", join(args, "\n").indent(), "\n)")
            if prefix.length + joined_length(args, ", ") + 2 > MAX_LINE_LENGTH
            else wrap("(", join(args, ", "), ")"),
        )
    )
