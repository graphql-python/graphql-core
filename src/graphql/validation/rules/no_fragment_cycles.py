from typing import Dict, List, Set

from ...error import GraphQLError
from ...language import FragmentDefinitionNode, FragmentSpreadNode
from . import ASTValidationContext, ASTValidationRule

__all__ = ["NoFragmentCyclesRule", "cycle_error_message"]


def cycle_error_message(frag_name: str, spread_names: List[str]) -> str:
    via = f" via {', '.join(spread_names)}" if spread_names else ""
    return f"Cannot spread fragment '{frag_name}' within itself{via}."


class NoFragmentCyclesRule(ASTValidationRule):
    """No fragment cycles"""

    def __init__(self, context: ASTValidationContext) -> None:
        super().__init__(context)
        # Tracks already visited fragments to maintain O(N) and to ensure that
        # cycles are not redundantly reported.
        self.visited_frags: Set[str] = set()
        # List of AST nodes used to produce meaningful errors
        self.spread_path: List[FragmentSpreadNode] = []
        # Position in the spread path
        self.spread_path_index_by_name: Dict[str, int] = {}

    def enter_operation_definition(self, *_args):
        return self.SKIP

    def enter_fragment_definition(self, node: FragmentDefinitionNode, *_args):
        self.detect_cycle_recursive(node)
        return self.SKIP

    def detect_cycle_recursive(self, fragment: FragmentDefinitionNode):
        # This does a straight-forward DFS to find cycles.
        # It does not terminate when a cycle was found but continues to explore
        # the graph to find all possible cycles.
        if fragment.name.value in self.visited_frags:
            return

        fragment_name = fragment.name.value
        visited_frags = self.visited_frags
        visited_frags.add(fragment_name)

        spread_nodes = self.context.get_fragment_spreads(fragment.selection_set)
        if not spread_nodes:
            return

        spread_path = self.spread_path
        spread_path_index = self.spread_path_index_by_name
        spread_path_index[fragment_name] = len(spread_path)
        get_fragment = self.context.get_fragment

        for spread_node in spread_nodes:
            spread_name = spread_node.name.value
            cycle_index = spread_path_index.get(spread_name)

            spread_path.append(spread_node)
            if cycle_index is None:
                spread_fragment = get_fragment(spread_name)
                if spread_fragment:
                    self.detect_cycle_recursive(spread_fragment)
            else:
                cycle_path = spread_path[cycle_index:]
                fragment_names = [s.name.value for s in cycle_path[:-1]]
                self.report_error(
                    GraphQLError(
                        cycle_error_message(spread_name, fragment_names), cycle_path
                    )
                )
            spread_path.pop()

        del spread_path_index[fragment_name]
