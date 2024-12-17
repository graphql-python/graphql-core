"""Fixtures for graphql tests"""

import json
from gc import collect
from pathlib import Path

import pytest

__all__ = [
    "big_schema_introspection_result",
    "big_schema_sdl",
    "cleanup",
    "kitchen_sink_query",
    "kitchen_sink_sdl",
]


def cleanup(rounds=5):
    """Run garbage collector.

    This can be used to remove coroutines that were not awaited after running tests.
    """
    for _generation in range(rounds):
        collect()


def read_graphql(name):
    path = (Path(__file__).parent / name).with_suffix(".graphql")
    with path.open(encoding="utf-8") as file:
        return file.read()


def read_json(name):
    path = (Path(__file__).parent / name).with_suffix(".json")
    with path.open(encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="module")
def kitchen_sink_query():
    return read_graphql("kitchen_sink")


@pytest.fixture(scope="module")
def kitchen_sink_sdl():
    return read_graphql("schema_kitchen_sink")


@pytest.fixture(scope="module")
def big_schema_sdl():
    return read_graphql("github_schema")


@pytest.fixture(scope="module")
def big_schema_introspection_result():
    return read_json("github_schema")
