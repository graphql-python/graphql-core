from __future__ import annotations

from math import nan
from typing import TYPE_CHECKING, Any

from graphql.execution.get_variable_signature import GraphQLVariableSignature
from graphql.execution.values import (
    FragmentVariableValues,
    FragmentVariableValueSource,
    VariableValues,
    get_variable_values,
)
from graphql.language import TokenKind, parse_value
from graphql.language.parser import Parser
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLDefaultInput,
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
    GraphQLSchema,
)
from graphql.utilities import validate_input_literal, validate_input_value

if TYPE_CHECKING:
    from graphql.error import GraphQLError


def describe_validate_input_value():
    def _test(
        input_value: Any,
        type_: GraphQLInputType,
        expected: Any,
        hide_suggestions: bool = False,
    ) -> None:
        errors: list[dict[str, Any]] = []

        def on_error(error: GraphQLError, path: list[str | int]) -> None:
            errors.append({"error": error.message, "path": path})

        validate_input_value(input_value, type_, on_error, hide_suggestions)
        assert errors == expected

    def describe_for_graphql_non_null():
        TestNonNull = GraphQLNonNull(GraphQLInt)

        def returns_no_error_for_non_null_value():
            _test(1, TestNonNull, [])

        def returns_an_error_for_undefined_value():
            _test(
                Undefined,
                TestNonNull,
                [
                    {
                        "error": "Expected a value of non-null type 'Int!'"
                        " to be provided.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_null_value():
            _test(
                None,
                TestNonNull,
                [
                    {
                        "error": "Expected value of non-null type 'Int!'"
                        " not to be None.",
                        "path": [],
                    }
                ],
            )

    def describe_for_graphql_scalar():
        def _coerce_input_value(input_value):
            assert isinstance(input_value, dict)
            error = input_value.get("error")
            if error is not None:
                raise ValueError(error)
            return input_value.get("value", Undefined)

        TestScalar = GraphQLScalarType(
            "TestScalar", coerce_input_value=_coerce_input_value
        )

        def returns_no_error_for_valid_input():
            _test({"value": 1}, TestScalar, [])

        def returns_no_error_for_null_result():
            _test({"value": None}, TestScalar, [])

        def returns_no_error_for_nan_result():
            _test({"value": nan}, TestScalar, [])

        def returns_an_error_for_undefined_result():
            _test(
                {"value": Undefined},
                TestScalar,
                [
                    {
                        "error": "Expected value of type 'TestScalar',"
                        " found: {'value': Undefined}.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_undefined_result_with_error_message():
            input_value = {"error": "Some error message."}
            _test(
                input_value,
                TestScalar,
                [
                    {
                        "error": "Expected value of type 'TestScalar',"
                        " but encountered error 'Some error message.';"
                        " found: {'error': 'Some error message.'}.",
                        "path": [],
                    }
                ],
            )

    def describe_for_graphql_enum():
        TestEnum = GraphQLEnumType(
            "TestEnum", {"FOO": "InternalFoo", "BAR": 123_456_789}
        )

        def returns_no_error_for_a_known_enum_name():
            _test("FOO", TestEnum, [])
            _test("BAR", TestEnum, [])

        def returns_an_error_for_unknown_enum_value():
            _test(
                "UNKNOWN",
                TestEnum,
                [
                    {
                        "error": "Value 'UNKNOWN' does not exist in 'TestEnum' enum.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_misspelled_enum_value():
            _test(
                "foo",
                TestEnum,
                [
                    {
                        "error": "Value 'foo' does not exist in 'TestEnum' enum."
                        " Did you mean the enum value 'FOO'?",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_misspelled_enum_value_no_suggestions():
            _test(
                "foo",
                TestEnum,
                [
                    {
                        "error": "Value 'foo' does not exist in 'TestEnum' enum.",
                        "path": [],
                    }
                ],
                True,
            )

        def returns_an_error_for_incorrect_value_type():
            _test(
                123,
                TestEnum,
                [
                    {
                        "error": "Enum 'TestEnum' cannot represent"
                        " non-string value: 123.",
                        "path": [],
                    }
                ],
            )

            _test(
                {"field": "value"},
                TestEnum,
                [
                    {
                        "error": "Enum 'TestEnum' cannot represent non-string value:"
                        " {'field': 'value'}.",
                        "path": [],
                    }
                ],
            )

        def reports_thrown_non_graphql_error():
            def _coerce_input_value(_input_value):
                raise RuntimeError("Not an error object.")

            TestThrowScalar = GraphQLScalarType(
                "TestScalar", coerce_input_value=_coerce_input_value
            )

            _test(
                {},
                TestThrowScalar,
                [
                    {
                        "error": "Expected value of type 'TestScalar',"
                        " but encountered error 'Not an error object.';"
                        " found: {}.",
                        "path": [],
                    }
                ],
            )

    def describe_for_graphql_input_object():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            lambda: {
                "foo": GraphQLInputField(GraphQLNonNull(GraphQLInt)),
                "bar": GraphQLInputField(GraphQLInt),
                "nested": GraphQLInputField(TestInputObject),
            },
        )

        def returns_no_error_for_a_valid_input():
            _test({"foo": 123}, TestInputObject, [])

        def returns_an_error_for_a_non_object_type():
            _test(
                123,
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " to be an object, found: 123.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_an_invalid_field():
            _test(
                {"foo": nan},
                TestInputObject,
                [
                    {
                        "error": "Int cannot represent non-integer value: nan",
                        "path": ["foo"],
                    }
                ],
            )

        def returns_multiple_errors_for_multiple_invalid_fields():
            _test(
                {"foo": "abc", "bar": "def"},
                TestInputObject,
                [
                    {
                        "error": "Int cannot represent non-integer value: 'abc'",
                        "path": ["foo"],
                    },
                    {
                        "error": "Int cannot represent non-integer value: 'def'",
                        "path": ["bar"],
                    },
                ],
            )

        def returns_error_for_a_missing_required_field():
            _test(
                {"bar": 123},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " to include required field 'foo', found: {'bar': 123}.",
                        "path": [],
                    }
                ],
            )

        def returns_error_for_an_unknown_field():
            _test(
                {"foo": 123, "unknownField": 123},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'unknownField',"
                        " found: {'foo': 123, 'unknownField': 123}.",
                        "path": [],
                    }
                ],
            )

        def ignores_unknown_fields_with_undefined_values():
            _test({"foo": 123, "unknownField": Undefined}, TestInputObject, [])

        def returns_error_when_supplied_with_an_array():
            _test(
                [{"foo": 123}, {"bar": 456}],
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " to be an object,"
                        " found: [{'foo': 123}, {'bar': 456}].",
                        "path": [],
                    }
                ],
            )

        def returns_error_when_a_nested_input_object_is_supplied_with_an_array():
            _test(
                {"foo": 123, "nested": [{"foo": 123}, {"bar": 456}]},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " to be an object,"
                        " found: [{'foo': 123}, {'bar': 456}].",
                        "path": ["nested"],
                    }
                ],
            )

        def returns_error_for_a_misspelled_field():
            _test(
                {"foo": 123, "bart": 123},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'bart'."
                        " Did you mean 'bar'?"
                        " Found: {'foo': 123, 'bart': 123}.",
                        "path": [],
                    }
                ],
            )

        def returns_error_for_a_misspelled_field_no_suggestions():
            _test(
                {"foo": 123, "bart": 123},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'bart',"
                        " found: {'foo': 123, 'bart': 123}.",
                        "path": [],
                    }
                ],
                True,
            )

    def describe_for_graphql_input_object_with_default_value():
        def _make_test_input_object(default_value):
            return GraphQLInputObjectType(
                "TestInputObject",
                {
                    "foo": GraphQLInputField(
                        GraphQLScalarType("TestScalar"),
                        default=GraphQLDefaultInput(value=default_value),
                    )
                },
            )

        def no_error_for_valid_input_value():
            _test({"foo": 5}, _make_test_input_object(7), [])

        def no_error_for_object_with_default_value():
            _test({}, _make_test_input_object(7), [])

        def no_error_for_null_as_value():
            _test({}, _make_test_input_object(None), [])

        def no_error_for_nan_as_value():
            _test({}, _make_test_input_object(nan), [])

    def describe_for_graphql_input_object_that_is_one_of():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "foo": GraphQLInputField(GraphQLInt),
                "bar": GraphQLInputField(GraphQLInt),
            },
            is_one_of=True,
        )

        def no_error_for_a_valid_input():
            _test({"foo": 123}, TestInputObject, [])

        def returns_error_if_more_than_one_field_is_specified():
            _test(
                {"foo": 123, "bar": None},
                TestInputObject,
                [
                    {
                        "error": "Exactly one key must be specified"
                        " for OneOf type 'TestInputObject'.",
                        "path": [],
                    }
                ],
            )

        def does_not_count_undefined_keys_as_provided():
            _test({"foo": 123, "bar": Undefined}, TestInputObject, [])

        def returns_error_if_the_one_field_is_null():
            _test(
                {"bar": None},
                TestInputObject,
                [
                    {
                        "error": "Field 'bar' for OneOf type 'TestInputObject'"
                        " must be non-null.",
                        "path": [],
                    }
                ],
            )

        def returns_error_for_an_invalid_field():
            _test(
                {"foo": nan},
                TestInputObject,
                [
                    {
                        "error": "Int cannot represent non-integer value: nan",
                        "path": ["foo"],
                    }
                ],
            )

        def returns_multiple_errors_for_multiple_invalid_fields():
            _test(
                {"foo": "abc", "bar": "def"},
                TestInputObject,
                [
                    {
                        "error": "Int cannot represent non-integer value: 'abc'",
                        "path": ["foo"],
                    },
                    {
                        "error": "Int cannot represent non-integer value: 'def'",
                        "path": ["bar"],
                    },
                    {
                        "error": "Exactly one key must be specified"
                        " for OneOf type 'TestInputObject'.",
                        "path": [],
                    },
                ],
            )

        def returns_error_for_an_unknown_field():
            _test(
                {"foo": 123, "unknownField": 123},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'unknownField',"
                        " found: {'foo': 123, 'unknownField': 123}.",
                        "path": [],
                    },
                    {
                        "error": "Exactly one key must be specified"
                        " for OneOf type 'TestInputObject'.",
                        "path": [],
                    },
                ],
            )

        def returns_error_for_a_misspelled_field():
            _test(
                {"bart": 123},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'bart'."
                        " Did you mean 'bar'? Found: {'bart': 123}.",
                        "path": [],
                    }
                ],
            )

        def returns_error_for_a_misspelled_field_no_suggestions():
            _test(
                {"bart": 123},
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'bart',"
                        " found: {'bart': 123}.",
                        "path": [],
                    }
                ],
                True,
            )

    def describe_for_graphql_list():
        TestList = GraphQLList(GraphQLInt)

        def returns_no_error_for_a_valid_input():
            _test([1, 2, 3], TestList, [])

        def returns_no_error_for_a_valid_iterable_input():
            def list_generator():
                yield 1
                yield 2
                yield 3

            _test(list_generator(), TestList, [])

        def returns_an_error_for_an_invalid_input():
            _test(
                [1, "b", True, 4],
                TestList,
                [
                    {
                        "error": "Int cannot represent non-integer value: 'b'",
                        "path": [1],
                    },
                    {
                        "error": "Int cannot represent non-integer value: True",
                        "path": [2],
                    },
                ],
            )

        def no_error_for_a_list_for_a_non_list_value():
            _test(42, TestList, [])

        def returns_an_error_for_a_non_list_invalid_value():
            _test(
                "INVALID",
                TestList,
                [
                    {
                        "error": "Int cannot represent non-integer value: 'INVALID'",
                        "path": [],
                    }
                ],
            )

        def no_error_for_null_for_a_null_value():
            _test(None, TestList, [])

    def describe_for_nested_graphql_list():
        TestNestedList = GraphQLList(GraphQLList(GraphQLInt))

        def no_error_for_a_valid_input():
            _test([[1], [2, 3]], TestNestedList, [])

        def no_error_for_a_list_for_a_non_list_value():
            _test(42, TestNestedList, [])

        def no_error_for_null_for_a_null_value():
            _test(None, TestNestedList, [])

        def no_error_for_nested_lists_for_nested_non_list_values():
            _test([1, 2, 3], TestNestedList, [])

        def no_error_for_nested_null_for_nested_null_values():
            _test([42, [None], None], TestNestedList, [])


def describe_validate_input_literal():
    def _test(
        input_value: str,
        type_: GraphQLInputType,
        expected: Any,
        variable_values: VariableValues | None = None,
        hide_suggestions: bool = False,
    ) -> None:
        errors: list[dict[str, Any]] = []

        def on_error(error: GraphQLError, path: list[str | int]) -> None:
            errors.append({"error": error.message, "path": path})

        validate_input_literal(
            parse_value(input_value),
            type_,
            on_error,
            variable_values,
            None,
            hide_suggestions,
        )
        assert errors == expected

    def _test_with_variables(
        variable_defs: str,
        values: dict[str, Any],
        input_value: str,
        type_: GraphQLInputType,
        expected: Any,
    ) -> None:
        parser = Parser(variable_defs)
        parser.expect_token(TokenKind.SOF)
        variable_values = get_variable_values(
            GraphQLSchema(types=[GraphQLInt]),
            parser.parse_variable_definitions() or (),
            values,
        )
        assert not isinstance(variable_values, list)
        _test(input_value, type_, expected, variable_values)

    def ignores_variables_statically():
        TestNonNull = GraphQLNonNull(GraphQLInt)
        _test("$var", TestNonNull, [])

    def uses_fragment_variable_values_when_present():
        # When a variable is provided by fragment variable values, those are
        # scoped in preference to the operation variable values.
        signature = GraphQLVariableSignature("var", GraphQLInt, None)
        fragment_variable_values = FragmentVariableValues(
            sources={"var": FragmentVariableValueSource(signature)},
            coerced={},
        )
        errors: list[dict[str, Any]] = []
        validate_input_literal(
            parse_value("$var"),
            GraphQLNonNull(GraphQLInt),
            lambda error, path: errors.append({"error": error.message, "path": path}),
            None,
            fragment_variable_values,
        )
        assert errors == [
            {
                "error": "Expected variable '$var' provided to type 'Int!'"
                " to provide a runtime value.",
                "path": [],
            }
        ]

    def returns_an_error_for_null_variables_for_non_nullable_types():
        TestNonNull = GraphQLNonNull(GraphQLInt)
        _test_with_variables(
            "($var: Int)",
            {"var": None},
            "$var",
            TestNonNull,
            [
                {
                    "error": "Expected variable '$var' provided to non-null type"
                    " 'Int!' not to be None.",
                    "path": [],
                }
            ],
        )

    def describe_for_graphql_non_null():
        TestNonNull = GraphQLNonNull(GraphQLInt)

        def returns_no_error_for_non_null_value():
            _test("1", TestNonNull, [])

        def returns_an_error_for_null_value():
            _test(
                "null",
                TestNonNull,
                [
                    {
                        "error": "Expected value of non-null type 'Int!'"
                        " not to be None.",
                        "path": [],
                    }
                ],
            )

    def describe_for_graphql_scalar():
        def _coerce_input_value(input_value):
            assert isinstance(input_value, dict)
            error = input_value.get("error")
            if error is not None:
                raise ValueError(error)
            return input_value.get("value", Undefined)

        TestScalar = GraphQLScalarType(
            "TestScalar", coerce_input_value=_coerce_input_value
        )

        def returns_no_error_for_valid_input():
            _test("{ value: 1 }", TestScalar, [])

        def returns_no_error_for_null_result():
            _test("{ value: null }", TestScalar, [])

        def returns_no_error_for_nan_result():
            _test("{ value: NaN }", TestScalar, [])

        def returns_an_error_for_undefined_result():
            _test(
                "{}",
                TestScalar,
                [
                    {
                        "error": "Expected value of type 'TestScalar', found: {  }.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_undefined_result_with_error_message():
            input_value = '{ error: "Some error message." }'
            _test(
                input_value,
                TestScalar,
                [
                    {
                        "error": "Expected value of type 'TestScalar',"
                        " but encountered error 'Some error message.';"
                        ' found: { error: "Some error message." }.',
                        "path": [],
                    }
                ],
            )

        def reports_thrown_non_graphql_error():
            def _coerce_input_value(_input_value):
                raise RuntimeError("Not an error object.")

            TestThrowScalar = GraphQLScalarType(
                "TestScalar", coerce_input_value=_coerce_input_value
            )

            _test(
                "{}",
                TestThrowScalar,
                [
                    {
                        "error": "Expected value of type 'TestScalar',"
                        " but encountered error 'Not an error object.';"
                        " found: {  }.",
                        "path": [],
                    }
                ],
            )

    def describe_for_graphql_enum():
        TestEnum = GraphQLEnumType(
            "TestEnum", {"FOO": "InternalFoo", "BAR": 123_456_789}
        )

        def returns_no_error_for_a_known_enum_name():
            _test("FOO", TestEnum, [])
            _test("BAR", TestEnum, [])

        def returns_an_error_for_unknown_enum_value():
            _test(
                "UNKNOWN",
                TestEnum,
                [
                    {
                        "error": "Value 'UNKNOWN' does not exist in 'TestEnum' enum.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_misspelled_enum_value():
            _test(
                "foo",
                TestEnum,
                [
                    {
                        "error": "Value 'foo' does not exist in 'TestEnum' enum."
                        " Did you mean the enum value 'FOO'?",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_misspelled_enum_value_no_suggestions():
            _test(
                "foo",
                TestEnum,
                [
                    {
                        "error": "Value 'foo' does not exist in 'TestEnum' enum.",
                        "path": [],
                    }
                ],
                None,
                True,
            )

        def returns_an_error_for_incorrect_value_type():
            _test(
                '"FOO"',
                TestEnum,
                [
                    {
                        "error": "Enum 'TestEnum' cannot represent non-enum value:"
                        " \"FOO\". Did you mean the enum value 'FOO'?",
                        "path": [],
                    }
                ],
            )

            _test(
                '"FOO"',
                TestEnum,
                [
                    {
                        "error": "Enum 'TestEnum' cannot represent non-enum value:"
                        ' "FOO".',
                        "path": [],
                    }
                ],
                None,
                True,
            )

            _test(
                '"UNKNOWN"',
                TestEnum,
                [
                    {
                        "error": "Enum 'TestEnum' cannot represent non-enum value:"
                        ' "UNKNOWN".',
                        "path": [],
                    }
                ],
            )

            _test(
                "123",
                TestEnum,
                [
                    {
                        "error": "Enum 'TestEnum' cannot represent non-enum value:"
                        " 123.",
                        "path": [],
                    }
                ],
            )

            _test(
                '{ field: "value" }',
                TestEnum,
                [
                    {
                        "error": "Enum 'TestEnum' cannot represent non-enum value:"
                        ' { field: "value" }.',
                        "path": [],
                    }
                ],
            )

    def describe_for_graphql_input_object():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "foo": GraphQLInputField(GraphQLNonNull(GraphQLInt)),
                "bar": GraphQLInputField(GraphQLInt),
                "optional": GraphQLInputField(
                    GraphQLNonNull(GraphQLInt), default=GraphQLDefaultInput(value=42)
                ),
            },
        )

        def returns_no_error_for_a_valid_input():
            _test("{ foo: 123 }", TestInputObject, [])

        def returns_an_error_for_a_non_object_type():
            _test(
                "123",
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " to be an object, found: 123.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_an_invalid_field():
            _test(
                "{ foo: 1.5 }",
                TestInputObject,
                [
                    {
                        "error": "Int cannot represent non-integer value: 1.5",
                        "path": ["foo"],
                    }
                ],
            )

        def returns_multiple_errors_for_multiple_invalid_fields():
            _test(
                '{ foo: "abc", bar: "def" }',
                TestInputObject,
                [
                    {
                        "error": 'Int cannot represent non-integer value: "abc"',
                        "path": ["foo"],
                    },
                    {
                        "error": 'Int cannot represent non-integer value: "def"',
                        "path": ["bar"],
                    },
                ],
            )

        def returns_error_for_a_missing_required_field():
            _test(
                "{ bar: 123 }",
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " to include required field 'foo', found: { bar: 123 }.",
                        "path": [],
                    }
                ],
            )

        def returns_error_for_an_unknown_field():
            _test(
                "{ foo: 123, unknownField: 123 }",
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'unknownField',"
                        " found: { foo: 123, unknownField: 123 }.",
                        "path": [],
                    }
                ],
            )

        def returns_error_for_a_misspelled_field():
            _test(
                "{ foo: 123, bart: 123 }",
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'bart'."
                        " Did you mean 'bar'? Found: { foo: 123, bart: 123 }.",
                        "path": [],
                    }
                ],
            )

        def allows_variables_in_an_object_statically():
            _test("{ foo: $var }", TestInputObject, [])

        def allows_correct_use_of_variables():
            _test_with_variables(
                "($var: Int)",
                {"var": 123},
                "{ foo: $var }",
                TestInputObject,
                [],
            )

        def allows_missing_variables_in_a_nullable_field():
            _test_with_variables("", {}, "{ foo: 123, bar: $var }", TestInputObject, [])
            _test_with_variables(
                "($var: Int)",
                {},
                "{ foo: 123, bar: $var }",
                TestInputObject,
                [],
            )

        def allows_missing_variables_in_an_optional_field():
            _test_with_variables(
                "($var: Int)",
                {},
                "{ foo: 123, optional: $var }",
                TestInputObject,
                [],
            )

        def errors_on_missing_variable_in_a_required_field():
            _test_with_variables(
                "($var: Int)",
                {},
                "{ foo: $var }",
                TestInputObject,
                [
                    {
                        "error": "Expected variable '$var' provided to type"
                        " 'Int!' to provide a runtime value.",
                        "path": ["foo"],
                    }
                ],
            )

        def errors_on_null_variable_in_a_non_null_field():
            _test_with_variables(
                "($var: Int)",
                {"var": None},
                "{ foo: 123, optional: $var }",
                TestInputObject,
                [
                    {
                        "error": "Expected variable '$var' provided to non-null type"
                        " 'Int!' not to be None.",
                        "path": ["optional"],
                    }
                ],
            )

    def describe_for_graphql_input_object_with_default_value():
        def _make_test_input_object(default_value):
            return GraphQLInputObjectType(
                "TestInputObject",
                {
                    "foo": GraphQLInputField(
                        GraphQLScalarType("TestScalar"),
                        default=GraphQLDefaultInput(value=default_value),
                    )
                },
            )

        def no_error_for_valid_input_value():
            _test("{ foo: 5 }", _make_test_input_object(7), [])

        def no_error_for_object_with_default_value():
            _test("{}", _make_test_input_object(7), [])

        def no_error_for_null_as_value():
            _test("{}", _make_test_input_object(None), [])

        def no_error_for_nan_as_value():
            _test("{}", _make_test_input_object(nan), [])

    def describe_for_graphql_input_object_that_is_one_of():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "foo": GraphQLInputField(GraphQLInt),
                "bar": GraphQLInputField(GraphQLInt),
            },
            is_one_of=True,
        )

        def returns_no_error_for_a_valid_input():
            _test("{ foo: 123 }", TestInputObject, [])

        def returns_an_error_if_more_than_one_field_is_specified():
            _test(
                "{ foo: 123, bar: null }",
                TestInputObject,
                [
                    {
                        "error": "OneOf Input Object 'TestInputObject'"
                        " must specify exactly one key.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_if_the_one_field_is_null():
            _test(
                "{ bar: null }",
                TestInputObject,
                [
                    {
                        "error": "Field 'TestInputObject.bar' used for OneOf"
                        " Input Object must be non-null.",
                        "path": ["bar"],
                    }
                ],
            )

        def returns_an_error_for_a_non_object_type():
            _test(
                "123",
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " to be an object, found: 123.",
                        "path": [],
                    }
                ],
            )

        def returns_an_error_for_an_invalid_field():
            _test(
                "{ foo: 1.5 }",
                TestInputObject,
                [
                    {
                        "error": "Int cannot represent non-integer value: 1.5",
                        "path": ["foo"],
                    }
                ],
            )

        def returns_error_for_an_unknown_field():
            _test(
                "{ foo: 123, unknownField: 123 }",
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'unknownField',"
                        " found: { foo: 123, unknownField: 123 }.",
                        "path": [],
                    },
                    {
                        "error": "OneOf Input Object 'TestInputObject'"
                        " must specify exactly one key.",
                        "path": [],
                    },
                ],
            )

        def returns_error_for_a_misspelled_field():
            _test(
                "{ foo: 123, bart: 123 }",
                TestInputObject,
                [
                    {
                        "error": "Expected value of type 'TestInputObject'"
                        " not to include unknown field 'bart'."
                        " Did you mean 'bar'? Found: { foo: 123, bart: 123 }.",
                        "path": [],
                    },
                    {
                        "error": "OneOf Input Object 'TestInputObject'"
                        " must specify exactly one key.",
                        "path": [],
                    },
                ],
            )

        def allows_variables_in_an_object_statically():
            _test("{ foo: $var }", TestInputObject, [])

        def allows_correct_use_of_variables():
            _test_with_variables(
                "($var: Int)",
                {"var": 123},
                "{ foo: $var }",
                TestInputObject,
                [],
            )

        def returns_error_with_variable_provided_a_value_of_null():
            _test_with_variables(
                "($var: Int)",
                {"var": None},
                "{ foo: $var }",
                TestInputObject,
                [
                    {
                        "error": "Expected variable '$var' provided to field 'foo'"
                        " for OneOf Input Object type 'TestInputObject'"
                        " not to be None.",
                        "path": [],
                    }
                ],
            )

        def errors_with_missing_variables_as_the_additional_field():
            _test_with_variables(
                "",
                {},
                "{ foo: 123, bar: $var }",
                TestInputObject,
                [
                    {
                        "error": "Expected variable '$var' provided to field 'bar'"
                        " for OneOf Input Object type 'TestInputObject'"
                        " to provide a runtime value.",
                        "path": [],
                    },
                    {
                        "error": "OneOf Input Object 'TestInputObject'"
                        " must specify exactly one key.",
                        "path": [],
                    },
                ],
            )
            _test_with_variables(
                "($var: Int)",
                {},
                "{ foo: 123, bar: $var }",
                TestInputObject,
                [
                    {
                        "error": "Expected variable '$var' provided to field 'bar'"
                        " for OneOf Input Object type 'TestInputObject'"
                        " to provide a runtime value.",
                        "path": [],
                    },
                    {
                        "error": "OneOf Input Object 'TestInputObject'"
                        " must specify exactly one key.",
                        "path": [],
                    },
                ],
            )

    def describe_for_graphql_list():
        TestList = GraphQLList(GraphQLInt)

        def returns_no_error_for_a_valid_input():
            _test("[1, 2, 3]", TestList, [])

        def returns_an_error_for_an_invalid_input():
            _test(
                '[1, "b", true, 4]',
                TestList,
                [
                    {
                        "error": 'Int cannot represent non-integer value: "b"',
                        "path": [1],
                    },
                    {
                        "error": "Int cannot represent non-integer value: true",
                        "path": [2],
                    },
                ],
            )

        def no_error_for_a_list_for_a_non_list_value():
            _test("42", TestList, [])

        def returns_an_error_for_a_non_list_invalid_value():
            _test(
                '"INVALID"',
                TestList,
                [
                    {
                        "error": 'Int cannot represent non-integer value: "INVALID"',
                        "path": [],
                    }
                ],
            )

        def no_error_for_null_for_a_null_value():
            _test("null", TestList, [])

        def allows_variables_in_a_list_statically():
            _test("[1, $var, 3]", TestList, [])

        def allows_missing_variables_in_a_list_which_coerce_to_null():
            _test_with_variables("($var: Int)", {}, "[1, $var, 3]", TestList, [])

        def errors_on_missing_variables_in_a_list_of_non_null():
            TestListNonNull = GraphQLList(GraphQLNonNull(GraphQLInt))
            _test_with_variables(
                "($var: Int)",
                {},
                "[1, $var, 3]",
                TestListNonNull,
                [
                    {
                        "error": "Expected variable '$var' provided to type"
                        " 'Int!' to provide a runtime value.",
                        "path": [1],
                    }
                ],
            )

        def errors_on_null_variables_in_a_list_of_non_null():
            TestListNonNull = GraphQLList(GraphQLNonNull(GraphQLInt))
            _test_with_variables(
                "($var: Int)",
                {"var": None},
                "[1, $var, 3]",
                TestListNonNull,
                [
                    {
                        "error": "Expected variable '$var' provided to non-null type"
                        " 'Int!' not to be None.",
                        "path": [1],
                    }
                ],
            )

    def describe_for_nested_graphql_list():
        TestNestedList = GraphQLList(GraphQLList(GraphQLInt))

        def no_error_for_a_valid_input():
            _test("[[1], [2, 3]]", TestNestedList, [])

        def no_error_for_a_list_for_a_non_list_value():
            _test("42", TestNestedList, [])

        def no_error_for_null_for_a_null_value():
            _test("null", TestNestedList, [])

        def no_error_for_nested_lists_for_nested_non_list_values():
            _test("[1, 2, 3]", TestNestedList, [])

        def no_error_for_nested_null_for_nested_null_values():
            _test("[42, [null], null]", TestNestedList, [])
