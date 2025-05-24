"""Python Utils

This package contains dependency-free Python utility functions used throughout the
codebase.

Each utility should belong in its own file and be the default export.

These functions are not part of the module interface and are subject to change.
"""

from .async_reduce import async_reduce
from .gather_with_cancel import gather_with_cancel
from .convert_case import camel_to_snake, snake_to_camel
from .cached_property import cached_property
from .description import (
    Description,
    is_description,
    register_description,
    unregister_description,
)
from .did_you_mean import did_you_mean
from .format_list import or_list, and_list
from .group_by import group_by
from .identity_func import identity_func
from .inspect import inspect
from .is_awaitable import is_awaitable
from .is_iterable import is_collection, is_iterable
from .natural_compare import natural_comparison_key
from .awaitable_or_value import AwaitableOrValue
from .suggestion_list import suggestion_list
from .frozen_error import FrozenError
from .merge_kwargs import merge_kwargs
from .path import Path
from .print_path_list import print_path_list
from .simple_pub_sub import SimplePubSub, SimplePubSubIterator
from .undefined import Undefined, UndefinedType
from .ref_map import RefMap
from .ref_set import RefSet

__all__ = [
    "AwaitableOrValue",
    "Description",
    "FrozenError",
    "Path",
    "RefMap",
    "RefSet",
    "SimplePubSub",
    "SimplePubSubIterator",
    "Undefined",
    "UndefinedType",
    "and_list",
    "async_reduce",
    "cached_property",
    "camel_to_snake",
    "did_you_mean",
    "gather_with_cancel",
    "group_by",
    "identity_func",
    "inspect",
    "is_awaitable",
    "is_collection",
    "is_description",
    "is_iterable",
    "merge_kwargs",
    "natural_comparison_key",
    "or_list",
    "print_path_list",
    "register_description",
    "snake_to_camel",
    "suggestion_list",
    "unregister_description",
]
