from array import array
from typing import Any, ByteString, Collection, Iterable, Mapping, Text, ValuesView


try:
    from typing import TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeGuard


__all__ = ["is_collection", "is_iterable"]

collection_types: Any = [Collection]
if not isinstance({}.values(), Collection):  # Python < 3.7.2
    collection_types.append(ValuesView)
if not issubclass(array, Collection):  # PyPy <= 7.3.9
    collection_types.append(array)
collection_types = (
    collection_types[0] if len(collection_types) == 1 else tuple(collection_types)
)
iterable_types: Any = Iterable
not_iterable_types: Any = (ByteString, Mapping, Text)


def is_collection(value: Any) -> TypeGuard[Collection]:
    """Check if value is a collection, but not a string or a mapping."""
    return isinstance(value, collection_types) and not isinstance(
        value, not_iterable_types
    )


def is_iterable(value: Any) -> TypeGuard[Iterable]:
    """Check if value is an iterable, but not a string or a mapping."""
    return isinstance(value, iterable_types) and not isinstance(
        value, not_iterable_types
    )
