from typing import Awaitable

from pytest import mark, raises

from graphql.execution import MiddlewareManager, execute
from graphql.language.parser import parse
from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString


def describe_middleware():
    def describe_with_manager():
        def default():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            middlewares = MiddlewareManager()
            result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )

            assert result.data["field"] == "resolved"  # type: ignore

        def single_function():
            doc = parse("{ first second }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def first(self, _info):
                    return "one"

                def second(self, _info):
                    return "two"

            test_type = GraphQLObjectType(
                "TestType",
                {
                    "first": GraphQLField(GraphQLString),
                    "second": GraphQLField(GraphQLString),
                },
            )

            def reverse_middleware(next_, *args, **kwargs):
                return next_(*args, **kwargs)[::-1]

            middlewares = MiddlewareManager(reverse_middleware)
            result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )

            assert result.data == {"first": "eno", "second": "owt"}  # type: ignore

        def two_functions_and_field_resolvers():
            doc = parse("{ first second }")

            # noinspection PyMethodMayBeStatic
            class Data:
                first = "one"
                second = "two"

            test_type = GraphQLObjectType(
                "TestType",
                {
                    "first": GraphQLField(
                        GraphQLString, resolve=lambda obj, _info: obj.first
                    ),
                    "second": GraphQLField(
                        GraphQLString, resolve=lambda obj, _info: obj.second
                    ),
                },
            )

            def reverse_middleware(next_, *args, **kwargs):
                return next_(*args, **kwargs)[::-1]

            def capitalize_middleware(next_, *args, **kwargs):
                return next_(*args, **kwargs).capitalize()

            middlewares = MiddlewareManager(reverse_middleware, capitalize_middleware)
            result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )

            assert result.data == {"first": "Eno", "second": "Owt"}  # type: ignore

        @mark.asyncio
        async def single_async_function():
            doc = parse("{ first second }")

            # noinspection PyMethodMayBeStatic
            class Data:
                async def first(self, _info):
                    return "one"

                async def second(self, _info):
                    return "two"

            test_type = GraphQLObjectType(
                "TestType",
                {
                    "first": GraphQLField(GraphQLString),
                    "second": GraphQLField(GraphQLString),
                },
            )

            async def reverse_middleware(next_, *args, **kwargs):
                return (await next_(*args, **kwargs))[::-1]

            middlewares = MiddlewareManager(reverse_middleware)
            awaitable_result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )
            assert isinstance(awaitable_result, Awaitable)
            result = await awaitable_result
            assert result.data == {"first": "eno", "second": "owt"}

        def single_object():
            doc = parse("{ first second }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def first(self, _info):
                    return "one"

                def second(self, _info):
                    return "two"

            test_type = GraphQLObjectType(
                "TestType",
                {
                    "first": GraphQLField(GraphQLString),
                    "second": GraphQLField(GraphQLString),
                },
            )

            class ReverseMiddleware:

                # noinspection PyMethodMayBeStatic
                def resolve(self, next_, *args, **kwargs):
                    return next_(*args, **kwargs)[::-1]

            middlewares = MiddlewareManager(ReverseMiddleware())
            result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )

            assert result.data == {"first": "eno", "second": "owt"}  # type: ignore

        def skip_middleware_without_resolve_method():
            class BadMiddleware:
                pass  # no resolve method here

            assert (
                execute(
                    GraphQLSchema(
                        GraphQLObjectType(
                            "TestType",
                            {"foo": GraphQLField(GraphQLString)},
                        )
                    ),
                    parse("{ foo }"),
                    {"foo": "bar"},
                    middleware=MiddlewareManager(BadMiddleware()),
                )
                == ({"foo": "bar"}, None)
            )

        def with_function_and_object():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            def reverse_middleware(next_, *args, **kwargs):
                return next_(*args, **kwargs)[::-1]

            class CaptitalizeMiddleware:

                # noinspection PyMethodMayBeStatic
                def resolve(self, next_, *args, **kwargs):
                    return next_(*args, **kwargs).capitalize()

            middlewares = MiddlewareManager(reverse_middleware, CaptitalizeMiddleware())
            result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )
            assert result.data == {"field": "Devloser"}  # type: ignore

            middlewares = MiddlewareManager(CaptitalizeMiddleware(), reverse_middleware)
            result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )
            assert result.data == {"field": "devloseR"}  # type: ignore

        @mark.asyncio
        async def with_async_function_and_object():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                async def field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            async def reverse_middleware(next_, *args, **kwargs):
                return (await next_(*args, **kwargs))[::-1]

            class CaptitalizeMiddleware:

                # noinspection PyMethodMayBeStatic
                async def resolve(self, next_, *args, **kwargs):
                    return (await next_(*args, **kwargs)).capitalize()

            middlewares = MiddlewareManager(reverse_middleware, CaptitalizeMiddleware())
            awaitable_result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )
            assert isinstance(awaitable_result, Awaitable)
            result = await awaitable_result
            assert result.data == {"field": "Devloser"}

            middlewares = MiddlewareManager(CaptitalizeMiddleware(), reverse_middleware)
            awaitable_result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )
            assert isinstance(awaitable_result, Awaitable)
            result = await awaitable_result
            assert result.data == {"field": "devloseR"}

    def describe_without_manager():
        def no_middleware():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            result = execute(GraphQLSchema(test_type), doc, Data(), middleware=None)

            assert result.data["field"] == "resolved"  # type: ignore

        def empty_middleware_list():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            result = execute(GraphQLSchema(test_type), doc, Data(), middleware=[])

            assert result.data["field"] == "resolved"  # type: ignore

        def bad_middleware_object():
            doc = parse("{ field }")

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                execute(
                    GraphQLSchema(test_type),
                    doc,
                    None,
                    middleware={"bad": "value"},  # type: ignore
                )

            assert str(exc_info.value) == (
                "Middleware must be passed as a list or tuple of functions"
                " or objects, or as a single MiddlewareManager object."
                " Got {'bad': 'value'} instead."
            )

        def list_of_functions():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            log = []

            class LogMiddleware:
                def __init__(self, name):
                    self.name = name

                # noinspection PyMethodMayBeStatic
                def resolve(self, next_, *args, **kwargs):
                    log.append(f"enter {self.name}")
                    value = next_(*args, **kwargs)
                    log.append(f"exit {self.name}")
                    return value

            middlewares = [LogMiddleware("A"), LogMiddleware("B"), LogMiddleware("C")]

            result = execute(
                GraphQLSchema(test_type), doc, Data(), middleware=middlewares
            )
            assert result.data == {"field": "resolved"}  # type: ignore

            assert log == [
                "enter C",
                "enter B",
                "enter A",
                "exit A",
                "exit B",
                "exit C",
            ]
