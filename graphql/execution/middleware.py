from functools import partial
from inspect import isfunction
from itertools import chain

from typing import Callable, Iterator, Dict, Tuple, Any, Iterable, Optional, cast

__all__ = ["MiddlewareManager"]

GraphQLFieldResolver = Callable[..., Any]


class MiddlewareManager:
    """Manager for the middleware chain.

    This class helps to wrap resolver functions with the provided middleware
    functions and/or objects. The functions take the next middleware function
    as first argument. If middleware is provided as an object, it must provide
    a method 'resolve' that is used as the middleware function.
    """

    __slots__ = "middlewares", "_middleware_resolvers", "_cached_resolvers"

    _cached_resolvers: Dict[GraphQLFieldResolver, GraphQLFieldResolver]
    _middleware_resolvers: Optional[Iterator[Callable]]

    def __init__(self, *middlewares: Any) -> None:
        self.middlewares = middlewares
        self._middleware_resolvers = (
            get_middleware_resolvers(middlewares) if middlewares else None
        )
        self._cached_resolvers = {}

    def get_field_resolver(
        self, field_resolver: GraphQLFieldResolver
    ) -> GraphQLFieldResolver:
        """Wrap the provided resolver with the middleware.

        Returns a function that chains the middleware functions with the
        provided resolver function
        """
        if self._middleware_resolvers is None:
            return field_resolver
        if field_resolver not in self._cached_resolvers:
            self._cached_resolvers[field_resolver] = middleware_chain(
                field_resolver, self._middleware_resolvers
            )
        return self._cached_resolvers[field_resolver]


def get_middleware_resolvers(middlewares: Tuple[Any, ...]) -> Iterator[Callable]:
    """Get a list of resolver functions from a list of classes or functions."""
    for middleware in middlewares:
        if isfunction(middleware):
            yield middleware
        else:  # middleware provided as object with 'resolve' method
            resolver_func = getattr(middleware, "resolve", None)
            if resolver_func is not None:
                yield resolver_func


def middleware_chain(
    func: GraphQLFieldResolver, middlewares: Iterable[Callable]
) -> GraphQLFieldResolver:
    """Chain the given function with the provided middlewares.

    Returns a new resolver function that is the chain of both.
    """
    if not middlewares:
        return func
    middlewares = chain((func,), middlewares)
    last_func: Optional[GraphQLFieldResolver] = None
    for middleware in middlewares:
        last_func = partial(middleware, last_func) if last_func else middleware
    return cast(GraphQLFieldResolver, last_func)
