from typing import Any, cast

from graphql.error import GraphQLError, located_error
from graphql.language import Source


def describe_located_error():
    def throws_without_an_original_error():
        e = located_error([], [], []).original_error  # type: ignore
        assert isinstance(e, TypeError)
        assert str(e) == "Unexpected error value: []"

    def passes_graphql_error_through():
        path = ["path", 3, "to", "field"]
        e = GraphQLError("msg", None, None, None, cast("Any", path))
        assert located_error(e, [], []) == e

    def passes_graphql_error_ish_through():
        e = GraphQLError("I am a located GraphQL error")
        e.path = []
        assert located_error(e, [], []) is e

    def does_not_pass_through_elasticsearch_like_errors():
        e = Exception("I am from elasticsearch")
        cast("Any", e).path = "/something/feed/_search"
        assert located_error(e, [], []) is not e

    def handles_lazy_error_messages():
        class LazyString:
            def __str__(self) -> str:
                return "lazy"

        class LazyError(Exception):
            def __init__(self):
                self.message = LazyString()
                super().__init__()

        assert str(located_error(LazyError())) == "lazy"

    def handles_error_with_proper_source():
        class CustomError(Exception):
            source = Source("foo")

        e = located_error(CustomError())

        assert e.source
        assert isinstance(e.source, Source)
        assert e.source.body == "foo"

    def handles_error_with_str_source():
        class CustomError(Exception):
            source = "foo"

        e = located_error(CustomError())

        assert e.source
        assert isinstance(e.source, Source)
        assert e.source.body == "foo"

    def handles_error_with_non_source():
        class CustomError(Exception):
            source = Exception("Not a source")

        e = located_error(CustomError())

        assert e.source is None

    def handles_error_without_source():
        e = located_error(ValueError("No source"))

        assert e.source is None
