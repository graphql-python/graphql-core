from inspect import (
    isclass,
    ismethod,
    isfunction,
    isgeneratorfunction,
    isgenerator,
    iscoroutinefunction,
    iscoroutine,
    isasyncgenfunction,
    isasyncgen,
)
from typing import Any

from ..error import INVALID


def inspect(value: Any) -> str:
    """Inspect value and a return string representation for error messages.

    Used to print values in error messages. We do not use repr() in order to not
    leak too much of the inner Python representation of unknown objects, and we
    do not use json.dumps() because not all objects can be serialized as JSON and
    we want to output strings with single quotes like Python repr() does it.
    """
    if isinstance(value, (bool, int, float, str)) or value in (None, INVALID):
        return repr(value)
    if isinstance(value, list):
        return f"[{', '.join(map(inspect, value))}]"
    if isinstance(value, tuple):
        if len(value) == 1:
            return f"({inspect(value[0])},)"
        return f"({', '.join(map(inspect, value))})"
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(
                map(lambda i: f"{inspect(i[0])}: {inspect(i[1])}", value.items())
            )
            + "}"
        )
    if isinstance(value, set):
        if not len(value):
            return "<empty set>"
        return "{" + ", ".join(map(inspect, value)) + "}"
    if isinstance(value, Exception):
        type_ = "exception"
        value = type(value)
    elif isclass(value):
        type_ = "exception class" if issubclass(value, Exception) else "class"
    elif ismethod(value):
        type_ = "method"
    elif iscoroutinefunction(value):
        type_ = "coroutine function"
    elif isasyncgenfunction(value):
        type_ = "async generator function"
    elif isgeneratorfunction(value):
        type_ = "generator function"
    elif isfunction(value):
        type_ = "function"
    elif iscoroutine(value):
        type_ = "coroutine"
    elif isasyncgen(value):
        type_ = "async generator"
    elif isgenerator(value):
        type_ = "generator"
    else:
        # stringify (only) the well-known GraphQL types
        from ..type import GraphQLNamedType, GraphQLScalarType, GraphQLWrappingType

        if isinstance(
            value, (GraphQLNamedType, GraphQLScalarType, GraphQLWrappingType)
        ):
            return str(value)
        # check if we have a custom inspect method
        try:
            inspect_method = value.__inspect__
            if not callable(inspect_method):
                raise AttributeError
        except AttributeError:
            pass
        else:
            return inspect_method()
        try:
            name = type(value).__name__
            if not name or "<" in name or ">" in name:
                raise AttributeError
        except AttributeError:
            return "<object>"
        else:
            return f"<{name} instance>"
    try:
        name = value.__name__
        if not name or "<" in name or ">" in name:
            raise AttributeError
    except AttributeError:
        return f"<{type_}>"
    else:
        return f"<{type_} {name}>"
