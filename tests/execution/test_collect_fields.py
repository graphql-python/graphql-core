from typing import List, cast

from graphql.execution.collect_fields import collect_fields
from graphql.language import (
    FragmentDefinitionNode,
    InlineFragmentNode,
    OperationDefinitionNode,
    SelectionSetNode,
    parse,
)
from graphql.type import assert_object_type
from graphql.utilities import build_schema


def describe_collect_fields_selection_set_visitor():
    def visits_each_collected_selection_set_in_traversal_order():
        schema = build_schema(
            "type Query { first: String, second: String, third: String }"
        )
        document = parse(
            "query { first ...F ... on Query { third } }"
            " fragment F on Query { second }"
        )
        operation = cast(OperationDefinitionNode, document.definitions[0])
        fragment = cast(FragmentDefinitionNode, document.definitions[1])
        visited: List[SelectionSetNode] = []
        fields = collect_fields(
            schema,
            {"F": fragment},
            {},
            assert_object_type(schema.query_type),
            operation.selection_set,
            visited.append,
        )
        assert visited == [
            operation.selection_set,
            fragment.selection_set,
            cast(
                InlineFragmentNode, operation.selection_set.selections[2]
            ).selection_set,
        ]
        assert list(fields) == ["first", "second", "third"]
