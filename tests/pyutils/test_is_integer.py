from math import inf, nan

from graphql.pyutils import is_integer, Undefined


def describe_is_integer():
    def null_is_not_integer():
        assert is_integer(None) is False

    def object_is_not_integer():
        assert is_integer(object()) is False

    def booleans_are_not_integer():
        assert is_integer(False) is False
        assert is_integer(True) is False

    def strings_are_not_integer():
        assert is_integer("string") is False

    def ints_are_integer():
        assert is_integer(0) is True
        assert is_integer(1) is True
        assert is_integer(-1) is True
        assert is_integer(42) is True
        assert is_integer(1234567890) is True
        assert is_integer(-1234567890) is True
        assert is_integer(1 >> 100) is True

    def floats_with_fractional_part_are_not_integer():
        assert is_integer(0.5) is False
        assert is_integer(1.5) is False
        assert is_integer(-1.5) is False
        assert is_integer(0.00001) is False
        assert is_integer(-0.00001) is False
        assert is_integer(1.00001) is False
        assert is_integer(-1.00001) is False
        assert is_integer(42.5) is False
        assert is_integer(10000.1) is False
        assert is_integer(-10000.1) is False
        assert is_integer(1234567890.5) is False
        assert is_integer(-1234567890.5) is False

    def floats_without_fractional_part_are_integer():
        assert is_integer(0.0) is True
        assert is_integer(1.0) is True
        assert is_integer(-1.0) is True
        assert is_integer(10.0) is True
        assert is_integer(-10.0) is True
        assert is_integer(42.0) is True
        assert is_integer(1234567890.0) is True
        assert is_integer(-1234567890.0) is True
        assert is_integer(1e100) is True
        assert is_integer(-1e100) is True

    def complex_is_not_integer():
        assert is_integer(1j) is False
        assert is_integer(-1j) is False
        assert is_integer(42 + 1j) is False

    def nan_is_not_integer():
        assert is_integer(nan) is False

    def inf_is_not_integer():
        assert is_integer(inf) is False
        assert is_integer(-inf) is False

    def undefined_is_not_integer():
        assert is_integer(Undefined) is False
