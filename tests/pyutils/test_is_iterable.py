from array import array
from collections import defaultdict, namedtuple
from decimal import Decimal
from itertools import count

from graphql.pyutils import FrozenDict, FrozenList, is_collection, is_iterable


def describe_is_collection():
    def should_return_true_for_lists():
        assert is_collection([]) is True
        assert is_collection([0, 1, 2]) is True
        assert is_collection(["A", "B", "C"]) is True

    def should_return_true_for_frozen_lists():
        assert is_collection(FrozenList()) is True
        assert is_collection(FrozenList([0, 1, 2])) is True
        assert is_collection(FrozenList(["A", "B", "C"])) is True

    def should_return_true_for_tuples():
        assert is_collection(()) is True
        assert is_collection((0, 1, 1)) is True
        assert is_collection(("A", "B", "C")) is True

    def should_return_true_for_named_tuples():
        named = namedtuple("named", "A B C")
        assert is_collection(named(0, 1, 2)) is True

    def should_return_true_for_arrays():
        assert is_collection(array("b")) is True
        assert is_collection(array("b", [0, 1, 2])) is True
        assert is_collection(array("i")) is True
        assert is_collection(array("i", [0, 1, 2])) is True

    def should_return_true_for_keys_view():
        assert is_collection({}.keys()) is True
        assert is_collection({0: "A", 1: "B", 2: "C"}.keys()) is True

    def should_return_true_for_values_view():
        assert is_collection({}.values()) is True
        assert is_collection({0: "A", 1: "B", 2: "C"}.values()) is True

    def should_return_true_for_ranges():
        assert is_collection(range(10)) is True

    def should_return_false_for_range_function():
        assert is_collection(range) is False

    def should_return_false_for_generator_function():
        assert is_collection(count) is False

    def should_return_false_for_infinite_generators():
        assert is_collection(count()) is False

    def should_return_false_for_none_object():
        assert is_collection(None) is False

    def should_return_false_for_strings():
        assert is_collection("ABC") is False
        assert is_collection("0") is False
        assert is_collection("") is False

    def should_return_false_for_byte_strings():
        assert is_collection(b"ABC") is False
        assert is_collection(b"0") is False
        assert is_collection(b"") is False

    def should_return_false_for_ints():
        assert is_collection(1) is False
        assert is_collection(-1) is False
        assert is_collection(0) is False

    def should_return_false_for_floats():
        assert is_collection(1.0) is False
        assert is_collection(-1.0) is False
        assert is_collection(0.0) is False
        assert is_collection(float("NaN")) is False
        assert is_collection(float("Inf")) is False
        assert is_collection(float("-Inf")) is False

    def should_return_false_for_decimals():
        assert is_collection(Decimal("1.0")) is False
        assert is_collection(Decimal("-1.0")) is False
        assert is_collection(Decimal("0.0")) is False
        assert is_collection(Decimal("NaN")) is False
        assert is_collection(Decimal("Inf")) is False
        assert is_collection(Decimal("-Inf")) is False

    def should_return_false_for_booleans():
        assert is_collection(True) is False
        assert is_collection(False) is False

    def should_return_true_for_sets():
        assert is_collection(set()) is True
        assert is_collection({0, 1, 2}) is True
        assert is_collection({"A", "B", "C"}) is True

    def should_return_false_for_dicts():
        assert is_collection({}) is False
        assert is_collection({"__iter__": True}) is False
        assert is_collection({0: "A", 1: "B", 2: "C"}) is False

    def should_return_false_for_frozen_dicts():
        assert is_collection(FrozenDict()) is False
        assert is_collection(FrozenDict({"__iter__": True})) is False
        assert is_collection(FrozenDict({0: "A", 1: "B", 2: "C"})) is False

    def should_return_false_for_default_dicts():
        assert is_collection(defaultdict(list)) is False

    def should_return_false_for_simple_objects():
        assert is_collection(object) is False
        assert is_collection(object()) is False

    def should_return_false_for_invalid_iterator_object():
        class NoIterator:
            __iter__ = None

        assert is_collection(NoIterator) is False
        assert is_collection(NoIterator()) is False


def describe_is_iterable():
    def should_return_true_for_lists():
        assert is_iterable([]) is True
        assert is_iterable([0, 1, 2]) is True
        assert is_iterable(["A", "B", "C"]) is True

    def should_return_true_for_frozen_lists():
        assert is_iterable(FrozenList()) is True
        assert is_iterable(FrozenList([0, 1, 2])) is True
        assert is_iterable(FrozenList(["A", "B", "C"])) is True

    def should_return_true_for_tuples():
        assert is_iterable(()) is True
        assert is_iterable((0, 1, 1)) is True
        assert is_iterable(("A", "B", "C")) is True

    def should_return_true_for_named_tuples():
        named = namedtuple("named", "a b c")
        assert is_iterable(named(0, 1, 2)) is True

    def should_return_true_for_arrays():
        assert is_iterable(array("b")) is True
        assert is_iterable(array("b", [0, 1, 2])) is True
        assert is_iterable(array("i")) is True
        assert is_iterable(array("i", [0, 1, 2])) is True

    def should_return_true_for_keys_view():
        assert is_iterable({}.keys()) is True
        assert is_iterable({0: "A", 1: "B", 2: "C"}.keys()) is True

    def should_return_true_for_values_view():
        assert is_iterable({}.values()) is True
        assert is_iterable({0: "A", 1: "B", 2: "C"}.values()) is True

    def should_return_true_for_ranges():
        assert is_iterable(range(10)) is True

    def should_return_false_for_range_function():
        assert is_iterable(range) is False

    def should_return_false_for_generator_function():
        assert is_iterable(count) is False

    def should_return_true_for_infinite_generators():
        assert is_iterable(count()) is True

    def should_return_false_for_none_object():
        assert is_iterable(None) is False

    def should_return_false_for_strings():
        assert is_iterable("ABC") is False
        assert is_iterable("0") is False
        assert is_iterable("") is False

    def should_return_false_for_byte_strings():
        assert is_iterable(b"ABC") is False
        assert is_iterable(b"0") is False
        assert is_iterable(b"") is False

    def should_return_false_for_ints():
        assert is_iterable(1) is False
        assert is_iterable(-1) is False
        assert is_iterable(0) is False

    def should_return_false_for_floats():
        assert is_iterable(1.0) is False
        assert is_iterable(-1.0) is False
        assert is_iterable(0.0) is False
        assert is_iterable(float("NaN")) is False
        assert is_iterable(float("Inf")) is False
        assert is_iterable(float("-Inf")) is False

    def should_return_false_for_decimals():
        assert is_iterable(Decimal("1.0")) is False
        assert is_iterable(Decimal("-1.0")) is False
        assert is_iterable(Decimal("0.0")) is False
        assert is_iterable(Decimal("NaN")) is False
        assert is_iterable(Decimal("Inf")) is False
        assert is_iterable(Decimal("-Inf")) is False

    def should_return_false_for_booleans():
        assert is_iterable(True) is False
        assert is_iterable(False) is False

    def should_return_true_for_sets():
        assert is_iterable(set()) is True
        assert is_iterable({0, 1, 2}) is True
        assert is_iterable({"A", "B", "C"}) is True

    def should_return_false_for_dicts():
        assert is_iterable({}) is False
        assert is_iterable({"__iter__": True}) is False
        assert is_iterable({0: "A", 1: "B", 2: "C"}) is False

    def should_return_false_for_frozen_dicts():
        assert is_iterable(FrozenDict()) is False
        assert is_iterable(FrozenDict({"__iter__": True})) is False
        assert is_iterable(FrozenDict({0: "A", 1: "B", 2: "C"})) is False

    def should_return_false_for_default_dicts():
        assert is_iterable(defaultdict(list)) is False

    def should_return_false_for_simple_objects():
        assert is_iterable(object) is False
        assert is_iterable(object()) is False

    def should_return_false_for_invalid_iterator_object():
        class NoIterator:
            __iter__ = None

        assert is_iterable(NoIterator) is False
        assert is_iterable(NoIterator()) is False
