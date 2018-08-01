from ...error import GraphQLError
from . import ValidationRule

__all__ = ['UniqueFragmentNamesRule', 'duplicate_fragment_name_message']


def duplicate_fragment_name_message(frag_name: str) -> str:
    return f"There can only be one fragment named '{frag_name}'."


class UniqueFragmentNamesRule(ValidationRule):
    """Unique fragment names

    A GraphQL document is only valid if all defined fragments have unique
    names.
    """

    def __init__(self, context):
        super().__init__(context)
        self.known_fragment_names = {}

    def enter_operation_definition(self, *_args):
        return self.SKIP

    def enter_fragment_definition(self, node, *_args):
        known_fragment_names = self.known_fragment_names
        fragment_name = node.name.value
        if fragment_name in known_fragment_names:
            self.report_error(GraphQLError(
                duplicate_fragment_name_message(fragment_name),
                [known_fragment_names[fragment_name], node.name]))
        else:
            known_fragment_names[fragment_name] = node.name
        return self.SKIP
