from inspect import isawaitable

from pytest import mark

from graphql.execution import execute
from graphql.language import parse
from graphql.type import (
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
)


def describe_default_type_resolver_awaitable_cleanup():
    @mark.asyncio
    @mark.filterwarnings("error:.*was never awaited:RuntimeWarning")
    @mark.parametrize("throws", [False, True], ids=["matches", "throws"])
    async def observes_earlier_rejections_when_a_later_type_throws_or_matches(throws):
        async def first_is_type_of(_value, _info):
            raise RuntimeError("Earlier rejection")

        def second_is_type_of(_value, _info):
            if throws:
                raise RuntimeError("Later throw")
            return True

        first = GraphQLObjectType(
            "First", {"name": GraphQLField(GraphQLString)}, is_type_of=first_is_type_of
        )
        second = GraphQLObjectType(
            "Second",
            {"name": GraphQLField(GraphQLString)},
            is_type_of=second_is_type_of,
        )
        union = GraphQLUnionType("Union", [first, second])
        query = GraphQLObjectType(
            "Query", {"value": GraphQLField(union, resolve=lambda *_args: {})}
        )

        result = execute(GraphQLSchema(query), parse("{ value { __typename } }"))
        assert isawaitable(result)
        result = await result

        if throws:
            assert result.errors
            assert [error.message for error in result.errors] == ["Later throw"]
            assert result.data == {"value": None}
        else:
            assert result.errors is None
            assert result.data == {"value": {"__typename": "Second"}}
