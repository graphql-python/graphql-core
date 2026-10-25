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

        def not_collect_spread_after_spread_collected_in_same_defer_context():
            """Should not collect a spread after one in the same defer context."""
            collected = collect_root_fields(
                """
                query {
                  ... @defer {
                    ...FragmentName
                    ...FragmentName
                  }
                }
                fragment FragmentName on Query {
                  field
                }
                """
            )

            assert len(collected.new_defer_usages) == 1
            field_details_list = collected.grouped_field_set.get("field")

            assert field_details_list is not None
            assert len(field_details_list) == 1

        def prevents_infinite_loops_from_circular_deferred_fragment_spreads():
            collected = collect_root_fields(
                """
                query {
                  ...FragmentOne @defer(label: "Foo")
                }
                fragment FragmentOne on Query {
                  ...FragmentTwo @defer(label: "Bar")
                  field
                }
                fragment FragmentTwo on Query {
                  ...FragmentThree @defer(label: "Baz")
                  }
                fragment FragmentThree on Query {
                  ...FragmentOne @defer(label: "Qux")
                  field
                }
                """
            )

            assert len(collected.new_defer_usages) == 4
