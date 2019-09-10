from typing import Sequence, Union


def print_path_list(path: Sequence[Union[str, int]]):
    """Build a string describing the path."""
    return "".join(f"[{key}]" if isinstance(key, int) else f".{key}" for key in path)
