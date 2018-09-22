from collections import defaultdict
from typing import Dict, List, Set

from ..language import (
    DocumentNode,
    ExecutableDefinitionNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    Visitor,
    visit,
)

__all__ = ["separate_operations"]


DepGraph = Dict[str, Set[str]]


def separate_operations(document_ast: DocumentNode) -> Dict[str, DocumentNode]:
    """Separate operations in a given AST document.

    This function accepts a single AST document which may contain many operations and
    fragments and returns a collection of AST documents each of which contains a single
    operation as well the fragment definitions it refers to.
    """

    # Populate metadata and build a dependency graph.
    visitor = SeparateOperations()
    visit(document_ast, visitor)
    operations = visitor.operations
    fragments = visitor.fragments
    positions = visitor.positions
    dep_graph = visitor.dep_graph

    # For each operation, produce a new synthesized AST which includes only what is
    # necessary for completing that operation.
    separated_document_asts = {}
    for operation in operations:
        operation_name = op_name(operation)
        dependencies: Set[str] = set()
        collect_transitive_dependencies(dependencies, dep_graph, operation_name)

        # The list of definition nodes to be included for this operation, sorted to
        # retain the same order as the original document.
        definitions: List[ExecutableDefinitionNode] = [operation]
        for name in dependencies:
            definitions.append(fragments[name])
            definitions.sort(key=lambda n: positions.get(n, 0))

        separated_document_asts[operation_name] = DocumentNode(definitions=definitions)

    return separated_document_asts


class SeparateOperations(Visitor):
    def __init__(self):
        super().__init__()
        self.operations: List[OperationDefinitionNode] = []
        self.fragments: Dict[str, FragmentDefinitionNode] = {}
        self.positions: Dict[ExecutableDefinitionNode, int] = {}
        self.dep_graph: DepGraph = defaultdict(set)
        self.from_name: str = None
        self.idx = 0

    def enter_operation_definition(self, node, *_args):
        self.from_name = op_name(node)
        self.operations.append(node)
        self.positions[node] = self.idx
        self.idx += 1

    def enter_fragment_definition(self, node, *_args):
        self.from_name = node.name.value
        self.fragments[self.from_name] = node
        self.positions[node] = self.idx
        self.idx += 1

    def enter_fragment_spread(self, node, *_args):
        to_name = node.name.value
        self.dep_graph[self.from_name].add(to_name)


def op_name(operation: OperationDefinitionNode) -> str:
    """Provide the empty string for anonymous operations."""
    return operation.name.value if operation.name else ""


def collect_transitive_dependencies(
    collected: Set[str], dep_graph: DepGraph, from_name: str
) -> None:
    """Collect transitive dependencies.

    From a dependency graph, collects a list of transitive dependencies by recursing
    through a dependency graph.
    """
    immediate_deps = dep_graph[from_name]
    for to_name in immediate_deps:
        if to_name not in collected:
            collected.add(to_name)
            collect_transitive_dependencies(collected, dep_graph, to_name)
