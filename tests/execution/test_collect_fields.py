from __future__ import annotations

from graphql.execution import Executor
from graphql.execution.collect_fields import collect_fields
from graphql.language import parse
from graphql.utilities import build_schema

schema = build_schema(
    """
    type Query {
      field: String
    }
    """
)


def collect_root_fields(query: str):
    executor = Executor.build(schema, parse(query))

    assert isinstance(executor, Executor)

    query_type = schema.query_type
    assert query_type is not None

    return collect_fields(
        executor.schema,
        executor.fragments,
        executor.variable_values,
        query_type,
        executor.operation,
    )


def describe_collect_fields():
    def describe_overlapping_fragment_spreads():
        def not_collect_deferred_spread_after_non_deferred_collected():
            """Should not collect a deferred spread after a non-deferred."""
            collected = collect_root_fields(
                """
                query {
                  ...FragmentName
                  ...FragmentName @defer
                }
                fragment FragmentName on Query {
                  field
                }
                """
            )

            assert len(collected.new_defer_usages) == 0

        def not_collect_deferred_spread_after_deferred_collected():
            """Should not collect a deferred spread after a deferred one."""
            collected = collect_root_fields(
                """
                query {
                  ...FragmentName @defer
                  ...FragmentName @defer
                }
                fragment FragmentName on Query {
                  field
                }
                """
            )

            assert len(collected.new_defer_usages) == 1

        def collect_non_deferred_spread_after_deferred_collected():
            """Should collect a non-deferred spread after a deferred one."""
            collected = collect_root_fields(
                """
                query {
                  ...FragmentName @defer
                  ...FragmentName
                }
                fragment FragmentName on Query {
                  field
                }
                """
            )

            field_details_list = collected.grouped_field_set.get("field")

            assert field_details_list is not None
            assert len(field_details_list) == 2

        def not_collect_non_deferred_spread_after_non_deferred_collected():
            """Should not collect a non-deferred spread after a non-deferred."""
            collected = collect_root_fields(
                """
                query {
                  ...FragmentName
                  ...FragmentName
                }
                fragment FragmentName on Query {
                  field
                }
                """
            )

            field_details_list = collected.grouped_field_set.get("field")

            assert field_details_list is not None
            assert len(field_details_list) == 1
