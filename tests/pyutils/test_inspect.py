from math import nan, inf
from contextlib import contextmanager
from importlib import import_module
from typing import Any, Dict, FrozenSet, List, Set, Tuple

from pytest import mark

from graphql.pyutils import inspect, Undefined
from graphql.type import (
    GraphQLDirective,
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLObjectType,
    GraphQLNonNull,
    GraphQLString,
)

inspect_module = import_module(inspect.__module__)


@contextmanager
def increased_recursive_depth():
    inspect_module.max_recursive_depth += 1  # type: ignore
    try:
        yield inspect
    finally:
        inspect_module.max_recursive_depth -= 1  # type: ignore


@contextmanager
def increased_str_size():
    inspect_module.max_str_size *= 2  # type: ignore
    try:
        yield inspect
    finally:
        inspect_module.max_str_size //= 2  # type: ignore


@contextmanager
def increased_list_size():
    inspect_module.max_list_size *= 2  # type: ignore
    try:
        yield inspect
    finally:
        inspect_module.max_list_size //= 2  # type: ignore


def describe_inspect():
    def inspect_invalid():
        assert inspect(Undefined) == "Undefined"

    def inspect_none():
        assert inspect(None) == "None"

    def inspect_boolean():
        assert inspect(True) == "True"
        assert inspect(False) == "False"

    def inspect_string():
        for s in "", "abc", "foo\tbar \u265e\0", "'", "'":
            assert inspect(s) == repr(s)

    def overly_large_string():
        s = "foo" * 100
        r = repr(s)
        assert inspect(s) == r[:118] + "..." + r[-119:]
        with increased_str_size():
            assert inspect(s) == r

    def inspect_bytes():
        for b in b"", b"abc", b"foo\tbar \x7f\xff\0", b"'", b"'":
            assert inspect(b) == repr(b)
            a = bytearray(b)
            assert inspect(a) == repr(a)

    def overly_many_bytes():
        b = b"foo" * 100
        r = repr(b)
        assert inspect(b) == r[:118] + "..." + r[-119:]
        a = bytearray(b)
        r = repr(a)
        assert inspect(a) == r[:118] + "..." + r[-119:]

    def inspect_numbers():
        assert inspect(0) == "0"
        assert inspect(0.0) == "0.0"
        assert inspect(314) == "314"
        assert inspect(3.14) == "3.14"
        assert inspect(complex(1, 2)) == "(1+2j)"
        assert inspect(nan) == "nan"
        assert inspect(inf) == "inf"
        assert inspect(-inf) == "-inf"

    def overly_large_int():
        n = int("123" * 100)
        r = repr(n)
        assert inspect(n) == r[:118] + "..." + r[-119:]
        with increased_str_size():
            assert inspect(n) == r

    def inspect_function():
        assert inspect(lambda: 0) == "<function>"  # pragma: no cover

        def test_func():
            pass

        assert inspect(test_func) == "<function test_func>"

    def inspect_exception():
        assert inspect(ValueError) == "<exception class ValueError>"
        assert inspect(ArithmeticError(42)) == "<exception ArithmeticError>"

    def inspect_class_and_method():
        class TestClass:
            def test_method(self):
                pass

        assert inspect(TestClass) == "<class TestClass>"
        assert inspect(TestClass()) == "<TestClass instance>"
        assert inspect(TestClass.test_method) == "<function test_method>"
        assert inspect(TestClass().test_method) == "<method test_method>"

    def inspect_unknown_object():
        class MetaClass(type):
            __name__ = ""

        class TestClass(metaclass=MetaClass):
            pass

        assert inspect(TestClass()) == "<object>"

    def inspect_generator():
        def test_generator():
            yield None  # pragma: no cover

        assert inspect(test_generator) == "<generator function test_generator>"
        assert inspect(test_generator()) == "<generator test_generator>"

    @mark.asyncio
    async def inspect_coroutine():
        async def test_coroutine():
            pass

        assert inspect(test_coroutine) == "<coroutine function test_coroutine>"
        coroutine_object = test_coroutine()
        assert inspect(coroutine_object) == "<coroutine test_coroutine>"
        await coroutine_object  # avoid warning

    def inspect_async_generator():
        async def test_async_generator():
            yield None  # pragma: no cover

        assert inspect(test_async_generator) == (
            "<async generator function test_async_generator>"
        )
        assert inspect(test_async_generator()) == (
            "<async generator test_async_generator>"
        )

    def inspect_lists():
        assert inspect([]) == "[]"
        assert inspect([None]) == "[None]"
        assert inspect([[None]]) == "[[None]]"
        assert inspect([1, nan]) == "[1, nan]"
        assert inspect([["a", "b"], "c"]) == "[['a', 'b'], 'c']"

    def inspect_overly_large_list():
        s: List[int] = list(range(20))
        assert inspect(s) == "[0, 1, 2, 3, 4, ..., 16, 17, 18, 19]"
        with increased_list_size():
            assert inspect(s) == repr(s)

    def inspect_overly_nested_list():
        s: List[List[List]] = [[[]]]
        assert inspect(s) == "[[[]]]"
        s = [[[1, 2, 3]]]
        assert inspect(s) == "[[[...]]]"
        with increased_recursive_depth():
            assert inspect(s) == repr(s)

    def inspect_recursive_list():
        s: List[Any] = [1, 2, 3]
        s[1] = s
        assert inspect(s) == "[1, [...], 3]"

    def inspect_tuples():
        assert inspect(()) == "()"
        assert inspect((None,)) == "(None,)"
        assert inspect(((None,),)) == "((None,),)"
        assert inspect((1, nan)) == "(1, nan)"
        assert inspect((("a", "b"), "c")) == "(('a', 'b'), 'c')"

    def inspect_overly_large_tuple():
        s = tuple(range(20))
        assert inspect(s) == "(0, 1, 2, 3, 4, ..., 16, 17, 18, 19)"
        with increased_list_size():
            assert inspect(s) == repr(s)

    def inspect_overly_nested_tuple():
        s: Tuple[Tuple[Tuple]] = (((),),)
        assert inspect(s) == "(((),),)"
        s = (((1, 2, 3),),)
        assert inspect(s) == "(((...),),)"
        with increased_recursive_depth():
            assert inspect(s) == repr(s)

    def inspect_recursive_tuple():
        s: List[Any] = [1, 2, 3]
        s[1] = s
        t = tuple(s)
        assert inspect(t) == "(1, [1, [...], 3], 3)"

    def mixed_lists_and_tuples():
        assert inspect(["a", ("b",)]) == "['a', ('b',)]"

    def mixed_lists_and_tuples_with_various_objects():
        class TestClass:
            pass

        assert inspect([TestClass, (TestClass,), ValueError()]) == (
            "[<class TestClass>, (<class TestClass>,), <exception ValueError>]"
        )

    def inspect_dicts():
        assert inspect({}) == "{}"
        assert inspect({"a": 1}) == "{'a': 1}"
        assert inspect({"a": 1, "b": 2}) == "{'a': 1, 'b': 2}"
        assert inspect({"list": [None, 0]}) == "{'list': [None, 0]}"
        assert inspect({"a": True, "b": None}) == "{'a': True, 'b': None}"

    def inspect_overly_large_dict():
        s = dict(zip((chr(97 + i) for i in range(20)), range(20)))
        assert (
            inspect(s) == "{'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4,"
            " ..., 'q': 16, 'r': 17, 's': 18, 't': 19}"
        )
        with increased_list_size():
            assert inspect(s) == repr(s)

    def inspect_overly_nested_dict():
        s: Dict[str, Dict[str, Dict]] = {"a": {"b": {}}}
        assert inspect(s) == "{'a': {'b': {}}}"
        s = {"a": {"b": {"c": 3}}}
        assert inspect(s) == "{'a': {'b': {...}}}"
        with increased_recursive_depth():
            assert inspect(s) == repr(s)

    def inspect_recursive_dict():
        s: Dict[int, Any] = {}
        s[1] = s
        assert inspect(s) == "{1: {...}}"

    def inspect_sets():
        assert inspect(set()) == "set()"
        assert inspect({"a"}) == "{'a'}"
        assert inspect({"a", 1}) in ("{'a', 1}", "{1, 'a'}")  # sets are unordered

    def inspect_overly_large_set():
        s = set(range(20))
        r = inspect(s)
        assert r.startswith("{") and r.endswith("}")
        assert "..., " in r and "5" not in s  # sets are unordered
        assert len(r) == 36
        with increased_list_size():
            assert inspect(s) == repr(s)

    def inspect_overly_nested_set():
        s: List[List[Set]] = [[set()]]
        assert inspect(s) == "[[set()]]"
        s = [[{1, 2, 3}]]
        assert inspect(s) == "[[set(...)]]"
        with increased_recursive_depth():
            assert inspect(s) == repr(s)

    def inspect_frozensets():
        assert inspect(frozenset()) == "frozenset()"
        assert inspect(frozenset(["a"])) == "frozenset({'a'})"
        assert inspect(frozenset(["a", 1])) in (
            "frozenset({'a', 1})",
            "frozenset({1, 'a'})",
        )  # frozensets are unordered

    def inspect_overly_large_frozenset():
        s = frozenset(range(20))
        r = inspect(s)
        assert r.startswith("frozenset({") and r.endswith("})")
        assert "..., " in r and "5" not in s  # frozensets are unordered
        assert len(r) == 47
        with increased_list_size():
            assert inspect(s) == repr(s)

    def inspect_overly_nested_frozenset():
        s: FrozenSet[FrozenSet[FrozenSet]] = frozenset([frozenset([frozenset()])])
        assert inspect(s) == "frozenset({frozenset({frozenset()})})"
        s = frozenset([frozenset([frozenset([1, 2, 3])])])
        assert inspect(s) == "frozenset({frozenset({frozenset(...)})})"
        with increased_recursive_depth():
            assert inspect(s) == repr(s)

    def mixed_recursive_dict_and_list():
        s: Any = {1: []}
        s[1].append(s)
        assert inspect(s) == "{1: [{...}]}"
        s = [1, 2, 3]
        s[1] = {2: s}
        assert inspect(s) == "[1, {2: [...]}, 3]"

    def mixed_dicts_and_sets():
        assert inspect({"a": {"b"}}) == "{'a': {'b'}}"
        assert inspect({1: [], 2: (), 3: set()}) == "{1: [], 2: (), 3: set()}"
        assert inspect([(set(),), {None: {()}}]) == "[(set(),), {None: set(...)}]"

    def mixed_dicts_and_sets_with_various_objects():
        class TestClass:
            pass

        assert inspect({TestClass: {ValueError()}, ValueError: {TestClass()}}) == (
            "{<class TestClass>: {<exception ValueError>},"
            " <exception class ValueError>: {<TestClass instance>}}"
        )

    def inspect_graphql_types():
        assert inspect(GraphQLInt) == "Int"
        assert inspect(GraphQLString) == "String"
        assert inspect(GraphQLNonNull(GraphQLString)) == "String!"
        assert inspect(GraphQLList(GraphQLString)) == "[String]"
        test_object_type = GraphQLObjectType(
            "TestObjectType", {"test": GraphQLField(GraphQLString)}
        )
        assert inspect(test_object_type) == "TestObjectType"
        test_directive = GraphQLDirective("TestDirective", [])
        assert inspect(test_directive) == "@TestDirective"

    def custom_inspect():
        class TestClass:
            @staticmethod
            def __inspect__():
                return "<custom magic method inspect>"

        assert inspect(TestClass()) == "<custom magic method inspect>"

    def custom_inspect_that_uses_self():
        class TestClass:
            str = "Hello World!"

            def __inspect__(self):
                return self.str

        assert inspect(TestClass()) == "Hello World!"

    def custom_inspect_that_returns_a_list():
        class TestClass:
            @staticmethod
            def __inspect__():
                return [1, 2, 3]

        assert inspect(TestClass()) == "[1, 2, 3]"

    def custom_inspect_that_returns_an_overly_large_string():
        s = "foo" * 100

        class TestClass:
            @staticmethod
            def __inspect__():
                return s

        value = TestClass()

        assert inspect(value) == s[:118] + "..." + s[-119:]
        with increased_str_size():
            assert inspect(value) == s

    def custom_inspect_that_is_recursive():
        class TestClass:
            def __inspect__(self):
                return self

        assert inspect(TestClass()) == "<TestClass instance>"
