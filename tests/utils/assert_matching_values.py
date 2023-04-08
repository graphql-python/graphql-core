from typing import TypeVar


__all__ = ["assert_matching_values"]

T = TypeVar("T")


def assert_matching_values(*values: T) -> T:
    """Test that all values in the sequence are equal."""
    first_value, *remaining_values = values
    for value in remaining_values:
        assert value == first_value
    return first_value
