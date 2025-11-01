"""Test utilities"""

from platform import python_implementation

from .dedent import dedent
from .gen_fuzz_strings import gen_fuzz_strings


# some tests can take much longer on PyPy
timeout_factor = 4 if python_implementation() == "PyPy" else 1


__all__ = ["dedent", "gen_fuzz_strings", "timeout_factor"]
