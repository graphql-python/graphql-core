"""Benchmarks for pickle serialization of parsed queries.

This module benchmarks pickle serialization using a large query (~100KB)
to provide realistic performance numbers for query caching use cases.
"""

import pickle

from graphql import parse

from ..fixtures import large_query  # noqa: F401

# Parse benchmark


def test_parse_large_query(benchmark, large_query):  # noqa: F811
    """Benchmark parsing large query."""
    result = benchmark(lambda: parse(large_query, no_location=True))
    assert result is not None


# Pickle benchmarks


def test_pickle_large_query_roundtrip(benchmark, large_query):  # noqa: F811
    """Benchmark pickle roundtrip for large query AST."""
    document = parse(large_query, no_location=True)

    def roundtrip():
        encoded = pickle.dumps(document)
        return pickle.loads(encoded)

    result = benchmark(roundtrip)
    assert result == document


def test_pickle_large_query_encode(benchmark, large_query):  # noqa: F811
    """Benchmark pickle encoding for large query AST."""
    document = parse(large_query, no_location=True)
    result = benchmark(lambda: pickle.dumps(document))
    assert isinstance(result, bytes)


def test_pickle_large_query_decode(benchmark, large_query):  # noqa: F811
    """Benchmark pickle decoding for large query AST."""
    document = parse(large_query, no_location=True)
    encoded = pickle.dumps(document)

    result = benchmark(lambda: pickle.loads(encoded))
    assert result == document
