from typing import cast, Any

from graphql.error import GraphQLError, located_error

from ..utils import dedent


def describe_located_error():
    def throws_without_an_original_error():
        e = located_error([], [], []).original_error  # type: ignore
        assert isinstance(e, TypeError)
        assert str(e) == "Unexpected error value: []"

    def passes_graphql_error_through():
        path = ["path", 3, "to", "field"]
        e = GraphQLError("msg", None, None, None, cast(Any, path))
        assert located_error(e, [], []) == e

    def passes_graphql_error_ish_through():
        e = GraphQLError("I am a located GraphQL error")
        e.path = []
        assert located_error(e, [], []) is e

    def does_not_pass_through_elasticsearch_like_errors():
        e = Exception("I am from elasticsearch")
        cast(Any, e).path = "/something/feed/_search"
        assert located_error(e, [], []) is not e

    def handles_proxy_error_messages():
        class ProxyString:
            def __init__(self, value):
                self.value = value

            def __str__(self):
                return self.value

        class MyError(Exception):
            def __init__(self):
                self.message = ProxyString("Example error")
                super().__init__()

        error = located_error(MyError(), [], [])

        assert str(error) == dedent(
            """
            Example error
            """
        )
