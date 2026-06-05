from graphql import parse, print_ast

from ..fixtures import kitchen_sink_query  # noqa: F401


def test_print_kitchen_sink(benchmark, kitchen_sink_query):  # noqa: F811
    document = parse(
        kitchen_sink_query, experimental_client_controlled_nullability=True
    )
    result = benchmark(lambda: print_ast(document))
    assert isinstance(result, str)
