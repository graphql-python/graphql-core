from graphql import GraphQLSchema
from graphql.execution import execute
from graphql.language import parse
from graphql.type import GraphQLObjectType, GraphQLField, GraphQLString

schema = GraphQLSchema(
    GraphQLObjectType(
        "TestType", {"a": GraphQLField(GraphQLString), "b": GraphQLField(GraphQLString)}
    )
)


# noinspection PyMethodMayBeStatic
class RootValue:
    def a(self, *_args):
        return "a"

    def b(self, *_args):
        return "b"


def execute_test_query(query):
    document = parse(query)
    return execute(schema, document, RootValue())


def describe_execute_handles_directives():
    def describe_works_without_directives():
        def basic_query_works():
            result = execute_test_query("{ a, b }")
            assert result == ({"a": "a", "b": "b"}, None)

    def describe_works_on_scalars():
        def if_true_includes_scalar():
            result = execute_test_query("{ a, b @include(if: true) }")
            assert result == ({"a": "a", "b": "b"}, None)

        def if_false_omits_on_scalar():
            result = execute_test_query("{ a, b @include(if: false) }")
            assert result == ({"a": "a"}, None)

        def unless_false_includes_scalar():
            result = execute_test_query("{ a, b @skip(if: false) }")
            assert result == ({"a": "a", "b": "b"}, None)

        def unless_true_omits_scalar():
            result = execute_test_query("{ a, b @skip(if: true) }")
            assert result == ({"a": "a"}, None)

    def describe_works_on_fragment_spreads():
        def if_false_omits_fragment_spread():
            result = execute_test_query(
                """
                query Q {
                  a
                  ...Frag @include(if: false)
                }
                fragment Frag on TestType {
                  b
                }
                """
            )
            assert result == ({"a": "a"}, None)

        def if_true_includes_fragment_spread():
            result = execute_test_query(
                """
                query Q {
                  a
                  ...Frag @include(if: true)
                }
                fragment Frag on TestType {
                  b
                }
                """
            )
            assert result == ({"a": "a", "b": "b"}, None)

        def unless_false_includes_fragment_spread():
            result = execute_test_query(
                """
                query Q {
                  a
                  ...Frag @skip(if: false)
                }
                fragment Frag on TestType {
                  b
                }
                """
            )
            assert result == ({"a": "a", "b": "b"}, None)

        def unless_true_omits_fragment_spread():
            result = execute_test_query(
                """
                query Q {
                  a
                  ...Frag @skip(if: true)
                }
                fragment Frag on TestType {
                  b
                }
                """
            )
            assert result == ({"a": "a"}, None)

    def describe_works_on_inline_fragment():
        def if_false_omits_inline_fragment():
            result = execute_test_query(
                """
                query Q {
                  a
                  ... on TestType @include(if: false) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a"}, None)

        def if_true_includes_inline_fragment():
            result = execute_test_query(
                """
                query Q {
                  a
                  ... on TestType @include(if: true) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a", "b": "b"}, None)

        def unless_false_includes_inline_fragment():
            result = execute_test_query(
                """
                query Q {
                  a
                  ... on TestType @skip(if: false) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a", "b": "b"}, None)

        def unless_true_omits_inline_fragment():
            result = execute_test_query(
                """
                query Q {
                  a
                  ... on TestType @skip(if: true) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a"}, None)

    def describe_works_on_anonymous_inline_fragment():
        def if_false_omits_anonymous_inline_fragment():
            result = execute_test_query(
                """
                query {
                  a
                  ... @include(if: false) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a"}, None)

        def if_true_includes_anonymous_inline_fragment():
            result = execute_test_query(
                """
                query {
                  a
                  ... @include(if: true) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a", "b": "b"}, None)

        def unless_false_includes_anonymous_inline_fragment():
            result = execute_test_query(
                """
                query {
                  a
                  ... @skip(if: false) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a", "b": "b"}, None)

        def unless_true_omits_anonymous_inline_fragment():
            result = execute_test_query(
                """
                query {
                  a
                  ... @skip(if: true) {
                    b
                  }
                }
                """
            )
            assert result == ({"a": "a"}, None)

    def describe_works_with_skip_and_include_directives():
        def include_and_no_skip():
            result = execute_test_query(
                """
                {
                  a
                  b @include(if: true) @skip(if: false)
                }
                """
            )
            assert result == ({"a": "a", "b": "b"}, None)

        def include_and_skip():
            result = execute_test_query(
                """
                {
                  a
                  b @include(if: true) @skip(if: true)
                }
                """
            )
            assert result == ({"a": "a"}, None)

        def no_include_or_skip():
            result = execute_test_query(
                """
                {
                  a
                  b @include(if: false) @skip(if: false)
                }
                """
            )
            assert result == ({"a": "a"}, None)
