from ...error import GraphQLError
from . import ValidationRule

__all__ = ['UniqueVariableNamesRule', 'duplicate_variable_message']


def duplicate_variable_message(variable_name: str) -> str:
    return f"There can be only one variable named '{variable_name}'."


class UniqueVariableNamesRule(ValidationRule):
    """Unique variable names

    A GraphQL operation is only valid if all its variables are uniquely named.
    """

    def __init__(self, context):
        super().__init__(context)
        self.known_variable_names = {}

    def enter_operation_definition(self, *_args):
        self.known_variable_names.clear()

    def enter_variable_definition(self, node, *_args):
        known_variable_names = self.known_variable_names
        variable_name = node.variable.name.value
        if variable_name in known_variable_names:
            self.report_error(GraphQLError(
                duplicate_variable_message(variable_name),
                [known_variable_names[variable_name], node.variable.name]))
        else:
            known_variable_names[variable_name] = node.variable.name
