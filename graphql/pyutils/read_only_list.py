__all__ = ["ReadOnlyList"]

from .read_only_error import ReadOnlyError


class ReadOnlyList(list):
    """List that can only be read, but not changed."""

    def __delitem__(self, key):
        raise ReadOnlyError

    def __setitem__(self, key, value):
        raise ReadOnlyError

    def __add__(self, value):
        if isinstance(value, tuple):
            value = list(value)
        return list.__add__(self, value)

    def __iadd__(self, value):
        raise ReadOnlyError

    def __mul__(self, value):
        return list.__mul__(self, value)

    def __imul__(self, value):
        raise ReadOnlyError

    def append(self, x):
        raise ReadOnlyError

    def extend(self, iterable):
        raise ReadOnlyError

    def insert(self, i, x):
        raise ReadOnlyError

    def remove(self, x):
        raise ReadOnlyError

    def pop(self, i=None):
        raise ReadOnlyError

    def clear(self):
        raise ReadOnlyError

    def sort(self, *, key=None, reverse=False):
        raise ReadOnlyError

    def reverse(self):
        raise ReadOnlyError
