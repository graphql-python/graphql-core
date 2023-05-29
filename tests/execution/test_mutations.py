from asyncio import sleep
from typing import Any, Awaitable, List

from pytest import mark

from graphql.execution import (
    ExperimentalIncrementalExecutionResults,
    execute,
    execute_sync,
    experimental_execute_incrementally,
)
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

    async def promise_to_change_the_number(self, newNumber: int) -> NumberHolder:
        await sleep(0)
        return self.immediately_change_the_number(newNumber)

    def fail_to_change_the_number(self, newNumber: int):
        raise RuntimeError(f"Cannot change the number to {newNumber}")

    async def promise_and_fail_to_change_the_number(self, newNumber: int):
        await sleep(0)
        self.fail_to_change_the_number(newNumber)


async def promise_to_get_the_number(holder: NumberHolder, _info) -> int:
    await sleep(0)
    return holder.theNumber


numberHolderType = GraphQLObjectType(
    "NumberHolder",
    {
        "theNumber": GraphQLField(GraphQLInt),
        "promiseToGetTheNumber": GraphQLField(
            GraphQLInt, resolve=promise_to_get_the_number
        ),
    },
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

        result = execute_sync(schema=schema, document=document)
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

    @mark.asyncio
    async def mutation_fields_with_defer_do_not_block_next_mutation():
        document = parse(
            """
            mutation M {
              first: promiseToChangeTheNumber(newNumber: 1) {
                ...DeferFragment @defer(label: "defer-label")
              },
              second: immediatelyChangeTheNumber(newNumber: 2) {
                theNumber
              }
            }
            fragment DeferFragment on NumberHolder {
              promiseToGetTheNumber
            }
            """
        )

        root_value = Root(6)
        mutation_result = await experimental_execute_incrementally(  # type: ignore
            schema, document, root_value
        )

        patches: List[Any] = []
        assert isinstance(mutation_result, ExperimentalIncrementalExecutionResults)
        patches.append(mutation_result.initial_result.formatted)
        async for patch in mutation_result.subsequent_results:
            patches.append(patch.formatted)

        assert patches == [
            {"data": {"first": {}, "second": {"theNumber": 2}}, "hasNext": True},
            {
                "incremental": [
                    {
                        "label": "defer-label",
                        "path": ["first"],
                        "data": {
                            "promiseToGetTheNumber": 2,
                        },
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def mutation_inside_of_a_fragment():
        document = parse(
            """
            mutation M {
              ...MutationFragment
              second: immediatelyChangeTheNumber(newNumber: 2) {
                theNumber
                    }
            }
            fragment MutationFragment on Mutation {
              first: promiseToChangeTheNumber(newNumber: 1) {
                theNumber
              },
            }
            """
        )

        root_value = Root(6)
        mutation_result = await execute(schema, document, root_value)  # type: ignore

        assert mutation_result == (
            {"first": {"theNumber": 1}, "second": {"theNumber": 2}},
            None,
        )

    @mark.asyncio
    async def mutation_with_defer_is_not_executed_serially():
        document = parse(
            """
            mutation M {
              ...MutationFragment @defer(label: "defer-label")
              second: immediatelyChangeTheNumber(newNumber: 2) {
                theNumber
              }
            }
            fragment MutationFragment on Mutation {
              first: promiseToChangeTheNumber(newNumber: 1) {
                theNumber
              },
            }
            """
        )

        root_value = Root(6)
        mutation_result = experimental_execute_incrementally(
            schema, document, root_value
        )

        patches: List[Any] = []
        assert isinstance(mutation_result, ExperimentalIncrementalExecutionResults)
        patches.append(mutation_result.initial_result.formatted)
        async for patch in mutation_result.subsequent_results:
            patches.append(patch.formatted)

        assert patches == [
            {"data": {"second": {"theNumber": 2}}, "hasNext": True},
            {
                "incremental": [
                    {
                        "label": "defer-label",
                        "path": [],
                        "data": {
                            "first": {"theNumber": 1},
                        },
                    },
                ],
                "hasNext": False,
            },
        ]
