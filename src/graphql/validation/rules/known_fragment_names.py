from ...error import GraphQLError
from ...language import FragmentSpreadNode
from . import ValidationRule

__all__ = ["KnownFragmentNamesRule", "unknown_fragment_message"]


def unknown_fragment_message(fragment_name: str) -> str:
    return f"Unknown fragment '{fragment_name}'."


class KnownFragmentNamesRule(ValidationRule):
    """Known fragment names

    A GraphQL document is only valid if all `...Fragment` fragment spreads refer to
    fragments defined in the same document.
    """

    def enter_fragment_spread(self, node: FragmentSpreadNode, *_args):
        fragment_name = node.name.value
        fragment = self.context.get_fragment(fragment_name)
        if not fragment:
            self.report_error(
                GraphQLError(unknown_fragment_message(fragment_name), node.name)
            )
