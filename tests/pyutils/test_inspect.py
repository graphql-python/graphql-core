from math import nan, inf

from pytest import mark

from graphql.error import INVALID
from graphql.pyutils import inspect
from graphql import (
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLObjectType,
    GraphQLNonNull,
    GraphQLString,
)


def describe_inspect():
    def invalid():
        assert inspect(INVALID) == "<INVALID>"

    def none():
        assert inspect(None) == "None"

    def boolean():
        assert inspect(True) == "True"
        assert inspect(False) == "False"

    def string():
        assert inspect("") == "''"
        assert inspect("abc") == "'abc'"
        assert inspect('"') == repr('"')
        assert inspect("'") == repr("'")

    def number():
        assert inspect(0) == "0"
        assert inspect(0.0) == "0.0"
        assert inspect(314) == "314"
        assert inspect(3.14) == "3.14"
        assert inspect(nan) == "nan"
        assert inspect(inf) == "inf"
        assert inspect(-inf) == "-inf"

    def function():
        assert inspect(lambda: 0) == "<function>"

        def test_func():
            return None

        assert inspect(test_func) == "<function test_func>"

    def exception():
        assert inspect(ValueError) == "<exception class ValueError>"
        assert inspect(ArithmeticError(42)) == "<exception ArithmeticError>"

    def class_and_method():
        class TestClass:
            def test_method(self):
                return None

        assert inspect(TestClass) == "<class TestClass>"
        assert inspect(TestClass()) == "<TestClass instance>"
        assert inspect(TestClass.test_method) == "<function test_method>"
        assert inspect(TestClass().test_method) == "<method test_method>"

    def unknown_object():
        class MetaClass(type):
            __name__ = None

        class TestClass(metaclass=MetaClass):
            pass

        assert inspect(TestClass()) == "<object>"

    def generator():
        def test_generator():
            yield None

        assert inspect(test_generator) == "<generator function test_generator>"
        assert inspect(test_generator()) == "<generator test_generator>"

    @mark.asyncio
    async def coroutine():
        async def test_coroutine():
            return None

        assert inspect(test_coroutine) == "<coroutine function test_coroutine>"
        coroutine_object = test_coroutine()
        assert inspect(coroutine_object) == "<coroutine test_coroutine>"
        await coroutine_object  # avoid warning

    def async_generator():
        async def test_async_generator():
            yield None

        assert inspect(test_async_generator) == (
            "<async generator function test_async_generator>"
        )
        assert inspect(test_async_generator()) == (
            "<async generator test_async_generator>"
        )

    def lists():
        assert inspect([]) == "[]"
        assert inspect([None]) == "[None]"
        assert inspect([[[None]]]) == "[[[None]]]"
        assert inspect([1, nan]) == "[1, nan]"
        assert inspect([["a", "b"], "c"]) == "[['a', 'b'], 'c']"

    def tuples():
        assert inspect(()) == "()"
        assert inspect((None,)) == "(None,)"
        assert inspect((((None,),),)) == "(((None,),),)"
        assert inspect((1, nan)) == "(1, nan)"
        assert inspect((("a", "b"), "c")) == "(('a', 'b'), 'c')"

    def mixed_lists_and_tuples():
        assert inspect(["a", ("b",)]) == "['a', ('b',)]"

    def mixed_lists_and_tuples_with_various_objects():
        class TestClass:
            pass

        assert inspect([TestClass, (TestClass,), ValueError()]) == (
            "[<class TestClass>, (<class TestClass>,), <exception ValueError>]"
        )

    def dicts():
        assert inspect({}) == "{}"
        assert inspect({"a": 1}) == "{'a': 1}"
        assert inspect({"a": 1, "b": 2}) == "{'a': 1, 'b': 2}"
        assert inspect({"list": [None, 0]}) == "{'list': [None, 0]}"
        assert inspect({"a": True, "b": None}) == "{'a': True, 'b': None}"

    def sets():
        assert inspect(set()) == "<empty set>"
        assert inspect({"a"}) == "{'a'}"
        assert inspect({"a", 1}) in ("{'a', 1}", "{1, 'a'}")  # sets are unordered

    def mixed_dicts_and_sets():
        assert inspect({"a": {"b"}}) == "{'a': {'b'}}"
        assert inspect({1: [], 2: (), 3: set()}) == "{1: [], 2: (), 3: <empty set>}"
        assert inspect([(set(),), {None: {()}}]) == "[(<empty set>,), {None: {()}}]"

    def mixed_dicts_and_sets_with_various_objects():
        class TestClass:
            pass

        assert inspect({TestClass: {ValueError()}, ValueError: {TestClass()}}) == (
            "{<class TestClass>: {<exception ValueError>},"
            " <exception class ValueError>: {<TestClass instance>}}"
        )

    def graphql_types():
        assert inspect(GraphQLInt) == "Int"
        assert inspect(GraphQLString) == "String"
        assert inspect(GraphQLNonNull(GraphQLString)) == "String!"
        assert inspect(GraphQLList(GraphQLString)) == "[String]"
        test_object_type = GraphQLObjectType(
            "TestObjectType", {"test": GraphQLField(GraphQLString)}
        )
        assert inspect(test_object_type) == "TestObjectType"

    def custom_inspect():
        class TestClass:
            @staticmethod
            def __inspect__():
                return "<custom magic method inspect>"

        assert inspect(TestClass()) == "<custom magic method inspect>"
