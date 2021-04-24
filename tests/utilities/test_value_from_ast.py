from math import isnan, nan
from typing import Any, Dict, Optional

from graphql.language import parse_value, ValueNode
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
    GraphQLString,
)
from graphql.utilities import value_from_ast


def describe_value_from_ast():
    def _value_from(
        value_text: str,
        type_: GraphQLInputType,
        variables: Optional[Dict[str, Any]] = None,
    ):
        ast = parse_value(value_text)
        return value_from_ast(ast, type_, variables)

    def rejects_empty_input():
        # noinspection PyTypeChecker
        assert value_from_ast(None, GraphQLBoolean) is Undefined

    def converts_according_to_input_coercion_rules():
        assert _value_from("true", GraphQLBoolean) is True
        assert _value_from("false", GraphQLBoolean) is False
        assert _value_from("123", GraphQLInt) == 123
        assert _value_from("123", GraphQLFloat) == 123
        assert _value_from("123.456", GraphQLFloat) == 123.456
        assert _value_from('"abc123"', GraphQLString) == "abc123"
        assert _value_from("123456", GraphQLID) == "123456"
        assert _value_from('"123456"', GraphQLID) == "123456"

    def does_not_convert_when_input_coercion_rules_reject_a_value():
        assert _value_from("123", GraphQLBoolean) is Undefined
        assert _value_from("123.456", GraphQLInt) is Undefined
        assert _value_from("true", GraphQLInt) is Undefined
        assert _value_from('"123"', GraphQLInt) is Undefined
        assert _value_from('"123"', GraphQLFloat) is Undefined
        assert _value_from("123", GraphQLString) is Undefined
        assert _value_from("true", GraphQLString) is Undefined
        assert _value_from("123.456", GraphQLID) is Undefined

    def convert_using_parse_literal_from_a_custom_scalar_type():
        def pass_through_parse_literal(node, _vars=None):
            assert node.kind == "string_value"
            return node.value

        pass_through_scalar = GraphQLScalarType(
            "PassThroughScalar",
            parse_literal=pass_through_parse_literal,
            parse_value=lambda value: value,  # pragma: no cover
        )

        assert _value_from('"value"', pass_through_scalar) == "value"

        def throw_parse_literal(_node: ValueNode, _vars=None):
            raise RuntimeError("Test")

        throw_scalar = GraphQLScalarType(
            "ThrowScalar",
            parse_literal=throw_parse_literal,
            parse_value=lambda value: value,  # pragma: no cover
        )

        assert _value_from("value", throw_scalar) is Undefined

        def undefined_parse_literal(_node: ValueNode, _vars=None):
            return Undefined

        return_undefined_scalar = GraphQLScalarType(
            "ReturnUndefinedScalar",
            parse_literal=undefined_parse_literal,
            parse_value=lambda value: value,  # pragma: no cover
        )

        assert _value_from("value", return_undefined_scalar) is Undefined

    def converts_enum_values_according_to_input_coercion_rules():
        test_enum = GraphQLEnumType(
            "TestColor",
            {
                "RED": 1,
                "GREEN": 2,
                "BLUE": 3,
                "NULL": None,
                "NAN": nan,
                "NO_CUSTOM_VALUE": Undefined,
            },
        )

        assert _value_from("RED", test_enum) == 1
        assert _value_from("BLUE", test_enum) == 3
        assert _value_from("YELLOW", test_enum) is Undefined
        assert _value_from("3", test_enum) is Undefined
        assert _value_from('"BLUE"', test_enum) is Undefined
        assert _value_from("null", test_enum) is None
        assert _value_from("NULL", test_enum) is None
        assert _value_from("NULL", GraphQLNonNull(test_enum)) is None
        assert isnan(_value_from("NAN", test_enum))
        assert _value_from("NO_CUSTOM_VALUE", test_enum) is Undefined

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
        assert _value_from("null", GraphQLBoolean) is None
        assert _value_from("null", non_null_bool) is Undefined

    def coerces_lists_of_values():
        assert _value_from("true", list_of_bool) == [True]
        assert _value_from("123", list_of_bool) is Undefined
        assert _value_from("null", list_of_bool) is None
        assert _value_from("[true, false]", list_of_bool) == [True, False]
        assert _value_from("[true, 123]", list_of_bool) is Undefined
        assert _value_from("[true, null]", list_of_bool) == [True, None]
        assert _value_from("{ true: true }", list_of_bool) is Undefined

    def coerces_non_null_lists_of_values():
        assert _value_from("true", non_null_list_of_bool) == [True]
        assert _value_from("123", non_null_list_of_bool) is Undefined
        assert _value_from("null", non_null_list_of_bool) is Undefined
        assert _value_from("[true, false]", non_null_list_of_bool) == [True, False]
        assert _value_from("[true, 123]", non_null_list_of_bool) is Undefined
        assert _value_from("[true, null]", non_null_list_of_bool) == [True, None]

    def coerces_lists_of_non_null_values():
        assert _value_from("true", list_of_non_null_bool) == [True]
        assert _value_from("123", list_of_non_null_bool) is Undefined
        assert _value_from("null", list_of_non_null_bool) is None
        assert _value_from("[true, false]", list_of_non_null_bool) == [True, False]
        assert _value_from("[true, 123]", list_of_non_null_bool) is Undefined
        assert _value_from("[true, null]", list_of_non_null_bool) is Undefined

    def coerces_non_null_lists_of_non_null_values():
        assert _value_from("true", non_null_list_of_non_mull_bool) == [True]
        assert _value_from("123", non_null_list_of_non_mull_bool) is Undefined
        assert _value_from("null", non_null_list_of_non_mull_bool) is Undefined
        assert _value_from("[true, false]", non_null_list_of_non_mull_bool) == [
            True,
            False,
        ]
        assert _value_from("[true, 123]", non_null_list_of_non_mull_bool) is Undefined
        assert _value_from("[true, null]", non_null_list_of_non_mull_bool) is Undefined

    test_input_obj = GraphQLInputObjectType(
        "TestInput",
        {
            "int": GraphQLInputField(GraphQLInt, default_value=42),
            "bool": GraphQLInputField(GraphQLBoolean),
            "requiredBool": GraphQLInputField(non_null_bool),
        },
    )

    def coerces_input_objects_according_to_input_coercion_rules():
        assert _value_from("null", test_input_obj) is None
        assert _value_from("[]", test_input_obj) is Undefined
        assert _value_from("123", test_input_obj) is Undefined
        assert _value_from("{ int: 123, requiredBool: false }", test_input_obj) == {
            "int": 123,
            "requiredBool": False,
        }
        assert _value_from("{ bool: true, requiredBool: false }", test_input_obj) == {
            "int": 42,
            "bool": True,
            "requiredBool": False,
        }
        assert (
            _value_from("{ int: true, requiredBool: true }", test_input_obj)
            is Undefined
        )
        assert _value_from("{ requiredBool: null }", test_input_obj) is Undefined
        assert _value_from("{ bool: true }", test_input_obj) is Undefined

    def accepts_variable_values_assuming_already_coerced():
        assert _value_from("$var", GraphQLBoolean, {}) is Undefined
        assert _value_from("$var", GraphQLBoolean, {"var": True}) is True
        assert _value_from("$var", GraphQLBoolean, {"var": None}) is None
        assert _value_from("$var", non_null_bool, {"var": None}) is Undefined

    def asserts_variables_are_provided_as_items_in_lists():
        assert _value_from("[ $foo ]", list_of_bool, {}) == [None]
        assert _value_from("[ $foo ]", list_of_non_null_bool, {}) is Undefined
        assert _value_from("[ $foo ]", list_of_non_null_bool, {"foo": True}) == [True]
        # Note: variables are expected to have already been coerced, so we
        # do not expect the singleton wrapping behavior for variables.
        assert _value_from("$foo", list_of_non_null_bool, {"foo": True}) is True
        assert _value_from("$foo", list_of_non_null_bool, {"foo": [True]}) == [True]

    def omits_input_object_fields_for_unprovided_variables():
        assert _value_from(
            "{ int: $foo, bool: $foo, requiredBool: true }", test_input_obj, {}
        ) == {"int": 42, "requiredBool": True}
        assert _value_from("{ requiredBool: $foo }", test_input_obj, {}) is Undefined
        assert _value_from("{ requiredBool: $foo }", test_input_obj, {"foo": True}) == {
            "int": 42,
            "requiredBool": True,
        }

    def transforms_names_using_out_name():
        # This is an extension of GraphQL.js.
        complex_input_obj = GraphQLInputObjectType(
            "Complex",
            {
                "realPart": GraphQLInputField(GraphQLFloat, out_name="real_part"),
                "imagPart": GraphQLInputField(
                    GraphQLFloat, default_value=0, out_name="imag_part"
                ),
            },
        )
        assert _value_from("{ realPart: 1 }", complex_input_obj) == {
            "real_part": 1,
            "imag_part": 0,
        }

    def transforms_values_with_out_type():
        # This is an extension of GraphQL.js.
        complex_input_obj = GraphQLInputObjectType(
            "Complex",
            {
                "real": GraphQLInputField(GraphQLFloat),
                "imag": GraphQLInputField(GraphQLFloat),
            },
            out_type=lambda value: complex(value["real"], value["imag"]),
        )
        assert _value_from("{ real: 1, imag: 2 }", complex_input_obj) == 1 + 2j
