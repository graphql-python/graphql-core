from ...error import GraphQLError
from ...language import VariableDefinitionNode, print_ast
from ...type import is_input_type
from ...utilities import type_from_ast
from . import ValidationRule

__all__ = ["VariablesAreInputTypesRule", "non_input_type_on_var_message"]


def non_input_type_on_var_message(variable_name: str, type_name: str) -> str:
    return f"Variable '${variable_name}' cannot be non-input type '{type_name}'."


class VariablesAreInputTypesRule(ValidationRule):
    """Variables are input types

    A GraphQL operation is only valid if all the variables it defines are of input types
    (scalar, enum, or input object).
    """

    def enter_variable_definition(self, node: VariableDefinitionNode, *_args):
        type_ = type_from_ast(self.context.schema, node.type)

        # If the variable type is not an input type, return an error.
        if type_ and not is_input_type(type_):
            variable_name = node.variable.name.value
            self.report_error(
                GraphQLError(
                    non_input_type_on_var_message(variable_name, print_ast(node.type)),
                    node.type,
                )
            )
