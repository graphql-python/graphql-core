from math import nan

from graphql.error import INVALID
from graphql.execution import execute
from graphql.language import parse
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

TestComplexScalar = GraphQLScalarType(
    name="ComplexScalar",
    serialize=lambda value: "SerializedValue" if value == "DeserializedValue" else None,
    parse_value=lambda value: "DeserializedValue"
    if value == "SerializedValue"
    else None,
    parse_literal=lambda ast, _variables=None: "DeserializedValue"
    if ast.value == "SerializedValue"
    else None,
)


TestInputObject = GraphQLInputObjectType(
    "TestInputObject",
    {
        "a": GraphQLInputField(GraphQLString),
        "b": GraphQLInputField(GraphQLList(GraphQLString)),
        "c": GraphQLInputField(GraphQLNonNull(GraphQLString)),
        "d": GraphQLInputField(TestComplexScalar),
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
        "UNDEFINED": INVALID,
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
        resolve=lambda _obj, _info, **args: repr(args["input"])
        if "input" in args
        else None,
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


def execute_query(query, variable_values=None):
    document = parse(query)
    return execute(schema, document, variable_values=variable_values)


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
                            "message": "Argument 'input' has invalid value"
                            ' ["foo", "bar", "baz"].',
                            "path": ["fieldWithObjectInput"],
                            "locations": [(3, 51)],
                        }
                    ],
                )

            def properly_runs_parse_literal_on_complex_scalar_types():
                result = execute_query(
                    """
                    {
                      fieldWithObjectInput(input: {c: "foo", d: "SerializedValue"})
                    }
                    """
                )

                assert result == (
                    {"fieldWithObjectInput": "{'c': 'foo', 'd': 'DeserializedValue'}"},
                    None,
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
                params = {"input": {"c": "foo", "d": "SerializedValue"}}
                result = execute_query(doc, params)

                assert result == (
                    {"fieldWithObjectInput": "{'c': 'foo', 'd': 'DeserializedValue'}"},
                    None,
                )

            def errors_on_null_for_nested_non_null():
                params = {"input": {"a": "foo", "b": "bar", "c": None}}
                result = execute_query(doc, params)

                assert result == (
                    None,
                    [
                        {
                            "message": "Variable '$input' got invalid value"
                            " {'a': 'foo', 'b': 'bar', 'c': None};"
                            " Expected non-nullable type String!"
                            " not to be null at value.c.",
                            "locations": [(2, 24)],
                            "path": None,
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
                            " Expected type TestInputObject to be a dict.",
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
                            " {'a': 'foo', 'b': 'bar'}; Field value.c"
                            " of required type String! was not provided.",
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
                            " {'na': {'a': 'foo'}}; Field value.na.c"
                            " of required type String! was not provided.",
                            "locations": [(2, 28)],
                        },
                        {
                            "message": "Variable '$input' got invalid value"
                            " {'na': {'a': 'foo'}}; Field value.nb"
                            " of required type String! was not provided.",
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
                            " 'extra' is not defined by type TestInputObject.",
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
                        "message": "Variable '$value' got invalid value [1, 2, 3];"
                        " Expected type String. String cannot represent"
                        " a non string value: [1, 2, 3]",
                        "locations": [(2, 24)],
                        "path": None,
                    }
                ],
            )

            assert isinstance(result.errors[0].original_error, TypeError)

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
                        "message": "Variable '$input' got invalid value"
                        " ['A', None, 'B']; Expected non-nullable type"
                        " String! not to be null at value[1].",
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
                        "message": "Variable '$input' got invalid value"
                        " ['A', None, 'B']; Expected non-nullable type"
                        " String! not to be null at value[1].",
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
            result = execute_query(doc, {"input": "whoknows"})

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
                        "message": "Argument 'input' has invalid value WRONG_TYPE.",
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
