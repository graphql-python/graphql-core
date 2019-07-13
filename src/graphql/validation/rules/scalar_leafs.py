from ...error import GraphQLError
from ...language import FieldNode
from ...type import get_named_type, is_leaf_type
from . import ValidationRule

__all__ = [
    "ScalarLeafsRule",
    "no_subselection_allowed_message",
    "required_subselection_message",
]


def no_subselection_allowed_message(field_name: str, type_: str) -> str:
    return (
        f"Field '{field_name}' must not have a sub selection"
        f" since type '{type_}' has no subfields."
    )


def required_subselection_message(field_name: str, type_: str) -> str:
    return (
        f"Field '{field_name}' of type '{type_}' must have a"
        " sub selection of subfields."
        f" Did you mean '{field_name} {{ ... }}'?"
    )


class ScalarLeafsRule(ValidationRule):
    """Scalar leafs

    A GraphQL document is valid only if all leaf fields (fields without sub selections)
    are of scalar or enum types.
    """

    def enter_field(self, node: FieldNode, *_args):
        type_ = self.context.get_type()
        if type_:
            selection_set = node.selection_set
            if is_leaf_type(get_named_type(type_)):
                if selection_set:
                    self.report_error(
                        GraphQLError(
                            no_subselection_allowed_message(
                                node.name.value, str(type_)
                            ),
                            selection_set,
                        )
                    )
            elif not selection_set:
                self.report_error(
                    GraphQLError(
                        required_subselection_message(node.name.value, str(type_)), node
                    )
                )
