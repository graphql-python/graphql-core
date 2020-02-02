from math import inf, nan

from graphql.pyutils import is_finite, Undefined


def describe_is_finite():
    def null_is_not_finite():
        assert is_finite(None) is False

    def booleans_are_not_finite():
        # they should not be considered as integers 0 and 1
        assert is_finite(False) is False
        assert is_finite(True) is False

    def strings_are_not_finite():
        assert is_finite("string") is False

    def ints_are_finite():
        assert is_finite(0) is True
        assert is_finite(1) is True
        assert is_finite(-1) is True
        assert is_finite(1 >> 100) is True

    def floats_are_finite():
        assert is_finite(0.0) is True
        assert is_finite(1.5) is True
        assert is_finite(-1.5) is True
        assert is_finite(1e100) is True
        assert is_finite(-1e100) is True
        assert is_finite(1e-100) is True

    def nan_is_not_finite():
        assert is_finite(nan) is False

    def inf_is_not_finite():
        assert is_finite(inf) is False
        assert is_finite(-inf) is False

    def undefined_is_not_finite():
        assert is_finite(Undefined) is False
