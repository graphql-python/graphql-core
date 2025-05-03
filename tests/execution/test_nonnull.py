import asyncio
import re
from typing import Any, Awaitable, cast

import pytest

from graphql.execution import ExecutionResult, execute, execute_sync
from graphql.language import parse
from graphql.pyutils import AwaitableOrValue
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import build_schema

sync_error = RuntimeError("sync")
sync_non_null_error = RuntimeError("syncNonNull")
promise_error = RuntimeError("promise")
promise_non_null_error = RuntimeError("promiseNonNull")


# noinspection PyPep8Naming,PyMethodMayBeStatic
class ThrowingData:
    def sync(self, _info):
        raise sync_error

    def syncNonNull(self, _info):
        raise sync_non_null_error

    async def promise(self, _info):
        raise promise_error

    async def promiseNonNull(self, _info):
        raise promise_non_null_error

    def syncNest(self, _info):
        return ThrowingData()

    def syncNonNullNest(self, _info):
        return ThrowingData()

    async def promiseNest(self, _info):
        return ThrowingData()

    async def promiseNonNullNest(self, _info):
        return ThrowingData()


# noinspection PyPep8Naming,PyMethodMayBeStatic
class NullingData:
    def sync(self, _info):
        return None

    def syncNonNull(self, _info):
        return None

    async def promise(self, _info):
        return None

    async def promiseNonNull(self, _info):
        return None

    def syncNest(self, _info):
        return NullingData()

    def syncNonNullNest(self, _info):
        return NullingData()

    async def promiseNest(self, _info):
        return NullingData()

    async def promiseNonNullNest(self, _info):
        return NullingData()


schema = build_schema(
    """
    type DataType {
      sync: String
      syncNonNull: String!
      promise: String
      promiseNonNull: String!
      syncNest: DataType
      syncNonNullNest: DataType!
      promiseNest: DataType
      promiseNonNullNest: DataType!
    }

    schema {
      query: DataType
    }
    """
)


def execute_query(query: str, root_value: Any) -> AwaitableOrValue[ExecutionResult]:
    return execute(schema=schema, document=parse(query), root_value=root_value)


# avoids also doing any nests
def patch(data: str) -> str:
    return re.sub(
        r"\bsyncNonNull\b", "promiseNonNull", re.sub(r"\bsync\b", "promise", data)
    )


async def execute_sync_and_async(query: str, root_value: Any) -> ExecutionResult:
    sync_result = execute_sync(schema, parse(query), root_value)
    async_result = await cast(
        "Awaitable[ExecutionResult]", execute(schema, parse(patch(query)), root_value)
    )

    assert repr(async_result) == patch(repr(sync_result))
    return sync_result


def describe_execute_handles_non_nullable_types():
    def describe_nulls_a_nullable_field():
        query = """
            {
              sync
            }
            """

        @pytest.mark.asyncio
        async def returns_null():
            result = await execute_sync_and_async(query, NullingData())
            assert result == ({"sync": None}, None)

        @pytest.mark.asyncio
        async def throws():
            result = await execute_sync_and_async(query, ThrowingData())
            assert result == (
                {"sync": None},
                [
                    {
                        "message": str(sync_error),
                        "path": ["sync"],
                        "locations": [(3, 15)],
                    }
                ],
            )

    def describe_nulls_a_returned_object_that_contains_a_non_null_field():
        query = """
            {
              syncNest {
                syncNonNull,
              }
            }
            """

        @pytest.mark.asyncio
        async def that_returns_null():
            result = await execute_sync_and_async(query, NullingData())
            assert result == (
                {"syncNest": None},
                [
                    {
                        "message": "Cannot return null for non-nullable field"
                        " DataType.syncNonNull.",
                        "path": ["syncNest", "syncNonNull"],
                        "locations": [(4, 17)],
                    }
                ],
            )

        @pytest.mark.asyncio
        async def that_throws():
            result = await execute_sync_and_async(query, ThrowingData())
            assert result == (
                {"syncNest": None},
                [
                    {
                        "message": str(sync_non_null_error),
                        "path": ["syncNest", "syncNonNull"],
                        "locations": [(4, 17)],
                    }
                ],
            )

    def describe_nulls_a_complex_tree_of_nullable_fields_each():
        query = """
            {
              syncNest {
                sync
                promise
                syncNest { sync promise }
                promiseNest { sync promise }
              }
              promiseNest {
                sync
                promise
                syncNest { sync promise }
                promiseNest { sync promise }
              }
            }
            """
        data = {
            "syncNest": {
                "sync": None,
                "promise": None,
                "syncNest": {"sync": None, "promise": None},
                "promiseNest": {"sync": None, "promise": None},
            },
            "promiseNest": {
                "sync": None,
                "promise": None,
                "syncNest": {"sync": None, "promise": None},
                "promiseNest": {"sync": None, "promise": None},
            },
        }

        @pytest.mark.asyncio
        async def returns_null():
            result = await cast(
                "Awaitable[ExecutionResult]", execute_query(query, NullingData())
            )
            assert result == (data, None)

        @pytest.mark.asyncio
        async def throws():
            result = await cast(
                "Awaitable[ExecutionResult]", execute_query(query, ThrowingData())
            )
            assert result == (
                data,
                [
                    {
                        "message": str(sync_error),
                        "path": ["syncNest", "sync"],
                        "locations": [(4, 17)],
                    },
                    {
                        "message": str(promise_error),
                        "path": ["syncNest", "promise"],
                        "locations": [(5, 17)],
                    },
                    {
                        "message": str(sync_error),
                        "path": ["syncNest", "syncNest", "sync"],
                        "locations": [(6, 28)],
                    },
                    {
                        "message": str(promise_error),
                        "path": ["syncNest", "syncNest", "promise"],
                        "locations": [(6, 33)],
                    },
                    {
                        "message": str(sync_error),
                        "path": ["syncNest", "promiseNest", "sync"],
                        "locations": [(7, 31)],
                    },
                    {
                        "message": str(promise_error),
                        "path": ["syncNest", "promiseNest", "promise"],
                        "locations": [(7, 36)],
                    },
                    {
                        "message": str(sync_error),
                        "path": ["promiseNest", "sync"],
                        "locations": [(10, 17)],
                    },
                    {
                        "message": str(promise_error),
                        "path": ["promiseNest", "promise"],
                        "locations": [(11, 17)],
                    },
                    {
                        "message": str(sync_error),
                        "path": ["promiseNest", "syncNest", "sync"],
                        "locations": [(12, 28)],
                    },
                    {
                        "message": str(promise_error),
                        "path": ["promiseNest", "syncNest", "promise"],
                        "locations": [(12, 33)],
                    },
                    {
                        "message": str(sync_error),
                        "path": ["promiseNest", "promiseNest", "sync"],
                        "locations": [(13, 31)],
                    },
                    {
                        "message": str(promise_error),
                        "path": ["promiseNest", "promiseNest", "promise"],
                        "locations": [(13, 36)],
                    },
                ],
            )

    def describe_nulls_first_nullable_after_long_chain_of_non_null_fields():
        query = """
            {
              syncNest {
                syncNonNullNest {
                  promiseNonNullNest {
                    syncNonNullNest {
                      promiseNonNullNest {
                        syncNonNull
                      }
                    }
                  }
                }
              }
              promiseNest {
                syncNonNullNest {
                  promiseNonNullNest {
                    syncNonNullNest {
                      promiseNonNullNest {
                        syncNonNull
                      }
                    }
                  }
                }
              }
              anotherNest: syncNest {
                syncNonNullNest {
                  promiseNonNullNest {
                    syncNonNullNest {
                      promiseNonNullNest {
                        promiseNonNull
                      }
                    }
                  }
                }
              }
              anotherPromiseNest: promiseNest {
                syncNonNullNest {
                  promiseNonNullNest {
                    syncNonNullNest {
                      promiseNonNullNest {
                        promiseNonNull
                      }
                    }
                  }
                }
              }
            }
            """
        data = {
            "syncNest": None,
            "promiseNest": None,
            "anotherNest": None,
            "anotherPromiseNest": None,
        }

        @pytest.mark.asyncio
        async def returns_null():
            result = await cast(
                "Awaitable[ExecutionResult]", execute_query(query, NullingData())
            )
            assert result == (
                data,
                [
                    {
                        "message": "Cannot return null for non-nullable field"
                        " DataType.syncNonNull.",
                        "path": [
                            "syncNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNull",
                        ],
                        "locations": [(8, 25)],
                    },
                    {
                        "message": "Cannot return null for non-nullable field"
                        " DataType.syncNonNull.",
                        "path": [
                            "promiseNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNull",
                        ],
                        "locations": [(19, 25)],
                    },
                    {
                        "message": "Cannot return null for non-nullable field"
                        " DataType.promiseNonNull.",
                        "path": [
                            "anotherNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "promiseNonNull",
                        ],
                        "locations": [(30, 25)],
                    },
                    {
                        "message": "Cannot return null for non-nullable field"
                        " DataType.promiseNonNull.",
                        "path": [
                            "anotherPromiseNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "promiseNonNull",
                        ],
                        "locations": [(41, 25)],
                    },
                ],
            )

        @pytest.mark.asyncio
        async def throws():
            result = await cast(
                "Awaitable[ExecutionResult]", execute_query(query, ThrowingData())
            )
            assert result == (
                data,
                [
                    {
                        "message": str(sync_non_null_error),
                        "path": [
                            "syncNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNull",
                        ],
                        "locations": [(8, 25)],
                    },
                    {
                        "message": str(sync_non_null_error),
                        "path": [
                            "promiseNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNull",
                        ],
                        "locations": [(19, 25)],
                    },
                    {
                        "message": str(promise_non_null_error),
                        "path": [
                            "anotherNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "promiseNonNull",
                        ],
                        "locations": [(30, 25)],
                    },
                    {
                        "message": str(promise_non_null_error),
                        "path": [
                            "anotherPromiseNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "syncNonNullNest",
                            "promiseNonNullNest",
                            "promiseNonNull",
                        ],
                        "locations": [(41, 25)],
                    },
                ],
            )

    def describe_nulls_the_top_level_if_non_nullable_field():
        query = """
            {
                syncNonNull
            }
            """

        @pytest.mark.asyncio
        async def returns_null():
            result = await execute_sync_and_async(query, NullingData())
            await asyncio.sleep(0)  # strangely needed to get coverage on Python 3.11
            assert result == (
                None,
                [
                    {
                        "message": "Cannot return null for non-nullable field"
                        " DataType.syncNonNull.",
                        "path": ["syncNonNull"],
                        "locations": [(3, 17)],
                    }
                ],
            )

        @pytest.mark.asyncio
        async def throws():
            result = await execute_sync_and_async(query, ThrowingData())
            await asyncio.sleep(0)  # strangely needed to get coverage on Python 3.11
            assert result == (
                None,
                [
                    {
                        "message": str(sync_non_null_error),
                        "path": ["syncNonNull"],
                        "locations": [(3, 17)],
                    }
                ],
            )

    def describe_handles_non_null_argument():
        # noinspection PyPep8Naming
        schema_with_non_null_arg = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "withNonNullArg": GraphQLField(
                        GraphQLString,
                        args={
                            "cannotBeNull": GraphQLArgument(
                                GraphQLNonNull(GraphQLString)
                            )
                        },
                        resolve=lambda _obj, _info, cannotBeNull: "Passed: "
                        + str(cannotBeNull),
                    )
                },
            )
        )

        def succeeds_when_passed_non_null_literal_value():
            result = execute_sync(
                schema_with_non_null_arg,
                parse(
                    """
                    query {
                      withNonNullArg (cannotBeNull: "literal value")
                    }
                    """
                ),
            )

            assert result == ({"withNonNullArg": "Passed: literal value"}, None)

        def succeeds_when_passed_non_null_variable_value():
            result = execute_sync(
                schema_with_non_null_arg,
                parse(
                    """
                    query ($testVar: String!) {
                      withNonNullArg (cannotBeNull: $testVar)
                    }
                    """
                ),
                variable_values={
                    "testVar": "variable value",
                },
            )

            assert result == ({"withNonNullArg": "Passed: variable value"}, None)

        def succeeds_when_missing_variable_has_default_value():
            result = execute_sync(
                schema_with_non_null_arg,
                parse(
                    """
                    query ($testVar: String = "default value") {
                      withNonNullArg (cannotBeNull: $testVar)
                    }
                    """
                ),
                variable_values={},  # intentionally missing variable
            )

            assert result == ({"withNonNullArg": "Passed: default value"}, None)

        def field_error_when_missing_non_null_arg():
            # Note: validation should identify this issue first
            # (missing args rule) however execution should still
            # protect against this.
            result = execute_sync(
                schema_with_non_null_arg,
                parse(
                    """
                    query {
                      withNonNullArg
                    }
                    """
                ),
            )

            assert result == (
                {"withNonNullArg": None},
                [
                    {
                        "message": "Argument 'cannotBeNull' of required type"
                        " 'String!' was not provided.",
                        "locations": [(3, 23)],
                        "path": ["withNonNullArg"],
                    }
                ],
            )

        def field_error_when_non_null_arg_provided_null():
            # Note: validation should identify this issue first
            # (values of correct type rule) however execution
            # should still protect against this.
            result = execute_sync(
                schema_with_non_null_arg,
                parse(
                    """
                    query {
                      withNonNullArg(cannotBeNull: null)
                    }
                    """
                ),
            )

            assert result == (
                {"withNonNullArg": None},
                [
                    {
                        "message": "Argument 'cannotBeNull' of non-null type"
                        " 'String!' must not be null.",
                        "locations": [(3, 52)],
                        "path": ["withNonNullArg"],
                    }
                ],
            )

        def field_error_when_non_null_arg_not_provided_variable_value():
            # Note: validation should identify this issue first
            # (variables in allowed position rule) however execution
            # should still protect against this.
            result = execute_sync(
                schema_with_non_null_arg,
                parse(
                    """
                    query ($testVar: String) {
                      withNonNullArg(cannotBeNull: $testVar)
                    }
                    """
                ),
                variable_values={},
            )  # intentionally missing variable

            assert result == (
                {"withNonNullArg": None},
                [
                    {
                        "message": "Argument 'cannotBeNull' of required type"
                        " 'String!' was provided the variable"
                        " '$testVar' which was not provided"
                        " a runtime value.",
                        "locations": [(3, 52)],
                        "path": ["withNonNullArg"],
                    }
                ],
            )

        def field_error_when_non_null_arg_provided_explicit_null_variable():
            result = execute_sync(
                schema_with_non_null_arg,
                parse(
                    """
                    query ($testVar: String = "default value") {
                      withNonNullArg (cannotBeNull: $testVar)
                    }
                    """
                ),
                variable_values={"testVar": None},
            )

            assert result == (
                {"withNonNullArg": None},
                [
                    {
                        "message": "Argument 'cannotBeNull' of non-null type"
                        " 'String!' must not be null.",
                        "locations": [(3, 53)],
                        "path": ["withNonNullArg"],
                    }
                ],
            )
