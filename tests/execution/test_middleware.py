from pytest import raises
from graphql.execution import MiddlewareManager, execute
from graphql.execution.middleware import get_middleware_resolvers, middleware_chain
from graphql.language.parser import parse
from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString


def test_middleware():
    doc = """{
        ok
        not_ok
    }"""

    class Data(object):
        def ok(self, info):
            return "ok"

        def not_ok(self, info):
            return "not_ok"

    doc_ast = parse(doc)

    Type = GraphQLObjectType(
        "Type",
        {"ok": GraphQLField(GraphQLString), "not_ok": GraphQLField(GraphQLString)},
    )

    def reversed_middleware(next, *args, **kwargs):
        p = next(*args, **kwargs)
        return p[::-1]

    middlewares = MiddlewareManager(reversed_middleware)
    result = execute(GraphQLSchema(Type), doc_ast, Data(), middleware=middlewares)
    assert result.data == {"ok": "ko", "not_ok": "ko_ton"}


def test_middleware_class():
    doc = """{
        ok
        not_ok
    }"""

    class Data(object):
        def ok(self, info):
            return "ok"

        def not_ok(self, info):
            return "not_ok"

    doc_ast = parse(doc)

    Type = GraphQLObjectType(
        "Type",
        {"ok": GraphQLField(GraphQLString), "not_ok": GraphQLField(GraphQLString)},
    )

    class MyMiddleware(object):
        def resolve(self, next, *args, **kwargs):
            p = next(*args, **kwargs)
            return p[::-1]

    middlewares = MiddlewareManager(MyMiddleware())
    result = execute(GraphQLSchema(Type), doc_ast, Data(), middleware=middlewares)
    assert result.data == {"ok": "ko", "not_ok": "ko_ton"}


def test_middleware_chain():
    call_order = []

    class CharPrintingMiddleware(object):
        def __init__(self, char):
            self.char = char

        def resolve(self, next, *args, **kwargs):
            call_order.append(f"resolve() called for middleware {self.char}")
            value = next(*args, **kwargs)
            call_order.append(f"then() for {self.char}")
            return value

    middlewares = [
        CharPrintingMiddleware("a"),
        CharPrintingMiddleware("b"),
        CharPrintingMiddleware("c"),
    ]

    middlewares_resolvers = get_middleware_resolvers(middlewares)

    def func():
        return

    chain_iter = middleware_chain(func, middlewares_resolvers)

    assert call_order == []

    chain_iter()

    assert call_order == [
        "resolve() called for middleware c",
        "resolve() called for middleware b",
        "resolve() called for middleware a",
        "then() for a",
        "then() for b",
        "then() for c",
    ]
