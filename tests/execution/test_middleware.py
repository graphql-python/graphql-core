from typing import Awaitable, cast

import pytest
from graphql.execution import Middleware, MiddlewareManager, execute
from graphql.language.parser import parse
from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString

def _create_schema(tp: GraphQLObjectType, is_subscription: bool) -> GraphQLSchema:
    if is_subscription:
        noop_type = GraphQLObjectType("Noop", {"noop": GraphQLField(GraphQLString, resolve=lambda *_: "noop")})
        return GraphQLSchema(query=noop_type, subscription=tp)
    return GraphQLSchema(tp)
@pytest.mark.parametrize("is_subscription", [False, True], ids=["query", "subscription"])
def test_describe_middleware(is_subscription: bool):

    def test_test_describe_with_manager():
        def test_default():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def test_field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            middlewares = MiddlewareManager()
            result = execute(
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )

            assert result.data["field"] == "resolved"  # type: ignore

        def test_single_function():
            doc = parse("{ first second }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def test_first(self, _info):
                    return "one"

                def test_second(self, _info):
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
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )

            assert result.data == {"first": "eno", "second": "owt"}  # type: ignore

        def test_two_functions_and_field_resolvers():
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
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )

            assert result.data == {"first": "Eno", "second": "Owt"}  # type: ignore

        @pytest.mark.asyncio()
        async def test_single_async_function():
            doc = parse("{ first second }")

            # noinspection PyMethodMayBeStatic
            class Data:
                async def test_first(self, _info):
                    return "one"

                async def test_second(self, _info):
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
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )
            assert isinstance(awaitable_result, Awaitable)
            result = await awaitable_result
            assert result.data == {"first": "eno", "second": "owt"}

        def test_single_object():
            doc = parse("{ first second }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def test_first(self, _info):
                    return "one"

                def test_second(self, _info):
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
                def test_resolve(self, next_, *args, **kwargs):
                    return next_(*args, **kwargs)[::-1]

            middlewares = MiddlewareManager(ReverseMiddleware())
            result = execute(
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )

            assert result.data == {"first": "eno", "second": "owt"}  # type: ignore

        def test_skip_middleware_without_resolve_method():
            class BadMiddleware:
                pass  # no resolve method here

            assert execute(
                GraphQLSchema(
                    GraphQLObjectType(
                        "TestType",
                        {"foo": GraphQLField(GraphQLString)},
                    )
                ),
                parse("{ foo }"),
                {"foo": "bar"},
                middleware=MiddlewareManager(BadMiddleware()),
            ) == ({"foo": "bar"}, None)

        def test_with_function_and_object():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def test_field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            def reverse_middleware(next_, *args, **kwargs):
                return next_(*args, **kwargs)[::-1]

            class CaptitalizeMiddleware:
                # noinspection PyMethodMayBeStatic
                def test_resolve(self, next_, *args, **kwargs):
                    return next_(*args, **kwargs).capitalize()

            middlewares = MiddlewareManager(reverse_middleware, CaptitalizeMiddleware())
            result = execute(
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )
            assert result.data == {"field": "Devloser"}  # type: ignore

            middlewares = MiddlewareManager(CaptitalizeMiddleware(), reverse_middleware)
            result = execute(
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )
            assert result.data == {"field": "devloseR"}  # type: ignore

        @pytest.mark.asyncio()
        async def test_with_async_function_and_object():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                async def test_field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            async def reverse_middleware(next_, *args, **kwargs):
                return (await next_(*args, **kwargs))[::-1]

            class CaptitalizeMiddleware:
                # noinspection PyMethodMayBeStatic
                async def test_resolve(self, next_, *args, **kwargs):
                    return (await next_(*args, **kwargs)).capitalize()

            middlewares = MiddlewareManager(reverse_middleware, CaptitalizeMiddleware())
            awaitable_result = execute(
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )
            assert isinstance(awaitable_result, Awaitable)
            result = await awaitable_result
            assert result.data == {"field": "Devloser"}

            middlewares = MiddlewareManager(CaptitalizeMiddleware(), reverse_middleware)
            awaitable_result = execute(
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
            )
            assert isinstance(awaitable_result, Awaitable)
            result = await awaitable_result
            assert result.data == {"field": "devloseR"}

    def test_describe_without_manager():
        def test_no_middleware():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def test_field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            result = execute(_create_schema(test_type, is_subscription), doc, Data(), middleware=None)

            assert result.data["field"] == "resolved"  # type: ignore

        def test_empty_middleware_list():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def test_field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            result = execute(_create_schema(test_type, is_subscription), doc, Data(), middleware=[])

            assert result.data["field"] == "resolved"  # type: ignore

        def test_bad_middleware_object():
            doc = parse("{ field }")

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            with pytest.raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                execute(
                    _create_schema(test_type, is_subscription),
                    doc,
                    None,
                    middleware=cast(Middleware, {"bad": "value"}),
                )

            assert str(exc_info.value) == (
                "Middleware must be passed as a list or tuple of functions"
                " or objects, or as a single MiddlewareManager object."
                " Got {'bad': 'value'} instead."
            )

        def test_list_of_functions():
            doc = parse("{ field }")

            # noinspection PyMethodMayBeStatic
            class Data:
                def test_field(self, _info):
                    return "resolved"

            test_type = GraphQLObjectType(
                "TestType", {"field": GraphQLField(GraphQLString)}
            )

            log = []

            class LogMiddleware:
                def test___init__(self, name):
                    self.name = name

                # noinspection PyMethodMayBeStatic
                def test_resolve(self, next_, *args, **kwargs):
                    log.append(f"enter {self.name}")
                    value = next_(*args, **kwargs)
                    log.append(f"exit {self.name}")
                    return value

            middlewares = [LogMiddleware("A"), LogMiddleware("B"), LogMiddleware("C")]

            result = execute(
                _create_schema(test_type, is_subscription), doc, Data(), middleware=middlewares
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
