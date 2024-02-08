from itertools import product
from typing import Generator

__all__ = ["gen_fuzz_strings"]


def gen_fuzz_strings(allowed_chars: str, max_length: int) -> Generator[str, None, None]:
    """Generator that produces all possible combinations of allowed characters."""
    for length in range(max_length + 1):
        yield from map("".join, product(allowed_chars, repeat=length))
