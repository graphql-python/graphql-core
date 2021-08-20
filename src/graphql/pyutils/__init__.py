"""Python Utils

This package contains dependency-free Python utility functions used throughout the
codebase.

Each utility should belong in its own file and be the default export.

These functions are not part of the module interface and are subject to change.
"""

from .convert_case import camel_to_snake, snake_to_camel
from .cached_property import cached_property
from .description import (
    Description,
    is_description,
    register_description,
    unregister_description,
)
from .did_you_mean import did_you_mean
from .identity_func import identity_func
from .inspect import inspect
from .is_awaitable import is_awaitable
from .is_collection import is_collection
from .is_finite import is_finite
from .is_integer import is_integer
from .natural_compare import natural_comparison_key
from .awaitable_or_value import AwaitableOrValue
from .suggestion_list import suggestion_list
from .frozen_error import FrozenError
from .frozen_list import FrozenList
from .frozen_dict import FrozenDict
from .path import Path
from .print_path_list import print_path_list
from .simple_pub_sub import SimplePubSub, SimplePubSubIterator
from .undefined import Undefined, UndefinedType

__all__ = [
    "camel_to_snake",
    "snake_to_camel",
    "cached_property",
    "did_you_mean",
    "Description",
    "is_description",
    "register_description",
    "unregister_description",
    "identity_func",
    "inspect",
    "is_awaitable",
    "is_collection",
    "is_finite",
    "is_integer",
    "natural_comparison_key",
    "AwaitableOrValue",
    "suggestion_list",
    "FrozenError",
    "FrozenList",
    "FrozenDict",
    "Path",
    "print_path_list",
    "SimplePubSub",
    "SimplePubSubIterator",
    "Undefined",
    "UndefinedType",
]
