from typing import Callable, Iterator, Dict, Tuple, Any, Iterable, Optional, cast

from inspect import isfunction
from functools import partial
from itertools import chain


from ..type import GraphQLFieldResolver


__all__ = ["MiddlewareManager", "middlewares"]

# If the provided middleware is a class, this is the attribute we will look at
MIDDLEWARE_RESOLVER_FUNCTION = "resolve"


class MiddlewareManager:
    """MiddlewareManager helps to chain resolver functions with the provided
    middleware functions and classes
    """

    __slots__ = ("middlewares", "_middleware_resolvers", "_cached_resolvers")

    _cached_resolvers: Dict[GraphQLFieldResolver, GraphQLFieldResolver]
    _middleware_resolvers: Optional[Tuple[Callable, ...]]

    def __init__(self, *middlewares: Any) -> None:
        self.middlewares = middlewares
        if middlewares:
            self._middleware_resolvers = tuple(get_middleware_resolvers(middlewares))
        else:
            self.__middleware_resolvers = None
        self._cached_resolvers = {}

    def get_field_resolver(
        self, field_resolver: GraphQLFieldResolver
    ) -> GraphQLFieldResolver:
        """Wraps the provided resolver returning a function that
        executes chains the middleware functions with the resolver function"""
        if self._middleware_resolvers is None:
            return field_resolver
        if field_resolver not in self._cached_resolvers:
            self._cached_resolvers[field_resolver] = middleware_chain(
                field_resolver, self._middleware_resolvers
            )

        return self._cached_resolvers[field_resolver]


middlewares = MiddlewareManager


def get_middleware_resolvers(middlewares: Tuple[Any, ...]) -> Iterator[Callable]:
    """Returns the functions related to the middleware classes or functions"""
    for middleware in middlewares:
        # If the middleware is a function instead of a class
        if isfunction(middleware):
            yield middleware
        resolver_func = getattr(middleware, MIDDLEWARE_RESOLVER_FUNCTION, None)
        if resolver_func is not None:
            yield resolver_func


def middleware_chain(
    func: GraphQLFieldResolver, middlewares: Iterable[Callable]
) -> GraphQLFieldResolver:
    """Reduces the current function with the provided middlewares,
    returning a new resolver function"""
    if not middlewares:
        return func
    middlewares = chain((func,), middlewares)
    last_func: Optional[GraphQLFieldResolver] = None
    for middleware in middlewares:
        last_func = partial(middleware, last_func) if last_func else middleware

    return cast(GraphQLFieldResolver, last_func)
