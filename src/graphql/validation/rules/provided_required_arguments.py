"""Provided required arguments on directives rule"""

from __future__ import annotations

from typing import Any, cast

from ...error import GraphQLError
from ...language import (
    SKIP,
    DirectiveDefinitionNode,
    DirectiveNode,
    FieldNode,
    FragmentSpreadNode,
    InputValueDefinitionNode,
    NonNullTypeNode,
    TypeNode,
    VariableDefinitionNode,
    VisitorAction,
    print_ast,
)
from ...pyutils import inspect
from ...type import (
    GraphQLArgument,
    get_named_type,
    is_introspection_type,
    is_required_argument,
    is_type,
    specified_directives,
)
from ...utilities import type_from_ast
from . import ASTValidationRule, SDLValidationContext, ValidationContext

__all__ = ["ProvidedRequiredArgumentsOnDirectivesRule", "ProvidedRequiredArgumentsRule"]


class ProvidedRequiredArgumentsOnDirectivesRule(ASTValidationRule):
    """Provided required arguments on directives

    A directive is only valid if all required (non-null without a default value)
    arguments have been provided.

    For internal use only.
    """

    context: ValidationContext | SDLValidationContext

    def __init__(self, context: ValidationContext | SDLValidationContext) -> None:
        super().__init__(context)
        required_args_map: dict[
            str, dict[str, GraphQLArgument | InputValueDefinitionNode]
        ] = {}

        schema = context.schema
        defined_directives = schema.directives if schema else specified_directives
        for directive in cast("list", defined_directives):
            required_args_map[directive.name] = {
                name: arg
                for name, arg in directive.args.items()
                if is_required_argument(arg)
            }

        ast_definitions = context.document.definitions
        for def_ in ast_definitions:
            if isinstance(def_, DirectiveDefinitionNode):
                required_args_map[def_.name.value] = {
                    arg.name.value: arg
                    for arg in filter(is_required_argument_node, def_.arguments or ())
                }

        self.required_args_map = required_args_map

    def leave_directive(self, directive_node: DirectiveNode, *_args: Any) -> None:
        # Validate on leave to allow for deeper errors to appear first.
        directive_name = directive_node.name.value
        required_args = self.required_args_map.get(directive_name)
        if required_args:
            arg_nodes = directive_node.arguments or ()
            arg_node_set = {arg.name.value for arg in arg_nodes}
            for arg_name in required_args:
                if arg_name not in arg_node_set:
                    arg_type = required_args[arg_name].type
                    arg_type_str = (
                        str(arg_type)
                        if is_type(arg_type)
                        else print_ast(cast("TypeNode", arg_type))
                    )
                    self.report_error(
                        GraphQLError(
                            f"Argument '@{directive_name}({arg_name}:)'"
                            f" of type '{arg_type_str}' is required,"
                            " but it was not provided.",
                            directive_node,
                        )
                    )


class ProvidedRequiredArgumentsRule(ProvidedRequiredArgumentsOnDirectivesRule):
    """Provided required arguments

    A field or directive is only valid if all required (non-null without a default
    value) field arguments have been provided.
    """

    context: ValidationContext

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)

    def leave_field(self, field_node: FieldNode, *_args: Any) -> VisitorAction:
        # Validate on leave to allow for deeper errors to appear first.
        field_def = self.context.get_field_def()
        if not field_def:
            return SKIP
        arg_nodes = field_node.arguments or ()

        arg_node_map = {arg.name.value: arg for arg in arg_nodes}
        for arg_name, arg_def in field_def.args.items():
            arg_node = arg_node_map.get(arg_name)
            if not arg_node and is_required_argument(arg_def):
                field_type = get_named_type(self.context.get_type())
                if field_type and is_introspection_type(field_type):
                    parent_type_str = "<meta>."
                else:
                    parent_type = self.context.get_parent_type()
                    parent_type_str = f"{parent_type}." if parent_type else ""
                self.report_error(
                    GraphQLError(
                        f"Argument '{parent_type_str}{field_node.name.value}"
                        f"({arg_name}:)' of type '{arg_def.type}' is required,"
                        " but it was not provided.",
                        field_node,
                    )
                )

        return None

    def leave_fragment_spread(
        self, spread_node: FragmentSpreadNode, *_args: Any
    ) -> VisitorAction:
        # Validate on leave to allow for deeper errors to appear first.
        fragment_signature = self.context.get_fragment_signature()
        if not fragment_signature:
            return SKIP

        provided_args = {arg.name.value for arg in spread_node.arguments or ()}
        for (
            var_name,
            variable_definition,
        ) in fragment_signature.variable_definitions.items():
            if var_name not in provided_args and is_required_argument_node(
                variable_definition
            ):
                arg_type = type_from_ast(self.context.schema, variable_definition.type)
                self.report_error(
                    GraphQLError(
                        f"Fragment '{spread_node.name.value}' argument"
                        f" '{var_name}' of type '{inspect(arg_type)}' is required,"
                        " but it was not provided.",
                        spread_node,
                    )
                )

        return None


def is_required_argument_node(
    arg: InputValueDefinitionNode | VariableDefinitionNode,
) -> bool:
    return isinstance(arg.type, NonNullTypeNode) and arg.default_value is None
