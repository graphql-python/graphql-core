import gc
import weakref
from importlib import import_module
from math import nan
from typing import Any, Dict, List, Optional

from graphql import graphql_sync
from graphql.error import GraphQLError
from graphql.execution import ExecutionResult, execute_sync
from graphql.execution.values import get_variable_values, input_is_nested_too_deeply
from graphql.language import OperationDefinitionNode, StringValueNode, ValueNode, parse
from graphql.language.parser import MAX_NESTING_DEPTH
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFloat,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import build_schema

TestFaultyScalarGraphQLError = GraphQLError(
    "FaultyScalarErrorMessage", extensions={"code": "FaultyScalarExtensionCode"}
)


def faulty_parse_value(value: str) -> str:
    raise TestFaultyScalarGraphQLError


def faulty_parse_literal(ast: ValueNode, _variables=None) -> str:
    raise TestFaultyScalarGraphQLError


TestFaultyScalar = GraphQLScalarType(
    name="FaultyScalar",
    parse_value=faulty_parse_value,
    parse_literal=faulty_parse_literal,
)


def parse_serialized_value(value: str) -> str:
    assert value == "SerializedValue"
    return "DeserializedValue"


def parse_literal_value(ast: ValueNode, _variables=None) -> str:
    assert isinstance(ast, StringValueNode)
    assert ast.value == "SerializedValue"
    return parse_serialized_value(ast.value)


TestComplexScalar = GraphQLScalarType(
    name="ComplexScalar",
    parse_value=parse_serialized_value,
    parse_literal=parse_literal_value,
)


TestInputObject = GraphQLInputObjectType(
    "TestInputObject",
    {
        "a": GraphQLInputField(GraphQLString),
        "b": GraphQLInputField(GraphQLList(GraphQLString)),
        "c": GraphQLInputField(GraphQLNonNull(GraphQLString)),
        "d": GraphQLInputField(TestComplexScalar),
        "e": GraphQLInputField(TestFaultyScalar),
    },
)

TestCustomInputObject = GraphQLInputObjectType(
    "TestCustomInputObject",
    {"x": GraphQLInputField(GraphQLFloat), "y": GraphQLInputField(GraphQLFloat)},
    out_type=lambda value: f"(x|y) = ({value['x']}|{value['y']})",
)


TestNestedInputObject = GraphQLInputObjectType(
    "TestNestedInputObject",
    {
        "na": GraphQLInputField(GraphQLNonNull(TestInputObject)),
        "nb": GraphQLInputField(GraphQLNonNull(GraphQLString)),
    },
)


TestEnum = GraphQLEnumType(
    "TestEnum",
    {
        "NULL": None,
        "UNDEFINED": Undefined,
        "NAN": nan,
        "FALSE": False,
        "CUSTOM": "custom value",
        "DEFAULT_VALUE": GraphQLEnumValue(),
    },
)


def field_with_input_arg(input_arg: GraphQLArgument):
    return GraphQLField(
        GraphQLString,
        args={"input": input_arg},
        resolve=lambda _obj, _info, **args: (
            repr(args["input"]) if "input" in args else None
        ),
    )


TestType = GraphQLObjectType(
    "TestType",
    {
        "fieldWithEnumInput": field_with_input_arg(GraphQLArgument(TestEnum)),
        "fieldWithNonNullableEnumInput": field_with_input_arg(
            GraphQLArgument(GraphQLNonNull(TestEnum))
        ),
        "fieldWithObjectInput": field_with_input_arg(GraphQLArgument(TestInputObject)),
        "fieldWithCustomObjectInput": field_with_input_arg(
            GraphQLArgument(TestCustomInputObject)
        ),
        "fieldWithNullableStringInput": field_with_input_arg(
            GraphQLArgument(GraphQLString)
        ),
        "fieldWithNonNullableStringInput": field_with_input_arg(
            GraphQLArgument(GraphQLNonNull(GraphQLString))
        ),
        "fieldWithDefaultArgumentValue": field_with_input_arg(
            GraphQLArgument(GraphQLString, default_value="Hello World")
        ),
        "fieldWithNonNullableStringInputAndDefaultArgValue": field_with_input_arg(
            GraphQLArgument(GraphQLNonNull(GraphQLString), default_value="Hello World")
        ),
        "fieldWithNestedInputObject": field_with_input_arg(
            GraphQLArgument(TestNestedInputObject, default_value="Hello World")
        ),
        "list": field_with_input_arg(GraphQLArgument(GraphQLList(GraphQLString))),
        "nnList": field_with_input_arg(
            GraphQLArgument(GraphQLNonNull(GraphQLList(GraphQLString)))
        ),
        "listNN": field_with_input_arg(
            GraphQLArgument(GraphQLList(GraphQLNonNull(GraphQLString)))
        ),
        "nnListNN": field_with_input_arg(
            GraphQLArgument(GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLString))))
        ),
    },
)

schema = GraphQLSchema(TestType)


def execute_query(
    query: str, variable_values: Optional[Dict[str, Any]] = None
) -> ExecutionResult:
    document = parse(query)
    return execute_sync(schema, document, variable_values=variable_values)


def describe_execute_handles_inputs():
    def describe_handles_objects_and_nullability():
        def describe_using_inline_struct():
            def executes_with_complex_input():
                result = execute_query("""
                    {
                      fieldWithObjectInput(
                        input: {a: "foo", b: ["bar"], c: "baz"})
                    }
                    """)

                assert result == (
                    {"fieldWithObjectInput": "{'a': 'foo', 'b': ['bar'], 'c': 'baz'}"},
                    None,
                )

            def executes_with_custom_input():
                # This is an extension of GraphQL.js.
                result = execute_query("""
                    {
                      fieldWithCustomObjectInput(
                        input: {x: -3.0, y: 4.5})
                    }
                    """)

                assert result == (
                    {"fieldWithCustomObjectInput": "'(x|y) = (-3.0|4.5)'"},
                    None,
                )

            def properly_parses_single_value_to_list():
                result = execute_query("""
                    {
                      fieldWithObjectInput(input: {a: "foo", b: "bar", c: "baz"})
                    }
                    """)

                assert result == (
                    {"fieldWithObjectInput": "{'a': 'foo', 'b': ['bar'], 'c': 'baz'}"},
                    None,
                )

            def properly_parses_null_value_to_null():
                result = execute_query("""
                    {
                      fieldWithObjectInput(
                        input: {a: null, b: null, c: "C", d: null})
                    }
                    """)

                assert result == (
                    {
                        "fieldWithObjectInput": "{'a': None, 'b': None,"
                        " 'c': 'C', 'd': None}"
                    },
                    None,
                )

            def properly_parses_null_value_in_list():
                result = execute_query("""
                    {
                      fieldWithObjectInput(input: {b: ["A",null,"C"], c: "C"})
                    }
                    """)

                assert result == (
                    {"fieldWithObjectInput": "{'b': ['A', None, 'C'], 'c': 'C'}"},
                    None,
                )

            def does_not_use_incorrect_value():
                result = execute_query("""
                    {
                      fieldWithObjectInput(input: ["foo", "bar", "baz"])
                    }
                    """)

                assert result == (
                    {"fieldWithObjectInput": None},
                    [
                        {
                            "message": "Argument 'input' has invalid value"
                            ' ["foo", "bar", "baz"].',
                            "path": ["fieldWithObjectInput"],
                            "locations": [(3, 51)],
                        }
                    ],
                )

            def properly_runs_parse_literal_on_complex_scalar_types():
                result = execute_query("""
                    {
                      fieldWithObjectInput(input: {c: "foo", d: "SerializedValue"})
                    }
                    """)

                assert result == (
                    {"fieldWithObjectInput": "{'c': 'foo', 'd': 'DeserializedValue'}"},
                    None,
                )

            def errors_on_faulty_scalar_type_input():
                result = execute_query("""
                    {
                      fieldWithObjectInput(input: {c: "foo", e: "bar"})
                    }
                    """)

                assert result == (
                    {"fieldWithObjectInput": None},
                    [
                        {
                            "message": "Argument 'input' has invalid value"
                            ' {c: "foo", e: "bar"}.',
                            "path": ["fieldWithObjectInput"],
                            "locations": [(3, 51)],
                        }
                    ],
                )

        def describe_using_variables():
            doc = """
                query ($input: TestInputObject) {
                  fieldWithObjectInput(input: $input)
                }
                """

            def executes_with_complex_input():
                params = {"input": {"a": "foo", "b": ["bar"], "c": "baz"}}
                result = execute_query(doc, params)

                assert result == (
                    {"fieldWithObjectInput": "{'a': 'foo', 'b': ['bar'], 'c': 'baz'}"},
                    None,
                )

            def uses_undefined_when_variable_not_provided():
                result = execute_query(
                    """
                    query q($input: String) {
                      fieldWithNullableStringInput(input: $input)
                    }
                    """,
                    {},
                )  # Intentionally missing variable values.

                assert result == ({"fieldWithNullableStringInput": None}, None)

            def uses_null_when_variable_provided_explicit_null_value():
                result = execute_query(
                    """
                    query q($input: String) {
                      fieldWithNullableStringInput(input: $input)
                    }
                    """,
                    {"input": None},
                )

                assert result == ({"fieldWithNullableStringInput": "None"}, None)

            def uses_default_value_when_not_provided():
                result = execute_query("""
                    query ($input: TestInputObject = {
                      a: "foo", b: ["bar"], c: "baz"}) {
                        fieldWithObjectInput(input: $input)
                    }
                    """)

                assert result == (
                    {"fieldWithObjectInput": "{'a': 'foo', 'b': ['bar'], 'c': 'baz'}"},
                    None,
                )

            def does_not_use_default_value_when_provided():
                result = execute_query(
                    """
                    query q($input: String = "Default value") {
                      fieldWithNullableStringInput(input: $input)
                    }
                    """,
                    {"input": "Variable value"},
                )

                assert result == (
                    {"fieldWithNullableStringInput": "'Variable value'"},
                    None,
                )

            def uses_explicit_null_value_instead_of_default_value():
                result = execute_query(
                    """
                    query q($input: String = "Default value") {
                      fieldWithNullableStringInput(input: $input)
                    }
                    """,
                    {"input": None},
                )

                assert result == ({"fieldWithNullableStringInput": "None"}, None)

            def uses_null_default_value_when_not_provided():
                result = execute_query(
                    """
                    query q($input: String = null) {
                      fieldWithNullableStringInput(input: $input)
                    }
                    """,
                    {},
                )  # Intentionally missing variable values.

                assert result == ({"fieldWithNullableStringInput": "None"}, None)

            def properly_parses_single_value_to_list():
                params = {"input": {"a": "foo", "b": "bar", "c": "baz"}}
                result = execute_query(doc, params)

                assert result == (
                    {"fieldWithObjectInput": "{'a': 'foo', 'b': ['bar'], 'c': 'baz'}"},
                    None,
                )

            def executes_with_complex_scalar_input():
                params = {"input": {"c": "foo", "d": "SerializedValue"}}
                result = execute_query(doc, params)

                assert result == (
                    {"fieldWithObjectInput": "{'c': 'foo', 'd': 'DeserializedValue'}"},
                    None,
                )

            def errors_on_faulty_scalar_type_input():
                params = {"input": {"c": "foo", "e": "SerializedValue"}}
                result = execute_query(doc, params)

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' got invalid value"
                            " 'SerializedValue' at 'input.e'; FaultyScalarErrorMessage",
                            "locations": [(2, 24)],
                            "extensions": {"code": "FaultyScalarExtensionCode"},
                        }
                    ],
                )

            def errors_on_null_for_nested_non_null():
                params = {"input": {"a": "foo", "b": "bar", "c": None}}
                result = execute_query(doc, params)

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' got invalid value"
                            " None at 'input.c';"
                            " Expected non-nullable type 'String!' not to be None.",
                            "locations": [(2, 24)],
                        }
                    ],
                )

            def errors_on_incorrect_type():
                result = execute_query(doc, {"input": "foo bar"})

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' got invalid value 'foo bar';"
                            " Expected type 'TestInputObject' to be a mapping.",
                            "locations": [(2, 24)],
                            "path": None,
                        }
                    ],
                )

            def errors_on_omission_of_nested_non_null():
                result = execute_query(doc, {"input": {"a": "foo", "b": "bar"}})

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' got invalid value"
                            " {'a': 'foo', 'b': 'bar'};"
                            " Field 'c' of required type 'String!' was not provided.",
                            "locations": [(2, 24)],
                        }
                    ],
                )

            def errors_on_deep_nested_errors_and_with_many_errors():
                nested_doc = """
                    query ($input: TestNestedInputObject) {
                      fieldWithNestedObjectInput(input: $input)
                    }
                    """
                result = execute_query(nested_doc, {"input": {"na": {"a": "foo"}}})

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' got invalid value"
                            " {'a': 'foo'} at 'input.na';"
                            " Field 'c' of required type 'String!' was not provided.",
                            "locations": [(2, 28)],
                        },
                        {
                            "message": "Variable '$input' got invalid value"
                            " {'na': {'a': 'foo'}};"
                            " Field 'nb' of required type 'String!' was not provided.",
                            "locations": [(2, 28)],
                        },
                    ],
                )

            def errors_on_addition_of_unknown_input_field():
                params = {"input": {"a": "foo", "b": "bar", "c": "baz", "extra": "dog"}}
                result = execute_query(doc, params)

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' got invalid value {'a':"
                            " 'foo', 'b': 'bar', 'c': 'baz', 'extra': 'dog'}; Field"
                            " 'extra' is not defined by type 'TestInputObject'.",
                            "locations": [(2, 24)],
                        }
                    ],
                )

    def describe_handles_custom_enum_values():
        def allows_custom_enum_values_as_inputs():
            result = execute_query("""
                {
                  null: fieldWithEnumInput(input: NULL)
                  NaN: fieldWithEnumInput(input: NAN)
                  false: fieldWithEnumInput(input: FALSE)
                  customValue: fieldWithEnumInput(input: CUSTOM)
                  defaultValue: fieldWithEnumInput(input: DEFAULT_VALUE)
                }
                """)

            assert result == (
                {
                    "null": "None",
                    "NaN": "nan",
                    "false": "False",
                    "customValue": "'custom value'",
                    # different from graphql.js, enum values are always wrapped
                    "defaultValue": "None",
                },
                None,
            )

        def allows_non_nullable_inputs_to_have_null_as_enum_custom_value():
            result = execute_query("""
                {
                   fieldWithNonNullableEnumInput(input: NULL)
                }
                """)

            assert result == ({"fieldWithNonNullableEnumInput": "None"}, None)

    def describe_handles_nullable_scalars():
        def allows_nullable_inputs_to_be_omitted():
            result = execute_query("""
                {
                  fieldWithNullableStringInput
                }
                """)

            assert result == ({"fieldWithNullableStringInput": None}, None)

        def allows_nullable_inputs_to_be_omitted_in_a_variable():
            result = execute_query("""
                query ($value: String) {
                  fieldWithNullableStringInput(input: $value)
                }
                """)

            assert result == ({"fieldWithNullableStringInput": None}, None)

        def allows_nullable_inputs_to_be_omitted_in_an_unlisted_variable():
            result = execute_query("""
                query SetsNullable {
                  fieldWithNullableStringInput(input: $value)
                }
                """)

            assert result == ({"fieldWithNullableStringInput": None}, None)

        def allows_nullable_inputs_to_be_set_to_null_in_a_variable():
            doc = """
                query SetsNullable($value: String) {
                  fieldWithNullableStringInput(input: $value)
                }
                """
            result = execute_query(doc, {"value": None})

            assert result == ({"fieldWithNullableStringInput": "None"}, None)

        def allows_nullable_inputs_to_be_set_to_a_value_in_a_variable():
            doc = """
                query SetsNullable($value: String) {
                  fieldWithNullableStringInput(input: $value)
                }
                """
            result = execute_query(doc, {"value": "a"})

            assert result == ({"fieldWithNullableStringInput": "'a'"}, None)

        def allows_nullable_inputs_to_be_set_to_a_value_directly():
            result = execute_query("""
                {
                  fieldWithNullableStringInput(input: "a")
                }
                """)

            assert result == ({"fieldWithNullableStringInput": "'a'"}, None)

    def describe_handles_non_nullable_scalars():
        def allows_non_nullable_variable_to_be_omitted_given_a_default():
            result = execute_query("""
                query ($value: String! = "default") {
                  fieldWithNullableStringInput(input: $value)
                }
                """)

            assert result == ({"fieldWithNullableStringInput": "'default'"}, None)

        def allows_non_nullable_inputs_to_be_omitted_given_a_default():
            result = execute_query("""
                query ($value: String = "default") {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """)

            assert result == ({"fieldWithNonNullableStringInput": "'default'"}, None)

        def does_not_allow_non_nullable_inputs_to_be_omitted_in_a_variable():
            result = execute_query("""
                query ($value: String!) {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """)

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$value' of required type 'String!'"
                        " was not provided.",
                        "locations": [(2, 24)],
                        "path": None,
                    }
                ],
            )

        def does_not_allow_non_nullable_inputs_to_be_set_to_null_in_variable():
            doc = """
                query ($value: String!) {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            result = execute_query(doc, {"value": None})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$value' of non-null type 'String!'"
                        " must not be null.",
                        "locations": [(2, 24)],
                        "path": None,
                    }
                ],
            )

        def allows_non_nullable_inputs_to_be_set_to_a_value_in_a_variable():
            doc = """
                query ($value: String!) {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            result = execute_query(doc, {"value": "a"})

            assert result == ({"fieldWithNonNullableStringInput": "'a'"}, None)

        def allows_non_nullable_inputs_to_be_set_to_a_value_directly():
            result = execute_query("""
                {
                  fieldWithNonNullableStringInput(input: "a")
                }
                """)

            assert result == ({"fieldWithNonNullableStringInput": "'a'"}, None)

        def reports_error_for_missing_non_nullable_inputs():
            result = execute_query("{ fieldWithNonNullableStringInput }")

            assert result == (
                {"fieldWithNonNullableStringInput": None},
                [
                    {
                        "message": "Argument 'input' of required type 'String!'"
                        " was not provided.",
                        "locations": [(1, 3)],
                        "path": ["fieldWithNonNullableStringInput"],
                    }
                ],
            )

        def reports_error_for_array_passed_into_string_input():
            doc = """
                query ($value: String!) {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            result = execute_query(doc, {"value": [1, 2, 3]})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$value' got invalid value [1, 2, 3];"
                        " String cannot represent a non string value: [1, 2, 3]",
                        "locations": [(2, 24)],
                        "path": None,
                    }
                ],
            )

            errors = result.errors
            assert errors
            assert errors[0].original_error

        def reports_error_for_non_provided_variables_for_non_nullable_inputs():
            # Note: this test would typically fail validation before
            # encountering this execution error, however for queries which
            # previously validated and are being run against a new schema which
            # have introduced a breaking change to make a formerly non-required
            # argument required, this asserts failure before allowing the
            # underlying code to receive a non-null value.
            result = execute_query("""
                {
                  fieldWithNonNullableStringInput(input: $foo)
                }
                """)

            assert result == (
                {"fieldWithNonNullableStringInput": None},
                [
                    {
                        "message": "Argument 'input' of required type 'String!'"
                        " was provided the variable '$foo' which was"
                        " not provided a runtime value.",
                        "locations": [(3, 58)],
                        "path": ["fieldWithNonNullableStringInput"],
                    }
                ],
            )

    def describe_handles_lists_and_nullability():
        def allows_lists_to_be_null():
            doc = """
                query ($input: [String]) {
                  list(input: $input)
                }
                """
            result = execute_query(doc, {"input": None})

            assert result == ({"list": "None"}, None)

        def allows_lists_to_contain_values():
            doc = """
                query ($input: [String]) {
                  list(input: $input)
                }
                """
            result = execute_query(doc, {"input": ["A"]})

            assert result == ({"list": "['A']"}, None)

        def allows_lists_to_contain_null():
            doc = """
                query ($input: [String]) {
                  list(input: $input)
                }
                """

            result = execute_query(doc, {"input": ["A", None, "B"]})

            assert result == ({"list": "['A', None, 'B']"}, None)

        def does_not_allow_non_null_lists_to_be_null():
            doc = """
                query ($input: [String]!) {
                  nnList(input: $input)
                }
                """

            result = execute_query(doc, {"input": None})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' of non-null type '[String]!'"
                        " must not be null.",
                        "locations": [(2, 24)],
                        "path": None,
                    }
                ],
            )

        def allows_non_null_lists_to_contain_values():
            doc = """
                query ($input: [String]!) {
                  nnList(input: $input)
                }
                """

            result = execute_query(doc, {"input": ["A"]})

            assert result == ({"nnList": "['A']"}, None)

        def allows_non_null_lists_to_contain_null():
            doc = """
                query ($input: [String]!) {
                  nnList(input: $input)
                }
                """

            result = execute_query(doc, {"input": ["A", None, "B"]})

            assert result == ({"nnList": "['A', None, 'B']"}, None)

        def allows_lists_of_non_nulls_to_be_null():
            doc = """
                query ($input: [String!]) {
                  listNN(input: $input)
                }
                """

            result = execute_query(doc, {"input": None})

            assert result == ({"listNN": "None"}, None)

        def allows_lists_of_non_nulls_to_contain_values():
            doc = """
                query ($input: [String!]) {
                  listNN(input: $input)
                }
                """

            result = execute_query(doc, {"input": ["A"]})

            assert result == ({"listNN": "['A']"}, None)

        def does_not_allow_lists_of_non_nulls_to_contain_null():
            doc = """
                query ($input: [String!]) {
                  listNN(input: $input)
                }
                """
            result = execute_query(doc, {"input": ["A", None, "B"]})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' got invalid value None"
                        " at 'input[1]';"
                        " Expected non-nullable type 'String!' not to be None.",
                        "locations": [(2, 24)],
                    }
                ],
            )

        def does_not_allow_non_null_lists_of_non_nulls_to_be_null():
            doc = """
                query ($input: [String!]!) {
                  nnListNN(input: $input)
                }
                """
            result = execute_query(doc, {"input": None})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' of non-null type '[String!]!'"
                        " must not be null.",
                        "locations": [(2, 24)],
                    }
                ],
            )

        def allows_non_null_lists_of_non_nulls_to_contain_values():
            doc = """
                query ($input: [String!]!) {
                  nnListNN(input: $input)
                }
                """
            result = execute_query(doc, {"input": ["A"]})

            assert result == ({"nnListNN": "['A']"}, None)

        def does_not_allow_non_null_lists_of_non_nulls_to_contain_null():
            doc = """
                query ($input: [String!]!) {
                  nnListNN(input: $input)
                }
                """
            result = execute_query(doc, {"input": ["A", None, "B"]})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' got invalid value None"
                        " at 'input[1]';"
                        " Expected non-nullable type 'String!' not to be None.",
                        "locations": [(2, 24)],
                        "path": None,
                    }
                ],
            )

        def does_not_allow_invalid_types_to_be_used_as_values():
            doc = """
                query ($input: TestType!) {
                  fieldWithObjectInput(input: $input)
                }
                """
            result = execute_query(doc, {"input": {"list": ["A", "B"]}})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' expected value"
                        " of type 'TestType!' which cannot"
                        " be used as an input type.",
                        "locations": [(2, 32)],
                    }
                ],
            )

        def does_not_allow_unknown_types_to_be_used_as_values():
            doc = """
                query ($input: UnknownType!) {
                  fieldWithObjectInput(input: $input)
                }
                """
            result = execute_query(doc, {"input": "whoKnows"})

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$input' expected value"
                        " of type 'UnknownType!' which cannot"
                        " be used as an input type.",
                        "locations": [(2, 32)],
                    }
                ],
            )

    def describe_execute_uses_argument_default_values():
        def when_no_argument_provided():
            result = execute_query("{ fieldWithDefaultArgumentValue }")

            assert result == ({"fieldWithDefaultArgumentValue": "'Hello World'"}, None)

        def when_omitted_variable_provided():
            result = execute_query("""
                query ($optional: String) {
                  fieldWithDefaultArgumentValue(input: $optional)
                }
                """)

            assert result == ({"fieldWithDefaultArgumentValue": "'Hello World'"}, None)

        def not_when_argument_cannot_be_coerced():
            result = execute_query("""
                {
                  fieldWithDefaultArgumentValue(input: WRONG_TYPE)
                }
                """)

            assert result == (
                {"fieldWithDefaultArgumentValue": None},
                [
                    {
                        "message": "Argument 'input' has invalid value WRONG_TYPE.",
                        "locations": [(3, 56)],
                        "path": ["fieldWithDefaultArgumentValue"],
                    }
                ],
            )

        def when_no_runtime_value_is_provided_to_a_non_null_argument():
            result = execute_query("""
                query optionalVariable($optional: String) {
                  fieldWithNonNullableStringInputAndDefaultArgValue(input: $optional)
                }
                """)

            assert result == (
                {"fieldWithNonNullableStringInputAndDefaultArgValue": "'Hello World'"},
                None,
            )

    def describe_get_variable_values_limit_maximum_number_of_coercion_errors():
        doc = parse("""
            query ($input: [String!]) {
              listNN(input: $input)
            }
            """)

        operation = doc.definitions[0]
        assert isinstance(operation, OperationDefinitionNode)
        variable_definitions = operation.variable_definitions
        assert variable_definitions is not None

        input_value = {"input": [0, 1, 2]}

        def _invalid_value_error(value: int, index: int) -> Dict[str, Any]:
            return {
                "message": "Variable '$input' got invalid value"
                f" {value} at 'input[{index}]';"
                f" String cannot represent a non string value: {value}",
                "locations": [(2, 20)],
            }

        def return_all_errors_by_default():
            result = get_variable_values(schema, variable_definitions, input_value)

            assert result == [
                _invalid_value_error(0, 0),
                _invalid_value_error(1, 1),
                _invalid_value_error(2, 2),
            ]

        def when_max_errors_is_equal_to_number_of_errors():
            result = get_variable_values(
                schema, variable_definitions, input_value, max_errors=3
            )

            assert result == [
                _invalid_value_error(0, 0),
                _invalid_value_error(1, 1),
                _invalid_value_error(2, 2),
            ]

        def when_max_errors_is_less_than_number_of_errors():
            result = get_variable_values(
                schema, variable_definitions, input_value, max_errors=2
            )

            assert result == [
                _invalid_value_error(0, 0),
                _invalid_value_error(1, 1),
                {
                    "message": "Too many errors processing variables,"
                    " error limit reached. Execution aborted."
                },
            ]


def describe_too_deeply_nested_variable_values():
    schema = build_schema("""
        input Nested {
          nested: Nested
          nestedList: [Nested]
          leaf: Int
        }

        type Query {
          field(input: Nested, other: Int): String
        }
        """)

    source = "query ($input: Nested) { field(input: $input) }"
    document = parse(source)
    operation = document.definitions[0]
    assert isinstance(operation, OperationDefinitionNode)
    variable_definitions = operation.variable_definitions
    assert variable_definitions is not None

    message = "Variable values are nested too deeply."

    def _nested(depth: int, key: str = "nested") -> Dict[str, Any]:
        value: Dict[str, Any] = {"leaf": 1}
        for _ in range(depth):
            value = {key: [value] if key == "nestedList" else value}
        return value

    # Far beyond the recursion limit on all interpreters.
    too_deep = 100_000

    def _assert_nested_too_deeply(error: GraphQLError):
        assert error.message == message
        assert error.__traceback__ is None
        assert error.__context__ is None
        assert error.__cause__ is None

    def get_variable_values_returns_an_error():
        for key in ("nested", "nestedList"):
            result = get_variable_values(
                schema, variable_definitions, {"input": _nested(too_deep, key)}
            )
            assert isinstance(result, list)
            assert len(result) == 1
            _assert_nested_too_deeply(result[0])

    def get_variable_values_keeps_previous_errors():
        operation = parse(
            "query ($other: Int, $input: Nested) { field(other: $other) }"
        ).definitions[0]
        assert isinstance(operation, OperationDefinitionNode)
        assert operation.variable_definitions is not None
        result = get_variable_values(
            schema,
            operation.variable_definitions,
            {"other": "bad", "input": _nested(too_deep)},
        )
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].message.startswith("Variable '$other' got invalid value")
        _assert_nested_too_deeply(result[1])

    def execute_sync_returns_a_result_with_the_error():
        result = execute_sync(
            schema, document, variable_values={"input": _nested(too_deep)}
        )
        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        _assert_nested_too_deeply(result.errors[0])

    def graphql_sync_returns_a_result_with_the_error():
        result = graphql_sync(
            schema, source, variable_values={"input": _nested(too_deep)}
        )
        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        _assert_nested_too_deeply(result.errors[0])

    def still_accepts_a_depth_that_fits():
        value = _nested(50)
        result = get_variable_values(schema, variable_definitions, {"input": value})
        assert result == {"input": value}

        def resolve_field(_info, input):
            return "ok" if input == value else "bad"

        assert execute_sync(
            schema, document, {"field": resolve_field}, variable_values={"input": value}
        ) == ({"field": "ok"}, None)

    def accepts_values_up_to_the_maximum_nesting_depth():
        value = _nested(MAX_NESTING_DEPTH - 1)
        result = get_variable_values(schema, variable_definitions, {"input": value})
        assert not isinstance(result, list)
        assert result == {"input": value}

    def rejects_values_above_the_maximum_nesting_depth():
        value = _nested(MAX_NESTING_DEPTH + 1)
        result = get_variable_values(schema, variable_definitions, {"input": value})
        assert isinstance(result, list)
        _assert_nested_too_deeply(result[0])

    def checks_list_values_and_single_values_of_list_types():
        list_type = GraphQLList(GraphQLNonNull(GraphQLInt))
        assert not input_is_nested_too_deeply(1, list_type)
        assert not input_is_nested_too_deeply([1, 2], list_type)
        deep_value: Any = 1
        deep_type: Any = GraphQLInt
        for _ in range(MAX_NESTING_DEPTH + 1):
            deep_value = [deep_value]
            deep_type = GraphQLList(deep_type)
        assert input_is_nested_too_deeply(deep_value, deep_type)
        assert input_is_nested_too_deeply(1, deep_type)

    def ignores_values_that_are_no_objects_for_input_object_types():
        input_type = GraphQLInputObjectType(
            "NoObject", {"a": GraphQLInputField(GraphQLInt)}
        )
        assert not input_is_nested_too_deeply("no object", input_type)

    def accepts_deep_values_of_custom_scalars():
        deep: Any = 1
        for _ in range(MAX_NESTING_DEPTH * 2):
            deep = {"a": deep}
        assert not input_is_nested_too_deeply(deep, GraphQLScalarType("Json"))

    def does_not_keep_the_frames_of_the_recursion_alive(monkeypatch):
        refs: List[weakref.ref] = []
        monkeypatch.setattr(
            "graphql.execution.values.input_is_nested_too_deeply", lambda *_args: False
        )
        module = import_module("graphql.utilities.coerce_input_value")
        coerce_input_value = module.coerce_input_value

        class Tracked:
            pass

        def tracked_coerce_input_value(*args, **kwargs):
            tracked = Tracked()
            refs.append(weakref.ref(tracked))
            return coerce_input_value(*args, **kwargs)

        monkeypatch.setattr(module, "coerce_input_value", tracked_coerce_input_value)
        result = get_variable_values(
            schema, variable_definitions, {"input": _nested(too_deep)}
        )
        gc.collect()
        assert len(refs) > 10
        assert all(ref() is None for ref in refs)
        assert isinstance(result, list)
        _assert_nested_too_deeply(result[0])
