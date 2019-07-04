__all__ = ["INVALID", "InvalidType"]


class InvalidType(ValueError):
    """Auxiliary class for creating the INVALID singleton."""

    def __repr__(self):
        return "<INVALID>"

    def __str__(self):
        return "INVALID"

    def __hash__(self):
        return hash(InvalidType)

    def __bool__(self):
        return False

    def __eq__(self, other):
        return other is INVALID

    def __ne__(self, other):
        return not self.__eq__(other)


# Used to indicate invalid values (like "undefined" in GraphQL.js):
INVALID = InvalidType()

INVALID.__doc__ = """Symbol for invalid or undefined values

This singleton object is used to describe invalid or undefined values.
It corresponds to the ``undefined`` value in GraphQL.js.
"""
