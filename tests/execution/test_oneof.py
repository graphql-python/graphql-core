from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphql.execution import ExecutionResult, execute
from graphql.language import parse
from graphql.utilities import build_schema

if TYPE_CHECKING:
    from graphql.pyutils import AwaitableOrValue

schema = build_schema("""
    type Query {
      test(input: TestInputObject!): TestObject
    }

    input TestInputObject @oneOf {
      a: String
      b: Int
    }

    type TestObject {
      a: String
      b: Int
    }
    """)


def execute_query(
    query: str, root_value: Any, variable_values: dict[str, Any] | None = None
) -> AwaitableOrValue[ExecutionResult]:
    return execute(schema, parse(query), root_value, variable_values=variable_values)


def describe_execute_handles_one_of_input_objects():
    def describe_one_of_input_objects():
        root_value = {
            "test": lambda _info, input: input,
        }

        def accepts_a_good_default_value():
            query = """
                query ($input: TestInputObject! = {a: "abc"}) {
                  test(input: $input) {
                    a
                    b
                  }
                }
                """
            result = execute_query(query, root_value)

            assert result == ({"test": {"a": "abc", "b": None}}, None)

        def rejects_a_bad_default_value():
            query = """
                query ($input: TestInputObject! = {a: "abc", b: 123}) {
                  test(input: $input) {
                    a
                    b
                  }
                }
                """
            result = execute_query(query, root_value)

            assert result == (
                {"test": None},
                [
                    {
                        # This type of error would be caught at validation-time
                        # hence the vague error message here.
                        "message": "Argument 'input' of non-null type"
                        " 'TestInputObject!' must not be null.",
                        "locations": [(3, 31)],
                        "path": ["test"],
                    }
                ],
            )

        def accepts_a_good_variable():
            query = """
                query ($input: TestInputObject!) {
                  test(input: $input) {
                    a
                    b
                  }
                }
                """
            result = execute_query(query, root_value, {"input": {"a": "abc"}})

            assert result == ({"test": {"a": "abc", "b": None}}, None)

        def accepts_a_good_variable_with_an_undefined_key():
            query = """
                query ($input: TestInputObject!) {
                  test(input: $input) {
                    a
                    b
                  }
                }
                """
            result = execute_query(query, root_value, {"input": {"a": "abc"}})

            assert result == ({"test": {"a": "abc", "b": None}}, None)

        def rejects_a_variable_with_multiple_non_null_keys():
            query = """
                query ($input: TestInputObject!) {
                  test(input: $input) {
                    a
                    b
                  }
                }
                """
            result = execute_query(query, root_value, {"input": {"a": "abc", "b": 123}})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' got invalid value"
                        " {'a': 'abc', 'b': 123}; Exactly one key must be specified"
                        " for OneOf type 'TestInputObject'.",
                        "locations": [(2, 24)],
                    }
                ],
            )

        def rejects_a_variable_with_multiple_nullable_keys():
            query = """
                query ($input: TestInputObject!) {
                  test(input: $input) {
                    a
                    b
                  }
                }
                """
            result = execute_query(
                query, root_value, {"input": {"a": "abc", "b": None}}
            )

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' got invalid value"
                        " {'a': 'abc', 'b': None}; Exactly one key must be specified"
                        " for OneOf type 'TestInputObject'.",
                        "locations": [(2, 24)],
                    }
                ],
            )
