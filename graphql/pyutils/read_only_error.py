__all__ = ["ReadOnlyError"]


class ReadOnlyError(TypeError):
    """Error when trying to write to a read only collection."""
