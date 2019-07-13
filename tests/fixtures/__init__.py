"""Fixtures for graphql tests"""

from os.path import dirname, join

from pytest import fixture  # type: ignore

__all__ = ["kitchen_sink_query", "kitchen_sink_sdl"]


def read_graphql(name):
    path = join(dirname(__file__), name + ".graphql")
    return open(path, encoding="utf-8").read()


@fixture(scope="module")
def kitchen_sink_query():
    return read_graphql("kitchen_sink")


@fixture(scope="module")
def kitchen_sink_sdl():
    return read_graphql("schema_kitchen_sink")
