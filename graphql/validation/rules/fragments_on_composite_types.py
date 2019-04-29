from ...error import GraphQLError
from ...language import FragmentDefinitionNode, InlineFragmentNode, print_ast
from ...type import is_composite_type
from ...utilities import type_from_ast
from . import ValidationRule

__all__ = [
    "FragmentsOnCompositeTypesRule",
    "inline_fragment_on_non_composite_error_message",
    "fragment_on_non_composite_error_message",
]


def inline_fragment_on_non_composite_error_message(type_: str) -> str:
    return f"Fragment cannot condition on non composite type '{type_}'."


def fragment_on_non_composite_error_message(frag_name: str, type_: str) -> str:
    return f"Fragment '{frag_name}' cannot condition on non composite type '{type_}'."


class FragmentsOnCompositeTypesRule(ValidationRule):
    """Fragments on composite type

    Fragments use a type condition to determine if they apply, since fragments can only
    be spread into a composite type (object, interface, or union), the type condition
    must also be a composite type.
    """

    def enter_inline_fragment(self, node: InlineFragmentNode, *_args):
        type_condition = node.type_condition
        if type_condition:
            type_ = type_from_ast(self.context.schema, type_condition)
            if type_ and not is_composite_type(type_):
                self.report_error(
                    GraphQLError(
                        inline_fragment_on_non_composite_error_message(
                            print_ast(type_condition)
                        ),
                        type_condition,
                    )
                )

    def enter_fragment_definition(self, node: FragmentDefinitionNode, *_args):
        type_condition = node.type_condition
        type_ = type_from_ast(self.context.schema, type_condition)
        if type_ and not is_composite_type(type_):
            self.report_error(
                GraphQLError(
                    fragment_on_non_composite_error_message(
                        node.name.value, print_ast(type_condition)
                    ),
                    type_condition,
                )
            )
