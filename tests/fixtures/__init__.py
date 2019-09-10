"""Fixtures for graphql tests"""
import json
from os.path import dirname, join

from pytest import fixture  # type: ignore

__all__ = [
    "kitchen_sink_query",
    "kitchen_sink_sdl",
    "big_schema_sdl",
    "big_schema_introspection_result",
]


def read_graphql(name):
    path = join(dirname(__file__), name + ".graphql")
    return open(path, encoding="utf-8").read()


def read_json(name):
    path = join(dirname(__file__), name + ".json")
    return json.load(open(path, encoding="utf-8"))


@fixture(scope="module")
def kitchen_sink_query():
    return read_graphql("kitchen_sink")


@fixture(scope="module")
def kitchen_sink_sdl():
    return read_graphql("schema_kitchen_sink")


@fixture(scope="module")
def big_schema_sdl():
    return read_graphql("github_schema")


@fixture(scope="module")
def big_schema_introspection_result():
    return read_json("github_schema")
