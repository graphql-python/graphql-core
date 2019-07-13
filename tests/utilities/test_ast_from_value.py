from math import nan

from pytest import raises  # type: ignore

from graphql.error import INVALID
from graphql.language import (
    BooleanValueNode,
    EnumValueNode,
    FloatValueNode,
    IntValueNode,
    ListValueNode,
    NameNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    StringValueNode,
)
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
from graphql.utilities import ast_from_value


def describe_ast_from_value():
    def converts_boolean_values_to_asts():
        assert ast_from_value(True, GraphQLBoolean) == BooleanValueNode(value=True)

        assert ast_from_value(False, GraphQLBoolean) == BooleanValueNode(value=False)

        assert ast_from_value(INVALID, GraphQLBoolean) is None

        assert ast_from_value(nan, GraphQLInt) is None

        assert ast_from_value(None, GraphQLBoolean) == NullValueNode()

        assert ast_from_value(0, GraphQLBoolean) == BooleanValueNode(value=False)

        assert ast_from_value(1, GraphQLBoolean) == BooleanValueNode(value=True)

        non_null_boolean = GraphQLNonNull(GraphQLBoolean)
        assert ast_from_value(0, non_null_boolean) == BooleanValueNode(value=False)

    def converts_int_values_to_int_asts():
        assert ast_from_value(-1, GraphQLInt) == IntValueNode(value="-1")

        assert ast_from_value(123.0, GraphQLInt) == IntValueNode(value="123")

        assert ast_from_value(1e4, GraphQLInt) == IntValueNode(value="10000")

        # GraphQL spec does not allow coercing non-integer values to Int to
        # avoid accidental data loss.
        with raises(TypeError) as exc_info:
            assert ast_from_value(123.5, GraphQLInt)
        msg = str(exc_info.value)
        assert msg == "Int cannot represent non-integer value: 123.5"

        # Note: outside the bounds of 32bit signed int.
        with raises(TypeError) as exc_info:
            assert ast_from_value(1e40, GraphQLInt)
        msg = str(exc_info.value)
        assert msg == "Int cannot represent non 32-bit signed integer value: 1e+40"

    def converts_float_values_to_float_asts():
        # luckily in Python we can discern between float and int
        assert ast_from_value(-1, GraphQLFloat) == FloatValueNode(value="-1")

        assert ast_from_value(123.0, GraphQLFloat) == FloatValueNode(value="123")

        assert ast_from_value(123.5, GraphQLFloat) == FloatValueNode(value="123.5")

        assert ast_from_value(1e4, GraphQLFloat) == FloatValueNode(value="10000")

        assert ast_from_value(1e40, GraphQLFloat) == FloatValueNode(value="1e+40")

    def converts_string_values_to_string_asts():
        assert ast_from_value("hello", GraphQLString) == StringValueNode(value="hello")

        assert ast_from_value("VALUE", GraphQLString) == StringValueNode(value="VALUE")

        assert ast_from_value("VA\nLUE", GraphQLString) == StringValueNode(
            value="VA\nLUE"
        )

        assert ast_from_value(123, GraphQLString) == StringValueNode(value="123")

        assert ast_from_value(False, GraphQLString) == StringValueNode(value="false")

        assert ast_from_value(None, GraphQLString) == NullValueNode()

        assert ast_from_value(INVALID, GraphQLString) is None

    def converts_id_values_to_int_or_string_asts():
        assert ast_from_value("hello", GraphQLID) == StringValueNode(value="hello")

        assert ast_from_value("VALUE", GraphQLID) == StringValueNode(value="VALUE")

        # Note: EnumValues cannot contain non-identifier characters
        assert ast_from_value("VA\nLUE", GraphQLID) == StringValueNode(value="VA\nLUE")

        # Note: IntValues are used when possible.
        assert ast_from_value(-1, GraphQLID) == IntValueNode(value="-1")

        assert ast_from_value(123, GraphQLID) == IntValueNode(value="123")

        assert ast_from_value("123", GraphQLID) == IntValueNode(value="123")

        assert ast_from_value("01", GraphQLID) == StringValueNode(value="01")

        with raises(TypeError) as exc_info:
            assert ast_from_value(False, GraphQLID)
        assert str(exc_info.value) == "ID cannot represent value: False"

        assert ast_from_value(None, GraphQLID) == NullValueNode()

        assert ast_from_value(INVALID, GraphQLString) is None

    def does_not_convert_non_null_values_to_null_value():
        non_null_boolean = GraphQLNonNull(GraphQLBoolean)
        assert ast_from_value(None, non_null_boolean) is None

    complex_value = {"someArbitrary": "complexValue"}

    my_enum = GraphQLEnumType(
        "MyEnum", {"HELLO": None, "GOODBYE": None, "COMPLEX": complex_value}
    )

    def converts_string_values_to_enum_asts_if_possible():
        assert ast_from_value("HELLO", my_enum) == EnumValueNode(value="HELLO")

        assert ast_from_value(complex_value, my_enum) == EnumValueNode(value="COMPLEX")

        # Note: case sensitive
        assert ast_from_value("hello", my_enum) is None

        # Note: not a valid enum value
        assert ast_from_value("VALUE", my_enum) is None

    def converts_list_values_to_list_asts():
        assert ast_from_value(
            ["FOO", "BAR"], GraphQLList(GraphQLString)
        ) == ListValueNode(
            values=[StringValueNode(value="FOO"), StringValueNode(value="BAR")]
        )

        assert ast_from_value(
            ["HELLO", "GOODBYE"], GraphQLList(my_enum)
        ) == ListValueNode(
            values=[EnumValueNode(value="HELLO"), EnumValueNode(value="GOODBYE")]
        )

    def converts_list_singletons():
        assert ast_from_value("FOO", GraphQLList(GraphQLString)) == StringValueNode(
            value="FOO"
        )

    def converts_input_objects():
        input_obj = GraphQLInputObjectType(
            "MyInputObj",
            {"foo": GraphQLInputField(GraphQLFloat), "bar": GraphQLInputField(my_enum)},
        )

        assert ast_from_value({"foo": 3, "bar": "HELLO"}, input_obj) == ObjectValueNode(
            fields=[
                ObjectFieldNode(
                    name=NameNode(value="foo"), value=FloatValueNode(value="3")
                ),
                ObjectFieldNode(
                    name=NameNode(value="bar"), value=EnumValueNode(value="HELLO")
                ),
            ]
        )

    def converts_input_objects_with_explicit_nulls():
        input_obj = GraphQLInputObjectType(
            "MyInputObj",
            {"foo": GraphQLInputField(GraphQLFloat), "bar": GraphQLInputField(my_enum)},
        )

        assert ast_from_value({"foo": None}, input_obj) == ObjectValueNode(
            fields=[ObjectFieldNode(name=NameNode(value="foo"), value=NullValueNode())]
        )
