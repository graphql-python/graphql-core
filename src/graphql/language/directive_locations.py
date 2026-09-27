from enum import Enum

__all__ = ["DirectiveLocation"]


class DirectiveLocation(Enum):
    """The enum type representing the directive location values."""

    # Request Definitions
    QUERY = "query"
    """Directive location for query operations."""
    MUTATION = "mutation"
    """Directive location for mutation operations."""
    SUBSCRIPTION = "subscription"
    """Directive location for subscription operations."""
    FIELD = "field"
    """Directive location for field selections."""
    FRAGMENT_DEFINITION = "fragment definition"
    """Directive location for fragment definitions."""
    FRAGMENT_SPREAD = "fragment spread"
    """Directive location for fragment spreads."""
    VARIABLE_DEFINITION = "variable definition"
    """Directive location for variable definitions."""
    INLINE_FRAGMENT = "inline fragment"
    """Directive location for inline fragments."""

    # Type System Definitions
    SCHEMA = "schema"
    """Directive location for schema definitions and extensions."""
    SCALAR = "scalar"
    """Directive location for scalar type definitions and extensions."""
    OBJECT = "object"
    """Directive location for object type definitions and extensions."""
    FIELD_DEFINITION = "field definition"
    """Directive location for field definitions."""
    ARGUMENT_DEFINITION = "argument definition"
    """Directive location for argument definitions."""
    INTERFACE = "interface"
    """Directive location for interface type definitions and extensions."""
    UNION = "union"
    """Directive location for union type definitions and extensions."""
    ENUM = "enum"
    """Directive location for enum type definitions and extensions."""
    ENUM_VALUE = "enum value"
    """Directive location for enum value definitions."""
    INPUT_OBJECT = "input object"
    """Directive location for input object type definitions and extensions."""
    INPUT_FIELD_DEFINITION = "input field definition"
    """Directive location for input object field definitions."""
    DIRECTIVE_DEFINITION = "directive definition"
    """Directive location for directive definitions and extensions."""
