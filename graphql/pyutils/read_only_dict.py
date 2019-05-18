__all__ = ["ReadOnlyDict"]

from .read_only_error import ReadOnlyError


class ReadOnlyDict(dict):
    """Dictionary that can only be read, but not changed."""

    def __delitem__(self, key):
        raise ReadOnlyError

    def __setitem__(self, key, value):
        raise ReadOnlyError

    def __add__(self, value):
        return dict.__add__(self, value)

    def __iadd__(self, value):
        raise ReadOnlyError

    def clear(self):
        raise ReadOnlyError

    def pop(self, key, default=None):
        raise ReadOnlyError

    def popitem(self):
        raise ReadOnlyError

    def setdefault(self, key, default=None):
        raise ReadOnlyError

    def update(self, other=None):
        raise ReadOnlyError
