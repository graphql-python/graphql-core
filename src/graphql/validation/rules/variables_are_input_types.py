"""Variables are input types rule"""

from typing import Any

from ...error import GraphQLError
from ...language import VariableDefinitionNode, print_ast
from ...type import is_input_type
from ...utilities import type_from_ast
from . import ValidationRule

__all__ = ["VariablesAreInputTypesRule"]


class VariablesAreInputTypesRule(ValidationRule):
    """Variables are input types

    A GraphQL operation is only valid if all the variables it defines are of input types
    (scalar, enum, or input object).

    See https://spec.graphql.org/draft/#sec-Variables-Are-Input-Types

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import VariablesAreInputTypesRule
    >>> sdl = 'type Query { field(arg: ID): String } type User { name: String }'
    >>> schema = build_schema(sdl)
    >>> document = parse('query ($user: User) { field(arg: "1") }')
    >>> errors = validate(schema, document, [VariablesAreInputTypesRule])
    >>> print(errors[0].message)
    Variable '$user' cannot be non-input type 'User'.
    >>> document = parse('query ($id: ID) { field(arg: $id) }')
    >>> validate(schema, document, [VariablesAreInputTypesRule])
    []
    """

    def enter_variable_definition(
        self, node: VariableDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering a variable definition node.

        :meta private:
        """
        type_ = type_from_ast(self.context.schema, node.type)

        # If the variable type is not an input type, return an error.
        if type_ is not None and not is_input_type(type_):
            variable_name = node.variable.name.value
            type_name = print_ast(node.type)
            self.report_error(
                GraphQLError(
                    f"Variable '${variable_name}'"
                    f" cannot be non-input type '{type_name}'.",
                    node.type,
                )
            )
