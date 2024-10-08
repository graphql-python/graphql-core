"""Human-readable descriptions"""

from __future__ import annotations

from typing import Any

__all__ = [
    "Description",
    "is_description",
    "register_description",
    "unregister_description",
]


class Description:
    """Type checker for human-readable descriptions.

    By default, only ordinary strings are accepted as descriptions,
    but you can register() other classes that will also be allowed,
    e.g. to support lazy string objects that are evaluated only at runtime.
    If you register(object), any object will be allowed as description.
    """

    bases: type | tuple[type, ...] = str

    @classmethod
    def isinstance(cls, obj: Any) -> bool:
        """Check whether this is an instance of a description."""
        return isinstance(obj, cls.bases)

    @classmethod
    def register(cls, base: type) -> None:
        """Register a class that shall be accepted as a description."""
        if not isinstance(base, type):
            msg = "Only types can be registered."
            raise TypeError(msg)
        if base is object:
            cls.bases = object
        elif cls.bases is object:
            cls.bases = base
        elif not isinstance(cls.bases, tuple):
            if base is not cls.bases:
                cls.bases = (cls.bases, base)
        elif base not in cls.bases:
            cls.bases += (base,)

    @classmethod
    def unregister(cls, base: type) -> None:
        """Unregister a class that shall no more be accepted as a description."""
        if not isinstance(base, type):
            msg = "Only types can be unregistered."
            raise TypeError(msg)
        if isinstance(cls.bases, tuple):
            if base in cls.bases:  # pragma: no branch
                cls.bases = tuple(b for b in cls.bases if b is not base)
            if not cls.bases:
                cls.bases = object
            elif len(cls.bases) == 1:
                cls.bases = cls.bases[0]
        elif cls.bases is base:
            cls.bases = object


is_description = Description.isinstance
register_description = Description.register
unregister_description = Description.unregister
