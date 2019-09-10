from graphql import parse, DocumentNode

# noinspection PyUnresolvedReferences
from ..fixtures import kitchen_sink_query  # noqa: F401


def test_parse_kitchen_sink(benchmark, kitchen_sink_query):  # noqa: F811
    query = benchmark(lambda: parse(kitchen_sink_query))
    assert isinstance(query, DocumentNode)
