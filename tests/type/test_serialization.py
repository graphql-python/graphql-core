from math import inf, nan

from pytest import raises  # type: ignore

from graphql.error import GraphQLError
from graphql.type import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLString,
)


def describe_type_system_scalar_coercion():
    def serializes_output_as_int():
        assert GraphQLInt.serialize(1) == 1
        assert GraphQLInt.serialize("123") == 123
        assert GraphQLInt.serialize(0) == 0
        assert GraphQLInt.serialize(-1) == -1
        assert GraphQLInt.serialize(1e5) == 100000
        assert GraphQLInt.serialize(False) == 0
        assert GraphQLInt.serialize(True) == 1
        assert GraphQLInt.serialize(type("Int", (int,), {})(5)) == 5

        # The GraphQL specification does not allow serializing non-integer
        # values as Int to avoid accidental data loss.
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(0.1)
        assert str(exc_info.value) == "Int cannot represent non-integer value: 0.1"
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(1.1)
        assert str(exc_info.value) == "Int cannot represent non-integer value: 1.1"
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(-1.1)
        assert str(exc_info.value) == "Int cannot represent non-integer value: -1.1"
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize("-1.1")
        assert str(exc_info.value) == "Int cannot represent non-integer value: '-1.1'"
        # Maybe a safe JavaScript int, but bigger than 2^32, so not
        # representable as a GraphQL Int
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(9876504321)
        assert str(exc_info.value) == (
            "Int cannot represent non 32-bit signed integer value: 9876504321"
        )
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(-9876504321)
        assert str(exc_info.value) == (
            "Int cannot represent non 32-bit signed integer value: -9876504321"
        )
        # Too big to represent as an Int in JavaScript or GraphQL
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(1e100)
        assert str(exc_info.value) == (
            "Int cannot represent non 32-bit signed integer value: 1e+100"
        )
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(-1e100)
        assert str(exc_info.value) == (
            "Int cannot represent non 32-bit signed integer value: -1e+100"
        )
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize("one")
        assert str(exc_info.value) == "Int cannot represent non-integer value: 'one'"
        # Doesn't represent number
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize("")
        assert str(exc_info.value) == "Int cannot represent non-integer value: ''"
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(nan)
        assert str(exc_info.value) == "Int cannot represent non-integer value: nan"
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize(inf)
        assert str(exc_info.value) == "Int cannot represent non-integer value: inf"
        with raises(GraphQLError) as exc_info:
            GraphQLInt.serialize([5])
        assert str(exc_info.value) == "Int cannot represent non-integer value: [5]"

    def serializes_output_as_float():
        assert GraphQLFloat.serialize(1) == 1.0
        assert GraphQLFloat.serialize(0) == 0.0
        assert GraphQLFloat.serialize("123.5") == 123.5
        assert GraphQLFloat.serialize(-1) == -1.0
        assert GraphQLFloat.serialize(0.1) == 0.1
        assert GraphQLFloat.serialize(1.1) == 1.1
        assert GraphQLFloat.serialize(-1.1) == -1.1
        assert GraphQLFloat.serialize("-1.1") == -1.1
        assert GraphQLFloat.serialize(False) == 0
        assert GraphQLFloat.serialize(True) == 1
        assert GraphQLFloat.serialize(type("Float", (float,), {})(5.5)) == 5.5

        with raises(GraphQLError) as exc_info:
            GraphQLFloat.serialize(nan)
        assert str(exc_info.value) == "Float cannot represent non numeric value: nan"
        with raises(GraphQLError) as exc_info:
            GraphQLFloat.serialize(inf)
        assert str(exc_info.value) == "Float cannot represent non numeric value: inf"
        with raises(GraphQLError) as exc_info:
            GraphQLFloat.serialize("one")
        assert str(exc_info.value) == (
            "Float cannot represent non numeric value: 'one'"
        )
        with raises(GraphQLError) as exc_info:
            GraphQLFloat.serialize("")
        assert str(exc_info.value) == "Float cannot represent non numeric value: ''"
        with raises(GraphQLError) as exc_info:
            GraphQLFloat.serialize([5])
        assert str(exc_info.value) == "Float cannot represent non numeric value: [5]"

    def serializes_output_as_string():
        assert GraphQLString.serialize("string") == "string"
        assert GraphQLString.serialize(1) == "1"
        assert GraphQLString.serialize(-1.1) == "-1.1"
        assert GraphQLString.serialize(True) == "true"
        assert GraphQLString.serialize(False) == "false"

        class StringableObjValue:
            def __str__(self):
                return "something useful"

        assert GraphQLString.serialize(StringableObjValue()) == "something useful"

        with raises(GraphQLError) as exc_info:
            GraphQLString.serialize(nan)
        assert str(exc_info.value) == "String cannot represent value: nan"

        with raises(GraphQLError) as exc_info:
            GraphQLString.serialize([1])
        assert str(exc_info.value) == "String cannot represent value: [1]"

        with raises(GraphQLError) as exc_info:
            GraphQLString.serialize({})
        assert str(exc_info.value) == "String cannot represent value: {}"

        with raises(GraphQLError) as exc_info:
            GraphQLString.serialize({"value_of": "value_of string"})
        assert (
            str(exc_info.value) == "String cannot represent value:"
            " {'value_of': 'value_of string'}"
        )

    def serializes_output_as_boolean():
        assert GraphQLBoolean.serialize(1) is True
        assert GraphQLBoolean.serialize(0) is False
        assert GraphQLBoolean.serialize(True) is True
        assert GraphQLBoolean.serialize(False) is False
        with raises(TypeError, match="not an acceptable base type"):
            # you can't subclass bool in Python
            assert GraphQLBoolean.serialize(type("Boolean", (bool,), {})(True)) is True

        with raises(GraphQLError) as exc_info:
            GraphQLBoolean.serialize(nan)
        assert str(exc_info.value) == (
            "Boolean cannot represent a non boolean value: nan"
        )

        with raises(GraphQLError) as exc_info:
            GraphQLBoolean.serialize("")
        assert str(exc_info.value) == (
            "Boolean cannot represent a non boolean value: ''"
        )

        with raises(GraphQLError) as exc_info:
            GraphQLBoolean.serialize("True")
        assert str(exc_info.value) == (
            "Boolean cannot represent a non boolean value: 'True'"
        )

        with raises(GraphQLError) as exc_info:
            GraphQLBoolean.serialize([False])
        assert str(exc_info.value) == (
            "Boolean cannot represent a non boolean value: [False]"
        )

        with raises(GraphQLError) as exc_info:
            GraphQLBoolean.serialize({})
        assert str(exc_info.value) == (
            "Boolean cannot represent a non boolean value: {}"
        )

    def serializes_output_as_id():
        assert GraphQLID.serialize("string") == "string"
        assert GraphQLID.serialize("false") == "false"
        assert GraphQLID.serialize("") == ""
        assert GraphQLID.serialize(123) == "123"
        assert GraphQLID.serialize(0) == "0"
        assert GraphQLID.serialize(-1) == "-1"

        class ObjValue:
            def __init__(self, value):
                self._id = value

            def __str__(self):
                return str(self._id)

        obj_value = ObjValue(123)
        assert GraphQLID.serialize(obj_value) == "123"

        with raises(GraphQLError) as exc_info:
            GraphQLID.serialize(True)
        assert str(exc_info.value) == "ID cannot represent value: True"

        with raises(GraphQLError) as exc_info:
            GraphQLID.serialize(3.14)
        assert str(exc_info.value) == "ID cannot represent value: 3.14"

        with raises(GraphQLError) as exc_info:
            GraphQLID.serialize({})
        assert str(exc_info.value) == "ID cannot represent value: {}"

        with raises(GraphQLError) as exc_info:
            GraphQLID.serialize(["abc"])
        assert str(exc_info.value) == "ID cannot represent value: ['abc']"
