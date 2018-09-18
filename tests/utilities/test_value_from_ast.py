from math import nan, isnan
from pytest import fixture

from graphql.error import INVALID
from graphql.language import parse_value
from graphql.type import (
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLString,
)
from graphql.utilities import value_from_ast


def describe_value_from_ast():
    @fixture
    def test_case(type_, value_text, expected):
        value_node = parse_value(value_text)
        assert value_from_ast(value_node, type_) == expected

    @fixture
    def test_case_expect_nan(type_, value_text):
        value_node = parse_value(value_text)
        assert isnan(value_from_ast(value_node, type_))

    @fixture
    def test_case_with_vars(variables, type_, value_text, expected):
        value_node = parse_value(value_text)
        assert value_from_ast(value_node, type_, variables) == expected

    def rejects_empty_input():
        # noinspection PyTypeChecker
        assert value_from_ast(None, GraphQLBoolean) is INVALID

    def converts_according_to_input_coercion_rules():
        test_case(GraphQLBoolean, "true", True)
        test_case(GraphQLBoolean, "false", False)
        test_case(GraphQLInt, "123", 123)
        test_case(GraphQLFloat, "123", 123)
        test_case(GraphQLFloat, "123.456", 123.456)
        test_case(GraphQLString, '"abc123"', "abc123")
        test_case(GraphQLID, "123456", "123456")
        test_case(GraphQLID, '"123456"', "123456")

    def does_not_convert_when_input_coercion_rules_reject_a_value():
        test_case(GraphQLBoolean, "123", INVALID)
        test_case(GraphQLInt, "123.456", INVALID)
        test_case(GraphQLInt, "true", INVALID)
        test_case(GraphQLInt, '"123"', INVALID)
        test_case(GraphQLFloat, '"123"', INVALID)
        test_case(GraphQLString, "123", INVALID)
        test_case(GraphQLString, "true", INVALID)
        test_case(GraphQLID, "123.456", INVALID)

    test_enum = GraphQLEnumType(
        "TestColor",
        {"RED": 1, "GREEN": 2, "BLUE": 3, "NULL": None, "INVALID": INVALID, "NAN": nan},
    )

    def converts_enum_values_according_to_input_coercion_rules():
        test_case(test_enum, "RED", 1)
        test_case(test_enum, "BLUE", 3)
        test_case(test_enum, "YELLOW", INVALID)
        test_case(test_enum, "3", INVALID)
        test_case(test_enum, '"BLUE"', INVALID)
        test_case(test_enum, "null", None)
        test_case(test_enum, "NULL", None)
        test_case(test_enum, "INVALID", INVALID)
        # nan is not equal to itself, needs a special test case
        test_case_expect_nan(test_enum, "NAN")

    # Boolean!
    non_null_bool = GraphQLNonNull(GraphQLBoolean)
    # [Boolean]
    list_of_bool = GraphQLList(GraphQLBoolean)
    # [Boolean!]
    list_of_non_null_bool = GraphQLList(non_null_bool)
    # [Boolean]!
    non_null_list_of_bool = GraphQLNonNull(list_of_bool)
    # [Boolean!]!
    non_null_list_of_non_mull_bool = GraphQLNonNull(list_of_non_null_bool)

    def coerces_to_null_unless_non_null():
        test_case(GraphQLBoolean, "null", None)
        test_case(non_null_bool, "null", INVALID)

    def coerces_lists_of_values():
        test_case(list_of_bool, "true", [True])
        test_case(list_of_bool, "123", INVALID)
        test_case(list_of_bool, "null", None)
        test_case(list_of_bool, "[true, false]", [True, False])
        test_case(list_of_bool, "[true, 123]", INVALID)
        test_case(list_of_bool, "[true, null]", [True, None])
        test_case(list_of_bool, "{ true: true }", INVALID)

    def coerces_non_null_lists_of_values():
        test_case(non_null_list_of_bool, "true", [True])
        test_case(non_null_list_of_bool, "123", INVALID)
        test_case(non_null_list_of_bool, "null", INVALID)
        test_case(non_null_list_of_bool, "[true, false]", [True, False])
        test_case(non_null_list_of_bool, "[true, 123]", INVALID)
        test_case(non_null_list_of_bool, "[true, null]", [True, None])

    def coerces_lists_of_non_null_values():
        test_case(list_of_non_null_bool, "true", [True])
        test_case(list_of_non_null_bool, "123", INVALID)
        test_case(list_of_non_null_bool, "null", None)
        test_case(list_of_non_null_bool, "[true, false]", [True, False])
        test_case(list_of_non_null_bool, "[true, 123]", INVALID)
        test_case(list_of_non_null_bool, "[true, null]", INVALID)

    def coerces_non_null_lists_of_non_null_values():
        test_case(non_null_list_of_non_mull_bool, "true", [True])
        test_case(non_null_list_of_non_mull_bool, "123", INVALID)
        test_case(non_null_list_of_non_mull_bool, "null", INVALID)
        test_case(non_null_list_of_non_mull_bool, "[true, false]", [True, False])
        test_case(non_null_list_of_non_mull_bool, "[true, 123]", INVALID)
        test_case(non_null_list_of_non_mull_bool, "[true, null]", INVALID)

    test_input_obj = GraphQLInputObjectType(
        "TestInput",
        {
            "int": GraphQLInputField(GraphQLInt, default_value=42),
            "bool": GraphQLInputField(GraphQLBoolean),
            "requiredBool": GraphQLInputField(non_null_bool),
        },
    )

    def coerces_input_objects_according_to_input_coercion_rules():
        test_case(test_input_obj, "null", None)
        test_case(test_input_obj, "123", INVALID)
        test_case(test_input_obj, "[]", INVALID)
        test_case(
            test_input_obj,
            "{ int: 123, requiredBool: false }",
            {"int": 123, "requiredBool": False},
        )
        test_case(
            test_input_obj,
            "{ bool: true, requiredBool: false }",
            {"int": 42, "bool": True, "requiredBool": False},
        )
        test_case(test_input_obj, "{ int: true, requiredBool: true }", INVALID)
        test_case(test_input_obj, "{ requiredBool: null }", INVALID)
        test_case(test_input_obj, "{ bool: true }", INVALID)

    def accepts_variable_values_assuming_already_coerced():
        test_case_with_vars({}, GraphQLBoolean, "$var", INVALID)
        test_case_with_vars({"var": True}, GraphQLBoolean, "$var", True)
        test_case_with_vars({"var": None}, GraphQLBoolean, "$var", None)

    def asserts_variables_are_provided_as_items_in_lists():
        test_case_with_vars({}, list_of_bool, "[ $foo ]", [None])
        test_case_with_vars({}, list_of_non_null_bool, "[ $foo ]", INVALID)
        test_case_with_vars({"foo": True}, list_of_non_null_bool, "[ $foo ]", [True])
        # Note: variables are expected to have already been coerced, so we
        # do not expect the singleton wrapping behavior for variables.
        test_case_with_vars({"foo": True}, list_of_non_null_bool, "$foo", True)
        test_case_with_vars({"foo": [True]}, list_of_non_null_bool, "$foo", [True])

    def omits_input_object_fields_for_unprovided_variables():
        test_case_with_vars(
            {},
            test_input_obj,
            "{ int: $foo, bool: $foo, requiredBool: true }",
            {"int": 42, "requiredBool": True},
        )
        test_case_with_vars({}, test_input_obj, "{ requiredBool: $foo }", INVALID)
        test_case_with_vars(
            {"foo": True},
            test_input_obj,
            "{ requiredBool: $foo }",
            {"int": 42, "requiredBool": True},
        )
