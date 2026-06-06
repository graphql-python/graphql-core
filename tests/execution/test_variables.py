from __future__ import annotations

from math import nan
from typing import Any

from graphql.error import GraphQLError
from graphql.execution import ExecutionResult, execute_sync
from graphql.execution.values import get_variable_values
from graphql.language import OperationDefinitionNode, StringValueNode, ValueNode, parse
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFloat,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
)


def make_faulty_scalar_error() -> GraphQLError:
    # Note: unlike GraphQL.js, a fresh error is raised on each call. The runtime
    # argument-coercion fallback now mutates the error message in place, so a
    # shared singleton would otherwise leak the mutated message into other tests
    # (test order is randomized).
    return GraphQLError(
        "FaultyScalarErrorMessage", extensions={"code": "FaultyScalarExtensionCode"}
    )


def faulty_coerce_input_value(_value: str) -> str:
    raise make_faulty_scalar_error()


def faulty_coerce_input_literal(_ast: ValueNode) -> str:
    raise make_faulty_scalar_error()


TestFaultyScalar = GraphQLScalarType(
    name="FaultyScalar",
    coerce_input_value=faulty_coerce_input_value,
    coerce_input_literal=faulty_coerce_input_literal,
)


def coerce_complex_input_value(value: str) -> str:
    assert value == "ExternalValue"
    return "InternalValue"


def coerce_input_literal_value(ast: ValueNode) -> str:
    assert isinstance(ast, StringValueNode)
    assert ast.value == "ExternalValue"
    return coerce_complex_input_value(ast.value)


TestComplexScalar = GraphQLScalarType(
    name="ComplexScalar",
    coerce_input_value=coerce_complex_input_value,
    coerce_input_literal=coerce_input_literal_value,
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


TestOneOfInputObject = GraphQLInputObjectType(
    "TestOneOfInputObject",
    {
        "a": GraphQLInputField(GraphQLString),
        "b": GraphQLInputField(GraphQLString),
    },
    is_one_of=True,
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


NestedType = GraphQLObjectType(
    "NestedType",
    {
        "echo": field_with_input_arg(GraphQLArgument(GraphQLString)),
    },
)


TestType = GraphQLObjectType(
    "TestType",
    {
        "fieldWithEnumInput": field_with_input_arg(GraphQLArgument(TestEnum)),
        "fieldWithNonNullableEnumInput": field_with_input_arg(
            GraphQLArgument(GraphQLNonNull(TestEnum))
        ),
        "fieldWithObjectInput": field_with_input_arg(GraphQLArgument(TestInputObject)),
        "fieldWithOneOfObjectInput": field_with_input_arg(
            GraphQLArgument(TestOneOfInputObject)
        ),
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
            GraphQLArgument(TestNestedInputObject)
        ),
        "nested": GraphQLField(NestedType, resolve=lambda *_args: {}),
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
    query: str, variable_values: dict[str, Any] | None = None
) -> ExecutionResult:
    document = parse(query)
    return execute_sync(schema, document, variable_values=variable_values)


def execute_query_with_fragment_arguments(
    query: str, variable_values: dict[str, Any] | None = None
) -> ExecutionResult:
    document = parse(query, experimental_fragment_arguments=True)
    return execute_sync(schema, document, variable_values=variable_values)


def describe_execute_handles_inputs():
    def describe_handles_objects_and_nullability():
        def describe_using_inline_struct():
            def executes_with_complex_input():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(
                        input: {a: "foo", b: ["bar"], c: "baz"})
                    }
                    """
                )

                assert result == (
                    {"fieldWithObjectInput": "{'a': 'foo', 'b': ['bar'], 'c': 'baz'}"},
                    None,
                )

            def executes_with_custom_input():
                # This is an extension of GraphQL.js.
                result = execute_query(
                    """
                    {
                      fieldWithCustomObjectInput(
                        input: {x: -3.0, y: 4.5})
                    }
                    """
                )

                assert result == (
                    {"fieldWithCustomObjectInput": "'(x|y) = (-3.0|4.5)'"},
                    None,
                )

            def properly_parses_single_value_to_list():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(input: {a: "foo", b: "bar", c: "baz"})
                    }
                    """
                )

                assert result == (
                    {"fieldWithObjectInput": "{'a': 'foo', 'b': ['bar'], 'c': 'baz'}"},
                    None,
                )

            def properly_parses_null_value_to_null():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(
                        input: {a: null, b: null, c: "C", d: null})
                    }
                    """
                )

                assert result == (
                    {
                        "fieldWithObjectInput": "{'a': None, 'b': None,"
                        " 'c': 'C', 'd': None}"
                    },
                    None,
                )

            def properly_parses_null_value_in_list():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(input: {b: ["A",null,"C"], c: "C"})
                    }
                    """
                )

                assert result == (
                    {"fieldWithObjectInput": "{'b': ['A', None, 'C'], 'c': 'C'}"},
                    None,
                )

            def does_not_use_incorrect_value():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(input: ["foo", "bar", "baz"])
                    }
                    """
                )

                assert result == (
                    {"fieldWithObjectInput": None},
                    [
                        {
                            "message": "Argument 'input' has invalid value:"
                            " Expected value of type 'TestInputObject'"
                            ' to be an object, found: ["foo", "bar", "baz"].',
                            "path": ["fieldWithObjectInput"],
                            "locations": [(3, 51)],
                        }
                    ],
                )

            def properly_runs_coerce_input_literal_on_complex_scalar_types():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(input: {c: "foo", d: "ExternalValue"})
                    }
                    """
                )

                assert result == (
                    {"fieldWithObjectInput": "{'c': 'foo', 'd': 'InternalValue'}"},
                    None,
                )

            def errors_on_faulty_scalar_type_input():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(input: {c: "foo", e: "bar"})
                    }
                    """
                )

                assert result == (
                    {"fieldWithObjectInput": None},
                    [
                        {
                            "message": "Argument 'input' has invalid value at .e:"
                            " FaultyScalarErrorMessage",
                            "path": ["fieldWithObjectInput"],
                            "locations": [(3, 23)],
                            "extensions": {"code": "FaultyScalarExtensionCode"},
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
                result = execute_query(
                    """
                    query ($input: TestInputObject = {
                      a: "foo", b: ["bar"], c: "baz"}) {
                        fieldWithObjectInput(input: $input)
                    }
                    """
                )

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
                params = {"input": {"c": "foo", "d": "ExternalValue"}}
                result = execute_query(doc, params)

                assert result == (
                    {"fieldWithObjectInput": "{'c': 'foo', 'd': 'InternalValue'}"},
                    None,
                )

            def errors_on_faulty_scalar_type_input():
                params = {"input": {"c": "foo", "e": "ExternalValue"}}
                result = execute_query(doc, params)

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' has invalid value at .e:"
                            " FaultyScalarErrorMessage",
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
                            "message": "Variable '$input' has invalid value at .c:"
                            " Expected value of non-null type 'String!'"
                            " not to be None.",
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
                            "message": "Variable '$input' has invalid value:"
                            " Expected value of type 'TestInputObject'"
                            " to be an object, found: 'foo bar'.",
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
                            "message": "Variable '$input' has invalid value:"
                            " Expected value of type 'TestInputObject'"
                            " to include required field 'c',"
                            " found: {'a': 'foo', 'b': 'bar'}.",
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
                            "message": "Variable '$input' has invalid value at .na:"
                            " Expected value of type 'TestInputObject'"
                            " to include required field 'c',"
                            " found: {'a': 'foo'}.",
                            "locations": [(2, 28)],
                        },
                        {
                            "message": "Variable '$input' has invalid value:"
                            " Expected value of type 'TestNestedInputObject'"
                            " to include required field 'nb',"
                            " found: {'na': {'a': 'foo'}}.",
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
                            "message": "Variable '$input' has invalid value:"
                            " Expected value of type 'TestInputObject'"
                            " not to include unknown field 'extra', found:"
                            " {'a': 'foo', 'b': 'bar', 'c': 'baz', 'extra': 'dog'}.",
                            "locations": [(2, 24)],
                        }
                    ],
                )

    def describe_handles_custom_enum_values():
        def allows_custom_enum_values_as_inputs():
            result = execute_query(
                """
                {
                  null: fieldWithEnumInput(input: NULL)
                  NaN: fieldWithEnumInput(input: NAN)
                  false: fieldWithEnumInput(input: FALSE)
                  customValue: fieldWithEnumInput(input: CUSTOM)
                  defaultValue: fieldWithEnumInput(input: DEFAULT_VALUE)
                }
                """
            )

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
            result = execute_query(
                """
                {
                   fieldWithNonNullableEnumInput(input: NULL)
                }
                """
            )

            assert result == ({"fieldWithNonNullableEnumInput": "None"}, None)

    def describe_handles_nullable_scalars():
        def allows_nullable_inputs_to_be_omitted():
            result = execute_query(
                """
                {
                  fieldWithNullableStringInput
                }
                """
            )

            assert result == ({"fieldWithNullableStringInput": None}, None)

        def allows_nullable_inputs_to_be_omitted_in_a_variable():
            result = execute_query(
                """
                query ($value: String) {
                  fieldWithNullableStringInput(input: $value)
                }
                """
            )

            assert result == ({"fieldWithNullableStringInput": None}, None)

        def allows_nullable_inputs_to_be_omitted_in_an_unlisted_variable():
            result = execute_query(
                """
                query SetsNullable {
                  fieldWithNullableStringInput(input: $value)
                }
                """
            )

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
            result = execute_query(
                """
                {
                  fieldWithNullableStringInput(input: "a")
                }
                """
            )

            assert result == ({"fieldWithNullableStringInput": "'a'"}, None)

    def describe_handles_non_nullable_scalars():
        def allows_non_nullable_variable_to_be_omitted_given_a_default():
            result = execute_query(
                """
                query ($value: String! = "default") {
                  fieldWithNullableStringInput(input: $value)
                }
                """
            )

            assert result == ({"fieldWithNullableStringInput": "'default'"}, None)

        def allows_non_nullable_inputs_to_be_omitted_given_a_default():
            result = execute_query(
                """
                query ($value: String = "default") {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            )

            assert result == ({"fieldWithNonNullableStringInput": "'default'"}, None)

        def does_not_allow_non_nullable_inputs_to_be_omitted_in_a_variable():
            result = execute_query(
                """
                query ($value: String!) {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            )

            assert result == (
                None,
                [
                    {
                        "message": "Variable '$value' has invalid value:"
                        " Expected a value of non-null type 'String!'"
                        " to be provided.",
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
                        "message": "Variable '$value' has invalid value:"
                        " Expected value of non-null type 'String!'"
                        " not to be None.",
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
            result = execute_query(
                """
                {
                  fieldWithNonNullableStringInput(input: "a")
                }
                """
            )

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
                        "message": "Variable '$value' has invalid value:"
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
            result = execute_query(
                """
                {
                  fieldWithNonNullableStringInput(input: $foo)
                }
                """
            )

            assert result == (
                {"fieldWithNonNullableStringInput": None},
                [
                    {
                        "message": "Argument 'input' has invalid value:"
                        " Expected variable '$foo' provided to type 'String!'"
                        " to provide a runtime value.",
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
                        "message": "Variable '$input' has invalid value:"
                        " Expected value of non-null type '[String]!'"
                        " not to be None.",
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
                        "message": "Variable '$input' has invalid value at [1]:"
                        " Expected value of non-null type 'String!'"
                        " not to be None.",
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
                        "message": "Variable '$input' has invalid value:"
                        " Expected value of non-null type '[String!]!'"
                        " not to be None.",
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
                        "message": "Variable '$input' has invalid value at [1]:"
                        " Expected value of non-null type 'String!'"
                        " not to be None.",
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

    def describe_using_fragment_arguments():
        def when_there_are_no_fragment_arguments():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a
                }
                fragment a on TestType {
                  fieldWithNonNullableStringInput(input: "A")
                }
                """
            )
            assert result == (
                {"fieldWithNonNullableStringInput": "'A'"},
                None,
            )

        def when_a_value_is_required_and_provided():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(value: "A")
                }
                fragment a($value: String!) on TestType {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            )
            assert result == (
                {"fieldWithNonNullableStringInput": "'A'"},
                None,
            )

        def when_a_value_is_required_and_not_provided():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a
                }
                fragment a($value: String!) on TestType {
                  fieldWithNullableStringInput(input: $value)
                }
                """
            )
            assert result.errors is not None
            assert len(result.errors) == 1
            assert result.errors[0].message.startswith(
                "Argument 'value' of required type 'String!'"
            )

        def when_the_definition_has_a_default_and_is_provided():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(value: "A")
                }
                fragment a($value: String! = "B") on TestType {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            )
            assert result == (
                {"fieldWithNonNullableStringInput": "'A'"},
                None,
            )

        def when_the_definition_has_a_default_and_is_not_provided():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a
                }
                fragment a($value: String! = "B") on TestType {
                  fieldWithNonNullableStringInput(input: $value)
                }
                """
            )
            assert result == (
                {"fieldWithNonNullableStringInput": "'B'"},
                None,
            )

        def when_a_default_is_not_provided_and_spreads_another_fragment():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a
                }
                fragment a($a: String! = "B") on TestType {
                  ...b(b: $a)
                }
                fragment b($b: String!) on TestType {
                  fieldWithNonNullableStringInput(input: $b)
                }
                """
            )
            assert result == (
                {"fieldWithNonNullableStringInput": "'B'"},
                None,
            )

        def when_the_definition_has_a_non_nullable_default_and_is_provided_null():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(value: null)
                }
                fragment a($value: String! = "B") on TestType {
                  fieldWithNullableStringInput(input: $value)
                }
                """
            )
            assert result.errors is not None
            assert len(result.errors) == 1
            assert result.errors[0].message.startswith(
                "Argument 'value' has invalid value:"
                " Expected value of non-null type 'String!' not to be None."
            )

        def when_the_definition_has_no_default_and_is_not_provided():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a
                }
                fragment a($value: String) on TestType {
                  fieldWithNonNullableStringInputAndDefaultArgValue(input: $value)
                }
                """
            )
            assert result == (
                {"fieldWithNonNullableStringInputAndDefaultArgValue": "'Hello World'"},
                None,
            )

        def when_an_argument_is_shadowed_by_an_operation_variable():
            result = execute_query_with_fragment_arguments(
                """
                query($x: String! = "A") {
                  ...a(x: "B")
                }
                fragment a($x: String) on TestType {
                  fieldWithNullableStringInput(input: $x)
                }
                """
            )
            assert result == (
                {"fieldWithNullableStringInput": "'B'"},
                None,
            )

        def when_a_nullable_argument_without_field_default_is_shadowed():
            result = execute_query_with_fragment_arguments(
                """
                query($x: String = "A") {
                  ...a
                }
                fragment a($x: String) on TestType {
                  fieldWithNullableStringInput(input: $x)
                }
                """
            )
            assert result == (
                {"fieldWithNullableStringInput": None},
                None,
            )

        def when_a_nullable_argument_with_field_default_is_shadowed():
            result = execute_query_with_fragment_arguments(
                """
                query($x: String = "A") {
                  ...a
                }
                fragment a($x: String) on TestType {
                  fieldWithNonNullableStringInputAndDefaultArgValue(input: $x)
                }
                """
            )
            assert result == (
                {"fieldWithNonNullableStringInputAndDefaultArgValue": "'Hello World'"},
                None,
            )

        def when_a_fragment_variable_is_shadowed_but_defined_in_op_variables():
            result = execute_query_with_fragment_arguments(
                """
                query($x: String = "A") {
                  ...a
                }
                fragment a($x: String) on TestType {
                  ...b
                }

                fragment b on TestType {
                  fieldWithNullableStringInput(input: $x)
                }
                """
            )
            assert result == (
                {"fieldWithNullableStringInput": "'A'"},
                None,
            )

        def when_a_fragment_is_used_with_different_args():
            result = execute_query_with_fragment_arguments(
                """
                query($x: String = "Hello") {
                  a: nested {
                    ...a(x: "a")
                  }
                  b: nested {
                    ...a(x: "b", b: true)
                  }
                  hello: nested {
                    ...a(x: $x)
                  }
                }
                fragment a($x: String, $b: Boolean = false) on NestedType {
                  a: echo(input: $x) @skip(if: $b)
                  b: echo(input: $x) @include(if: $b)
                }
                """
            )
            assert result == (
                {
                    "a": {"a": "'a'"},
                    "b": {"b": "'b'"},
                    "hello": {"a": "'Hello'"},
                },
                None,
            )

        def when_the_argument_variable_is_nested_in_a_complex_type():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(value: "C")
                }
                fragment a($value: String) on TestType {
                  list(input: ["A", "B", $value, "D"])
                }
                """
            )
            assert result == (
                {"list": "['A', 'B', 'C', 'D']"},
                None,
            )

        def when_argument_variables_are_used_recursively():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(aValue: "C")
                }
                fragment a($aValue: String) on TestType {
                  ...b(bValue: $aValue)
                }
                fragment b($bValue: String) on TestType {
                  list(input: ["A", "B", $bValue, "D"])
                }
                """
            )
            assert result == (
                {"list": "['A', 'B', 'C', 'D']"},
                None,
            )

        def when_same_name_argument_variables_used_directly_and_recursively():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(value: "A")
                }
                fragment a($value: String!) on TestType {
                  ...b(value: "B")
                  fieldInFragmentA: fieldWithNonNullableStringInput(input: $value)
                }
                fragment b($value: String!) on TestType {
                  fieldInFragmentB: fieldWithNonNullableStringInput(input: $value)
                }
                """
            )
            assert result == (
                {
                    "fieldInFragmentA": "'A'",
                    "fieldInFragmentB": "'B'",
                },
                None,
            )

        def when_argument_passed_in_as_list():
            result = execute_query_with_fragment_arguments(
                """
                query Q($opValue: String = "op") {
                  ...a(aValue: "A")
                }
                fragment a($aValue: String, $bValue: String) on TestType {
                  ...b(aValue: [$aValue, "B"], bValue: [$bValue, $opValue])
                }
                fragment b(
                  $aValue: [String], $bValue: [String], $cValue: String
                ) on TestType {
                  aList: list(input: $aValue)
                  bList: list(input: $bValue)
                  cList: list(input: [$cValue])
                }
                """
            )
            assert result == (
                {
                    "aList": "['A', 'B']",
                    "bList": "[None, 'op']",
                    "cList": "[None]",
                },
                None,
            )

        def when_argument_passed_to_a_directive():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(value: true)
                }
                fragment a($value: Boolean!) on TestType {
                  fieldWithNonNullableStringInput @skip(if: $value)
                }
                """
            )
            assert result == ({}, None)

        def when_argument_passed_to_a_directive_on_a_nested_field():
            result = execute_query_with_fragment_arguments(
                """
                query {
                  ...a(value: true)
                }
                fragment a($value: Boolean!) on TestType {
                  nested { echo(input: "echo") @skip(if: $value) }
                }
                """
            )
            assert result == ({"nested": {}}, None)

    def describe_execute_uses_argument_default_values():
        def when_no_argument_provided():
            result = execute_query("{ fieldWithDefaultArgumentValue }")

            assert result == ({"fieldWithDefaultArgumentValue": "'Hello World'"}, None)

        def when_omitted_variable_provided():
            result = execute_query(
                """
                query ($optional: String) {
                  fieldWithDefaultArgumentValue(input: $optional)
                }
                """
            )

            assert result == ({"fieldWithDefaultArgumentValue": "'Hello World'"}, None)

        def not_when_argument_cannot_be_coerced():
            result = execute_query(
                """
                {
                  fieldWithDefaultArgumentValue(input: WRONG_TYPE)
                }
                """
            )

            assert result == (
                {"fieldWithDefaultArgumentValue": None},
                [
                    {
                        "message": "Argument 'input' has invalid value:"
                        " String cannot represent a non string value: WRONG_TYPE",
                        "locations": [(3, 56)],
                        "path": ["fieldWithDefaultArgumentValue"],
                    }
                ],
            )

        def when_no_runtime_value_is_provided_to_a_non_null_argument():
            result = execute_query(
                """
                query optionalVariable($optional: String) {
                  fieldWithNonNullableStringInputAndDefaultArgValue(input: $optional)
                }
                """
            )

            assert result == (
                {"fieldWithNonNullableStringInputAndDefaultArgValue": "'Hello World'"},
                None,
            )

    def describe_get_variable_values_limit_maximum_number_of_coercion_errors():
        doc = parse(
            """
            query ($input: [String!]) {
              listNN(input: $input)
            }
            """
        )

        operation = doc.definitions[0]
        assert isinstance(operation, OperationDefinitionNode)
        variable_definitions = operation.variable_definitions
        assert variable_definitions is not None

        input_value = {"input": [0, 1, 2]}

        def _invalid_value_error(value: int, index: int) -> dict[str, Any]:
            return {
                "message": "Variable '$input' has invalid value"
                f" at [{index}]:"
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
