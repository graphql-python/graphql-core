"""Tests for graphql.language"""

from os.path import dirname, join

from pytest import fixture


def read_graphql(name):
    path = join(dirname(__file__), name + '.graphql')
    return open(path, encoding='utf-8').read()


@fixture(scope='module')
def kitchen_sink():
    return read_graphql('kitchen_sink')


@fixture(scope='module')
def schema_kitchen_sink():
    return read_graphql('schema_kitchen_sink')
