# Code taken from https://github.com/bottlepy/bottle

__all__ = ["cached_property"]


class CachedProperty:
    """A cached property.

    A property that is only computed once per instance and then replaces itself with an
    ordinary attribute. Deleting the attribute resets the property.
    """

    def __init__(self, func):
        self.__doc__ = getattr(func, "__doc__")
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


cached_property = CachedProperty
