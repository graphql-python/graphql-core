"""Python Utils

This package contains dependency-free Python utility functions used throughout the
codebase.

Each utility should belong in its own file and be the default export.

These functions are not part of the module interface and are subject to change.
"""

from .convert_case import camel_to_snake, snake_to_camel
from .cached_property import cached_property
from .dedent import dedent
from .did_you_mean import did_you_mean
from .event_emitter import EventEmitter, EventEmitterAsyncIterator
from .identity_func import identity_func
from .inspect import inspect
from .is_finite import is_finite
from .is_integer import is_integer
from .is_invalid import is_invalid
from .is_nullish import is_nullish
from .awaitable_or_value import AwaitableOrValue
from .suggestion_list import suggestion_list
from .frozen_error import FrozenError
from .frozen_list import FrozenList
from .frozen_dict import FrozenDict

__all__ = [
    "camel_to_snake",
    "snake_to_camel",
    "cached_property",
    "dedent",
    "did_you_mean",
    "EventEmitter",
    "EventEmitterAsyncIterator",
    "identity_func",
    "inspect",
    "is_finite",
    "is_integer",
    "is_invalid",
    "is_nullish",
    "AwaitableOrValue",
    "suggestion_list",
    "FrozenError",
    "FrozenList",
    "FrozenDict",
]
