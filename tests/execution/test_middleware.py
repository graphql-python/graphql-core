from graphql.execution import MiddlewareManager, execute
from graphql.language.parser import parse
from graphql.type import (
    GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString)


def describe_middleware():

    def with_function_as_middleware():
        doc = parse("{ first second }")

        # noinspection PyMethodMayBeStatic
        class Data:
            def first(self, _info):
                return 'one'

            def second(self, _info):
                return 'two'

        test_type = GraphQLObjectType('Type', {
            'first': GraphQLField(GraphQLString),
            'second': GraphQLField(GraphQLString)})

        def reverse_middleware(next_, *args, **kwargs):
            return next_(*args, **kwargs)[::-1]

        middlewares = MiddlewareManager(reverse_middleware)
        result = execute(
            GraphQLSchema(test_type), doc, Data(), middleware=middlewares)
        assert result.data == {'first': 'eno', 'second': 'owt'}

    def with_object_as_middleware():
        doc = parse("{ first second }")

        # noinspection PyMethodMayBeStatic
        class Data:
            def first(self, _info):
                return 'one'

            def second(self, _info):
                return 'two'

        test_type = GraphQLObjectType('Type', {
            'first': GraphQLField(GraphQLString),
            'second': GraphQLField(GraphQLString)})

        class ReverseMiddleware:

            # noinspection PyMethodMayBeStatic
            def resolve(self, next_, *args, **kwargs):
                return next_(*args, **kwargs)[::-1]

        middlewares = MiddlewareManager(ReverseMiddleware())
        result = execute(
            GraphQLSchema(test_type), doc, Data(), middleware=middlewares)
        assert result.data == {'first': 'eno', 'second': 'owt'}

    def with_middleware_chain():
        doc = parse("{ field }")

        # noinspection PyMethodMayBeStatic
        class Data:
            def field(self, _info):
                return 'resolved'

        test_type = GraphQLObjectType('Type', {
            'field': GraphQLField(GraphQLString)})

        log = []

        class LogMiddleware:
            def __init__(self, name):
                self.name = name

            # noinspection PyMethodMayBeStatic
            def resolve(self, next_, *args, **kwargs):
                log.append(f'enter {self.name}')
                value = next_(*args, **kwargs)
                log.append(f'exit {self.name}')
                return value

        middlewares = [
            LogMiddleware('A'), LogMiddleware('B'), LogMiddleware('C')]

        result = execute(
            GraphQLSchema(test_type), doc, Data(), middleware=middlewares)
        assert result.data == {'field': 'resolved'}

        assert log == [
            'enter C', 'enter B', 'enter A',
            'exit A', 'exit B', 'exit C']
