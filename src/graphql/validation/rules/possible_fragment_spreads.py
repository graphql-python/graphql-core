from ...error import GraphQLError
from ...language import FragmentSpreadNode, InlineFragmentNode
from ...type import is_composite_type
from ...utilities import do_types_overlap, type_from_ast
from . import ValidationRule

__all__ = [
    "PossibleFragmentSpreadsRule",
    "type_incompatible_spread_message",
    "type_incompatible_anon_spread_message",
]


def type_incompatible_spread_message(
    frag_name: str, parent_type: str, frag_type: str
) -> str:
    return (
        f"Fragment '{frag_name}' cannot be spread here as objects"
        f" of type '{parent_type}' can never be of type '{frag_type}'."
    )


def type_incompatible_anon_spread_message(parent_type: str, frag_type: str) -> str:
    return (
        f"Fragment cannot be spread here as objects"
        f" of type '{parent_type}' can never be of type '{frag_type}'."
    )


class PossibleFragmentSpreadsRule(ValidationRule):
    """Possible fragment spread

    A fragment spread is only valid if the type condition could ever possibly be true:
    if there is a non-empty intersection of the possible parent types, and possible
    types which pass the type condition.
    """

    def enter_inline_fragment(self, node: InlineFragmentNode, *_args):
        context = self.context
        frag_type = context.get_type()
        parent_type = context.get_parent_type()
        if (
            is_composite_type(frag_type)
            and is_composite_type(parent_type)
            and not do_types_overlap(context.schema, frag_type, parent_type)
        ):
            context.report_error(
                GraphQLError(
                    type_incompatible_anon_spread_message(
                        str(parent_type), str(frag_type)
                    ),
                    node,
                )
            )

    def enter_fragment_spread(self, node: FragmentSpreadNode, *_args):
        context = self.context
        frag_name = node.name.value
        frag_type = self.get_fragment_type(frag_name)
        parent_type = context.get_parent_type()
        if (
            frag_type
            and parent_type
            and not do_types_overlap(context.schema, frag_type, parent_type)
        ):
            context.report_error(
                GraphQLError(
                    type_incompatible_spread_message(
                        frag_name, str(parent_type), str(frag_type)
                    ),
                    node,
                )
            )

    def get_fragment_type(self, name: str):
        context = self.context
        frag = context.get_fragment(name)
        if frag:
            type_ = type_from_ast(context.schema, frag.type_condition)
            if is_composite_type(type_):
                return type_
