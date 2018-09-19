from math import inf, nan

from graphql.error import INVALID
from graphql.pyutils import is_invalid


def describe_is_invalid():
    def null_is_not_invalid():
        assert is_invalid(None) is False

    def falsy_objects_are_not_invalid():
        assert is_invalid("") is False
        assert is_invalid(0) is False
        assert is_invalid([]) is False
        assert is_invalid({}) is False

    def truthy_objects_are_not_invalid():
        assert is_invalid("str") is False
        assert is_invalid(1) is False
        assert is_invalid([0]) is False
        assert is_invalid({None: None}) is False

    def inf_is_not_invalid():
        assert is_invalid(inf) is False
        assert is_invalid(-inf) is False

    def undefined_is_invalid():
        assert is_invalid(INVALID) is True

    def nan_is_invalid():
        assert is_invalid(nan) is True
