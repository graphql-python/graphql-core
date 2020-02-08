import asyncio
from typing import Awaitable

from pytest import mark  # type: ignore

from graphql.execution import execute
from graphql.language import parse
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInt,
    GraphQLObjectType,
    GraphQLSchema,
)


# noinspection PyPep8Naming
class NumberHolder:

    theNumber: int

    def __init__(self, originalNumber: int):
        self.theNumber = originalNumber


# noinspection PyPep8Naming
class Root:

    numberHolder: NumberHolder

    def __init__(self, originalNumber: int):
        self.numberHolder = NumberHolder(originalNumber)

    def immediately_change_the_number(self, newNumber: int) -> NumberHolder:
        self.numberHolder.theNumber = newNumber
        return self.numberHolder

    async def promise_to_change_the_number(self, new_number: int) -> NumberHolder:
        await asyncio.sleep(0)
        return self.immediately_change_the_number(new_number)

    def fail_to_change_the_number(self, newNumber: int):
        raise RuntimeError(f"Cannot change the number to {newNumber}")

    async def promise_and_fail_to_change_the_number(self, newNumber: int):
        await asyncio.sleep(0)
        self.fail_to_change_the_number(newNumber)


numberHolderType = GraphQLObjectType(
    "NumberHolder", {"theNumber": GraphQLField(GraphQLInt)}
)

# noinspection PyPep8Naming
schema = GraphQLSchema(
    GraphQLObjectType("Query", {"numberHolder": GraphQLField(numberHolderType)}),
    GraphQLObjectType(
        "Mutation",
        {
            "immediatelyChangeTheNumber": GraphQLField(
                numberHolderType,
                args={"newNumber": GraphQLArgument(GraphQLInt)},
                resolve=lambda obj, _info, newNumber: obj.immediately_change_the_number(
                    newNumber
                ),
            ),
            "promiseToChangeTheNumber": GraphQLField(
                numberHolderType,
                args={"newNumber": GraphQLArgument(GraphQLInt)},
                resolve=lambda obj, _info, newNumber: obj.promise_to_change_the_number(
                    newNumber
                ),
            ),
            "failToChangeTheNumber": GraphQLField(
                numberHolderType,
                args={"newNumber": GraphQLArgument(GraphQLInt)},
                resolve=lambda obj, _info, newNumber: obj.fail_to_change_the_number(
                    newNumber
                ),
            ),
            "promiseAndFailToChangeTheNumber": GraphQLField(
                numberHolderType,
                args={"newNumber": GraphQLArgument(GraphQLInt)},
                resolve=lambda obj, _info, newNumber: (
                    obj.promise_and_fail_to_change_the_number(newNumber)
                ),
            ),
        },
    ),
)


def describe_execute_handles_mutation_execution_ordering():
    @mark.asyncio
    async def evaluates_mutations_serially():
        document = parse(
            """
            mutation M {
              first: immediatelyChangeTheNumber(newNumber: 1) {
                theNumber
              },
              second: promiseToChangeTheNumber(newNumber: 2) {
                theNumber
              },
              third: immediatelyChangeTheNumber(newNumber: 3) {
                theNumber
              }
              fourth: promiseToChangeTheNumber(newNumber: 4) {
                theNumber
              },
              fifth: immediatelyChangeTheNumber(newNumber: 5) {
                theNumber
              }
            }
            """
        )

        root_value = Root(6)
        awaitable_result = execute(
            schema=schema, document=document, root_value=root_value
        )
        assert isinstance(awaitable_result, Awaitable)
        mutation_result = await awaitable_result

        assert mutation_result == (
            {
                "first": {"theNumber": 1},
                "second": {"theNumber": 2},
                "third": {"theNumber": 3},
                "fourth": {"theNumber": 4},
                "fifth": {"theNumber": 5},
            },
            None,
        )

    def does_not_include_illegal_mutation_fields_in_output():
        document = parse("mutation { thisIsIllegalDoNotIncludeMe }")

        result = execute(schema=schema, document=document)
        assert result == ({}, None)

    @mark.asyncio
    async def evaluates_mutations_correctly_in_presence_of_a_failed_mutation():
        document = parse(
            """
            mutation M {
              first: immediatelyChangeTheNumber(newNumber: 1) {
                theNumber
              },
              second: promiseToChangeTheNumber(newNumber: 2) {
                theNumber
              },
              third: failToChangeTheNumber(newNumber: 3) {
                theNumber
              }
              fourth: promiseToChangeTheNumber(newNumber: 4) {
                theNumber
              },
              fifth: immediatelyChangeTheNumber(newNumber: 5) {
                theNumber
              }
              sixth: promiseAndFailToChangeTheNumber(newNumber: 6) {
                theNumber
              }
            }
            """
        )

        root_value = Root(6)
        awaitable_result = execute(
            schema=schema, document=document, root_value=root_value
        )
        assert isinstance(awaitable_result, Awaitable)
        result = await awaitable_result

        assert result == (
            {
                "first": {"theNumber": 1},
                "second": {"theNumber": 2},
                "third": None,
                "fourth": {"theNumber": 4},
                "fifth": {"theNumber": 5},
                "sixth": None,
            },
            [
                {
                    "message": "Cannot change the number to 3",
                    "locations": [(9, 15)],
                    "path": ["third"],
                },
                {
                    "message": "Cannot change the number to 6",
                    "locations": [(18, 15)],
                    "path": ["sixth"],
                },
            ],
        )
