from typing import Generator

__all__ = ["gen_fuzz_strings"]


def gen_fuzz_strings(allowed_chars: str, max_length: int) -> Generator[str, None, None]:
    """Generator that produces all possible combinations of allowed characters."""
    num_allowed_chars = len(allowed_chars)

    num_combinations = 0
    for length in range(1, max_length + 1):
        num_combinations += num_allowed_chars ** length

    yield ""  # special case for empty string
    for combination in range(num_combinations):
        permutation = ""

        left_over = combination
        while left_over >= 0:
            reminder = left_over % num_allowed_chars
            permutation = allowed_chars[reminder] + permutation
            left_over = (left_over - reminder) // num_allowed_chars - 1

        yield permutation
