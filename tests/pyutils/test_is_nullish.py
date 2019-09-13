from math import inf, nan

from graphql.error import INVALID
from graphql.pyutils import is_nullish


class FakeNumpyArray:
    def __eq__(self, other):
        # Numpy arrays return an array when compared with another numpy array
        # containing the pointwise equality of the two
        if isinstance(other, FakeNumpyArray):
            return FakeNumpyArray()
        else:
            return False

    def __bool__(self):
        raise TypeError(
            "The truth value of an array with more than one element is "
            "ambiguous. Use a.any() or a.all()"
        )


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
        assert is_nullish(nan)

    def numpy_arrays_are_not_nullish():
        assert is_nullish(FakeNumpyArray()) is False

