from functools import wraps
from json import dumps
from typing import Collection, Optional

from .ast import Node, OperationType
from .visitor import visit, Visitor
from .block_string import print_block_string

__all__ = ["print_ast"]


def print_ast(ast: Node) -> str:
    """Convert an AST into a string.

    The conversion is done using a set of reasonable formatting rules.
    """
    return visit(ast, PrintAstVisitor())


def add_description(method):
    """Decorator adding the description to the output of a visitor method."""

    @wraps(method)
    def wrapped(self, node, *args):
        return join([node.description, method(self, node, *args)], "\n")

    return wrapped


# noinspection PyMethodMayBeStatic
class PrintAstVisitor(Visitor):
    def leave_name(self, node, *_args):
        return node.value

    def leave_variable(self, node, *_args):
        return f"${node.name}"

    # Document

    def leave_document(self, node, *_args):
        return join(node.definitions, "\n\n") + "\n"

    def leave_operation_definition(self, node, *_args):
        name, op, selection_set = node.name, node.operation, node.selection_set
        var_defs = wrap("(", join(node.variable_definitions, ", "), ")")
        directives = join(node.directives, " ")
        # Anonymous queries with no directives or variable definitions can use the
        # query short form.
        return (
            join([op.value, join([name, var_defs]), directives, selection_set], " ")
            if (name or directives or var_defs or op != OperationType.QUERY)
            else selection_set
        )

    def leave_variable_definition(self, node, *_args):
        return (
            f"{node.variable}: {node.type}"
            f"{wrap(' = ', node.default_value)}"
            f"{wrap(' ', join(node.directives, ' '))}"
        )

    def leave_selection_set(self, node, *_args):
        return block(node.selections)

    def leave_field(self, node, *_args):
        return join(
            [
                wrap("", node.alias, ": ")
                + node.name
                + wrap("(", join(node.arguments, ", "), ")"),
                join(node.directives, " "),
                node.selection_set,
            ],
            " ",
        )

    def leave_argument(self, node, *_args):
        return f"{node.name}: {node.value}"

    # Fragments

    def leave_fragment_spread(self, node, *_args):
        return f"...{node.name}{wrap(' ', join(node.directives, ' '))}"

    def leave_inline_fragment(self, node, *_args):
        return join(
            [
                "...",
                wrap("on ", node.type_condition),
                join(node.directives, " "),
                node.selection_set,
            ],
            " ",
        )

    def leave_fragment_definition(self, node, *_args):
        # Note: fragment variable definitions are experimental and may be changed or
        # removed in the future.
        return (
            f"fragment {node.name}"
            f"{wrap('(', join(node.variable_definitions, ', '), ')')}"
            f" on {node.type_condition}"
            f" {wrap('', join(node.directives, ' '), ' ')}"
            f"{node.selection_set}"
        )

    # Value

    def leave_int_value(self, node, *_args):
        return node.value

    def leave_float_value(self, node, *_args):
        return node.value

    def leave_string_value(self, node, key, *_args):
        if node.block:
            return print_block_string(node.value, "" if key == "description" else "  ")
        return dumps(node.value)

    def leave_boolean_value(self, node, *_args):
        return "true" if node.value else "false"

    def leave_null_value(self, _node, *_args):
        return "null"

    def leave_enum_value(self, node, *_args):
        return node.value

    def leave_list_value(self, node, *_args):
        return f"[{join(node.values, ', ')}]"

    def leave_object_value(self, node, *_args):
        return f"{{{join(node.fields, ', ')}}}"

    def leave_object_field(self, node, *_args):
        return f"{node.name}: {node.value}"

    # Directive

    def leave_directive(self, node, *_args):
        return f"@{node.name}{wrap('(', join(node.arguments, ', '), ')')}"

    # Type

    def leave_named_type(self, node, *_args):
        return node.name

    def leave_list_type(self, node, *_args):
        return f"[{node.type}]"

    def leave_non_null_type(self, node, *_args):
        return f"{node.type}!"

    # Type System Definitions

    @add_description
    def leave_schema_definition(self, node, *_args):
        return join(
            ["schema", join(node.directives, " "), block(node.operation_types)], " "
        )

    def leave_operation_type_definition(self, node, *_args):
        return f"{node.operation.value}: {node.type}"

    @add_description
    def leave_scalar_type_definition(self, node, *_args):
        return join(["scalar", node.name, join(node.directives, " ")], " ")

    @add_description
    def leave_object_type_definition(self, node, *_args):
        return join(
            [
                "type",
                node.name,
                wrap("implements ", join(node.interfaces, " & ")),
                join(node.directives, " "),
                block(node.fields),
            ],
            " ",
        )

    @add_description
    def leave_field_definition(self, node, *_args):
        args = node.arguments
        args = (
            wrap("(\n", indent(join(args, "\n")), "\n)")
            if has_multiline_items(args)
            else wrap("(", join(args, ", "), ")")
        )
        directives = wrap(" ", join(node.directives, " "))
        return f"{node.name}{args}: {node.type}{directives}"

    @add_description
    def leave_input_value_definition(self, node, *_args):
        return join(
            [
                f"{node.name}: {node.type}",
                wrap("= ", node.default_value),
                join(node.directives, " "),
            ],
            " ",
        )

    @add_description
    def leave_interface_type_definition(self, node, *_args):
        return join(
            [
                "interface",
                node.name,
                wrap("implements ", join(node.interfaces, " & ")),
                join(node.directives, " "),
                block(node.fields),
            ],
            " ",
        )

    @add_description
    def leave_union_type_definition(self, node, *_args):
        return join(
            [
                "union",
                node.name,
                join(node.directives, " "),
                "= " + join(node.types, " | ") if node.types else "",
            ],
            " ",
        )

    @add_description
    def leave_enum_type_definition(self, node, *_args):
        return join(
            ["enum", node.name, join(node.directives, " "), block(node.values)], " "
        )

    @add_description
    def leave_enum_value_definition(self, node, *_args):
        return join([node.name, join(node.directives, " ")], " ")

    @add_description
    def leave_input_object_type_definition(self, node, *_args):
        return join(
            ["input", node.name, join(node.directives, " "), block(node.fields)], " "
        )

    @add_description
    def leave_directive_definition(self, node, *_args):
        args = node.arguments
        args = (
            wrap("(\n", indent(join(args, "\n")), "\n)")
            if has_multiline_items(args)
            else wrap("(", join(args, ", "), ")")
        )
        repeatable = " repeatable" if node.repeatable else ""
        locations = join(node.locations, " | ")
        return f"directive @{node.name}{args}{repeatable} on {locations}"

    def leave_schema_extension(self, node, *_args):
        return join(
            ["extend schema", join(node.directives, " "), block(node.operation_types)],
            " ",
        )

    def leave_scalar_type_extension(self, node, *_args):
        return join(["extend scalar", node.name, join(node.directives, " ")], " ")

    def leave_object_type_extension(self, node, *_args):
        return join(
            [
                "extend type",
                node.name,
                wrap("implements ", join(node.interfaces, " & ")),
                join(node.directives, " "),
                block(node.fields),
            ],
            " ",
        )

    def leave_interface_type_extension(self, node, *_args):
        return join(
            [
                "extend interface",
                node.name,
                wrap("implements ", join(node.interfaces, " & ")),
                join(node.directives, " "),
                block(node.fields),
            ],
            " ",
        )

    def leave_union_type_extension(self, node, *_args):
        return join(
            [
                "extend union",
                node.name,
                join(node.directives, " "),
                "= " + join(node.types, " | ") if node.types else "",
            ],
            " ",
        )

    def leave_enum_type_extension(self, node, *_args):
        return join(
            ["extend enum", node.name, join(node.directives, " "), block(node.values)],
            " ",
        )

    def leave_input_object_type_extension(self, node, *_args):
        return join(
            ["extend input", node.name, join(node.directives, " "), block(node.fields)],
            " ",
        )


def join(strings: Optional[Collection[str]], separator: str = "") -> str:
    """Join strings in a given collection.

    Return an empty string if it is None or empty, otherwise join all items together
    separated by separator if provided.
    """
    return separator.join(s for s in strings if s) if strings else ""


def block(strings: Collection[str]) -> str:
    """Return strings inside a block.

    Given a collection of strings, return a string with each item on its own line,
    wrapped in an indented "{ }" block.
    """
    return "{\n" + indent(join(strings, "\n")) + "\n}" if strings else ""


def wrap(start: str, string: str, end: str = "") -> str:
    """Wrap string inside other strings at start and end.

    If the string is not None or empty, then wrap with start and end, otherwise return
    an empty string.
    """
    return f"{start}{string}{end}" if string else ""


def indent(string: str) -> str:
    """Indent string with two spaces.

    If the string is not None or empty, add two spaces at the beginning of every line
    inside the string.
    """
    return "  " + string.replace("\n", "\n  ") if string else string


def is_multiline(string: str) -> bool:
    """Check whether a string consists of multiple lines."""
    return "\n" in string


def has_multiline_items(maybe_list: Optional[Collection[str]]):
    """Check whether one of the items in the list has multiple lines."""
    return maybe_list and any(is_multiline(item) for item in maybe_list)
