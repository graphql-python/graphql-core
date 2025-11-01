import warnings
from typing import Any, Optional

__all__ = ["Undefined", "UndefinedType"]


class UndefinedType(ValueError):
    """Auxiliary class for creating the Undefined singleton."""

    _instance: Optional["UndefinedType"] = None

    def __new__(cls) -> "UndefinedType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        else:
            warnings.warn("Redefinition of 'Undefined'", RuntimeWarning, stacklevel=2)
        return cls._instance

    def __reduce__(self) -> str:
        return "Undefined"

    def __repr__(self) -> str:
        return "Undefined"

    __str__ = __repr__

    def __hash__(self) -> int:
        return hash(UndefinedType)

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: Any) -> bool:
        return other is Undefined

    def __ne__(self, other: Any) -> bool:
        return not self == other


# Used to indicate undefined or invalid values (like "undefined" in JavaScript):
Undefined = UndefinedType()

Undefined.__doc__ = """Symbol for undefined values

This singleton object is used to describe undefined or invalid  values.
It can be used in places where you would use ``undefined`` in GraphQL.js.
"""
