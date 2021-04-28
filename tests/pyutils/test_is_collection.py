from collections import defaultdict, namedtuple
from itertools import count

from graphql.pyutils import FrozenDict, FrozenList, is_collection


def describe_is_collection():
    def null_is_not_a_collection():
        assert is_collection(None) is False

    def a_string_is_not_a_collection():
        assert is_collection("") is False
        assert is_collection("text") is False

    def a_byte_string_is_not_a_collection():
        assert is_collection(b"") is False
        assert is_collection(b"bytes") is False

    def a_list_is_a_collection():
        assert is_collection([]) is True
        assert is_collection([1, 2, 3]) is True

    def a_tuple_is_a_collection():
        assert is_collection(()) is True
        assert is_collection((1, 2, 3)) is True

    def a_namedtuple_is_a_collection():
        named = namedtuple("named", "a b c")
        assert is_collection(named(1, 2, 3)) is True

    def a_dict_is_not_a_collection():
        assert is_collection({}) is False
        assert is_collection({1: 2, 3: 4}) is False

    def a_defaultdict_is_not_a_collection():
        assert is_collection(defaultdict(list)) is False

    def a_keys_view_is_a_collection():
        assert is_collection({}.keys()) is True
        assert is_collection({1: 2, 3: 4}.keys()) is True

    def a_values_view_is_a_collection():
        assert is_collection({}.values()) is True
        assert is_collection({1: 2, 3: 4}.values()) is True

    def a_range_is_a_collection():
        assert is_collection(range(10)) is True

    def range_function_itself_is_not_a_collection():
        assert is_collection(range) is False

    def an_infinite_generator_is_not_a_collection():
        assert is_collection(count()) is False

    def a_frozen_list_is_a_collection():
        assert is_collection(FrozenList()) is True
        assert is_collection(FrozenList([1, 2, 3])) is True

    def a_frozen_dict_is_not_a_collection():
        assert is_collection(FrozenDict()) is False
        assert is_collection(FrozenDict({1: 2, 3: 4})) is False
