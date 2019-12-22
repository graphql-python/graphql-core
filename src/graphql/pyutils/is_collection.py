from typing import Any, ByteString, Collection, Mapping, Text, ValuesView

__all__ = ["is_collection"]

collection_type: Any = Collection
if not isinstance({}.values(), Collection):  # Python < 3.7.2
    collection_type = (Collection, ValuesView)
no_collection_type: Any = (ByteString, Mapping, Text)


def is_collection(value: Any) -> bool:
    """Check if value is a collection, but not a mapping and not a string."""
    return isinstance(value, collection_type) and not isinstance(
        value, no_collection_type
    )
