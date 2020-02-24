from math import inf, nan

from graphql.error import INVALID
from graphql.pyutils import is_nullish


def describe_is_nullish():
    def null_is_nullish():
        assert is_nullish(None) is True

    def falsy_objects_are_not_nullish():
        assert is_nullish("") is False
        assert is_nullish(0) is False
        assert is_nullish([]) is False
        assert is_nullish({}) is False

    def truthy_objects_are_not_nullish():
        assert is_nullish("str") is False
        assert is_nullish(1) is False
        assert is_nullish([0]) is False
        assert is_nullish({None: None}) is False

    def inf_is_not_nullish():
        assert is_nullish(inf) is False
        assert is_nullish(-inf) is False

    def undefined_is_nullish():
        assert is_nullish(INVALID) is True

    def nan_is_nullish():
        assert is_nullish(nan) is True

    def irreflexive_objects_are_not_nullish():
        # Numpy arrays operate element-wise and the comparison operator returns arrays.
        # Similar to math.nan, they are therefore not equal to themselves. However, we
        # only want math.nan to be considered nullish, not values like numpy arrays.

        class IrreflexiveValue:
            def __eq__(self, other):
                return False

            def __bool__(self):
                return False

        value = IrreflexiveValue()
        assert value != value
        assert not value

        assert is_nullish(value) is False
