from ...error import GraphQLError
from . import ValidationRule

__all__ = ['UniqueInputFieldNamesRule', 'duplicate_input_field_message']


def duplicate_input_field_message(field_name: str) -> str:
    return f"There can only be one input field named '{field_name}'."


class UniqueInputFieldNamesRule(ValidationRule):
    """Unique input field names

    A GraphQL input object value is only valid if all supplied fields are
    uniquely named.
    """

    def __init__(self, context):
        super().__init__(context)
        self.known_names_stack = []
        self.known_names = {}

    def enter_object_value(self, *_args):
        self.known_names_stack.append(self.known_names)
        self.known_names = {}

    def leave_object_value(self, *_args):
        self.known_names = self.known_names_stack.pop()

    def enter_object_field(self, node, *_args):
        known_names = self.known_names
        field_name = node.name.value
        if field_name in known_names:
            self.report_error(GraphQLError(duplicate_input_field_message(
                field_name), [known_names[field_name], node.name]))
        else:
            known_names[field_name] = node.name
        return False
