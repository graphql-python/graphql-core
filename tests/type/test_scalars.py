from math import inf, nan, pi

from pytest import raises  # type: ignore

from graphql.error import INVALID
from graphql.language import parse_value as parse_value_to_ast
from graphql.type import (
    GraphQLInt,
    GraphQLFloat,
    GraphQLString,
    GraphQLBoolean,
    GraphQLID,
)


def describe_type_system_specified_scalar_types():
    def describe_graphql_int():
        def parse_value():
            parse_value = GraphQLInt.parse_value

            assert parse_value(1) == 1
            assert parse_value(0) == 0
            assert parse_value(-1) == -1

            with raises(TypeError) as exc_info:
                parse_value(9876504321)
            assert (
                str(exc_info.value)
                == "Int cannot represent non 32-bit signed integer value: 9876504321"
            )
            with raises(TypeError) as exc_info:
                parse_value(-9876504321)
            assert (
                str(exc_info.value)
                == "Int cannot represent non 32-bit signed integer value: -9876504321"
            )
            with raises(TypeError) as exc_info:
                parse_value(0.1)
            assert str(exc_info.value) == "Int cannot represent non-integer value: 0.1"
            with raises(TypeError) as exc_info:
                parse_value(nan)
            assert str(exc_info.value) == "Int cannot represent non-integer value: nan"
            with raises(TypeError) as exc_info:
                parse_value(inf)
            assert str(exc_info.value) == "Int cannot represent non-integer value: inf"
            with raises(TypeError) as exc_info:
                parse_value(INVALID)
            assert (
                str(exc_info.value)
                == "Int cannot represent non-integer value: <INVALID>"
            )
            with raises(TypeError) as exc_info:
                parse_value(None)
            assert str(exc_info.value) == "Int cannot represent non-integer value: None"
            with raises(TypeError) as exc_info:
                parse_value("")
            assert str(exc_info.value) == "Int cannot represent non-integer value: ''"
            with raises(TypeError) as exc_info:
                parse_value("123")
            assert (
                str(exc_info.value) == "Int cannot represent non-integer value: '123'"
            )
            with raises(TypeError) as exc_info:
                parse_value(False)
            assert (
                str(exc_info.value) == "Int cannot represent non-integer value: False"
            )
            with raises(TypeError) as exc_info:
                parse_value(True)
            assert str(exc_info.value) == "Int cannot represent non-integer value: True"
            with raises(TypeError) as exc_info:
                parse_value([1])
            assert str(exc_info.value) == "Int cannot represent non-integer value: [1]"
            with raises(TypeError) as exc_info:
                parse_value({"value": 1})
            assert (
                str(exc_info.value)
                == "Int cannot represent non-integer value: {'value': 1}"
            )

        def parse_literal():
            def parse_literal(s):
                return GraphQLInt.parse_literal(parse_value_to_ast(s))

            assert parse_literal("1") == 1
            assert parse_literal("0") == 0
            assert parse_literal("-1") == -1

            assert parse_literal("9876504321") is INVALID
            assert parse_literal("-9876504321") is INVALID

            assert parse_literal("1.0") is INVALID
            assert parse_literal("null") is INVALID
            assert parse_literal("None") is INVALID
            assert parse_literal('""') is INVALID
            assert parse_literal('"123"') is INVALID
            assert parse_literal("false") is INVALID
            assert parse_literal("False") is INVALID
            assert parse_literal("[1]") is INVALID
            assert parse_literal("{value: 1}") is INVALID
            assert parse_literal("ENUM_VALUE") is INVALID
            assert parse_literal("$var") is INVALID

    def describe_graphql_float():
        def parse_value():
            parse_value = GraphQLFloat.parse_value

            assert parse_value(1) == 1
            assert parse_value(0) == 0
            assert parse_value(-1) == -1
            assert parse_value(0.1) == 0.1
            assert parse_value(pi) == pi

            with raises(TypeError) as exc_info:
                parse_value(nan)
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: nan"
            )
            with raises(TypeError) as exc_info:
                parse_value(inf)
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: inf"
            )
            with raises(TypeError) as exc_info:
                parse_value("")
            assert str(exc_info.value) == "Float cannot represent non numeric value: ''"
            with raises(TypeError) as exc_info:
                parse_value("123")
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: '123'"
            )
            with raises(TypeError) as exc_info:
                parse_value("123.5")
            assert (
                str(exc_info.value)
                == "Float cannot represent non numeric value: '123.5'"
            )
            with raises(TypeError) as exc_info:
                parse_value(False)
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: False"
            )
            with raises(TypeError) as exc_info:
                parse_value(True)
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: True"
            )
            with raises(TypeError) as exc_info:
                parse_value([0.1])
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: [0.1]"
            )
            with raises(TypeError) as exc_info:
                parse_value({"value": 0.1})
            assert (
                str(exc_info.value)
                == "Float cannot represent non numeric value: {'value': 0.1}"
            )

        def parse_literal():
            def parse_literal(s):
                return GraphQLFloat.parse_literal(parse_value_to_ast(s))

            assert parse_literal("1") == 1
            assert parse_literal("0") == 0
            assert parse_literal("-1") == -1
            assert parse_literal("0.1") == 0.1
            assert parse_literal(str(pi)) == pi

            assert parse_literal("null") is INVALID
            assert parse_literal("None") is INVALID
            assert parse_literal('""') is INVALID
            assert parse_literal('"123"') is INVALID
            assert parse_literal('"123.5"') is INVALID
            assert parse_literal("false") is INVALID
            assert parse_literal("False") is INVALID
            assert parse_literal("[0.1]") is INVALID
            assert parse_literal("{value: 0.1}") is INVALID
            assert parse_literal("ENUM_VALUE") is INVALID
            assert parse_literal("$var") is INVALID

    def describe_graphql_string():
        def parse_value():
            parse_value = GraphQLString.parse_value

            assert parse_value("foo") == "foo"

            with raises(TypeError) as exc_info:
                parse_value(INVALID)
            assert (
                str(exc_info.value)
                == "String cannot represent a non string value: <INVALID>"
            )
            with raises(TypeError) as exc_info:
                parse_value(None)
            assert (
                str(exc_info.value)
                == "String cannot represent a non string value: None"
            )
            with raises(TypeError) as exc_info:
                parse_value(1)
            assert (
                str(exc_info.value) == "String cannot represent a non string value: 1"
            )
            with raises(TypeError) as exc_info:
                parse_value(nan)
            assert (
                str(exc_info.value) == "String cannot represent a non string value: nan"
            )
            with raises(TypeError) as exc_info:
                parse_value(False)
            assert (
                str(exc_info.value)
                == "String cannot represent a non string value: False"
            )
            with raises(TypeError) as exc_info:
                parse_value(["foo"])
            assert (
                str(exc_info.value)
                == "String cannot represent a non string value: ['foo']"
            )
            with raises(TypeError) as exc_info:
                parse_value({"value": "foo"})
            assert (
                str(exc_info.value)
                == "String cannot represent a non string value: {'value': 'foo'}"
            )

        def parse_literal():
            def parse_literal(s):
                return GraphQLString.parse_literal(parse_value_to_ast(s))

            assert parse_literal('"foo"') == "foo"
            assert parse_literal('"""bar"""') == "bar"

            assert parse_literal("null") == INVALID
            assert parse_literal("None") == INVALID
            assert parse_literal("1") == INVALID
            assert parse_literal("0.1") == INVALID
            assert parse_literal("false") == INVALID
            assert parse_literal("False") == INVALID
            assert parse_literal('["foo"]') == INVALID
            assert parse_literal('{value: "foo"}') == INVALID
            assert parse_literal("ENUM_VALUE") == INVALID
            assert parse_literal("$var") == INVALID

    def describe_graphql_boolean():
        def parse_value():
            parse_value = GraphQLBoolean.parse_value

            assert parse_value(True) is True
            assert parse_value(False) is False

            with raises(TypeError) as exc_info:
                parse_value(INVALID)
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: <INVALID>"
            )
            with raises(TypeError) as exc_info:
                parse_value(None)
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: None"
            )
            with raises(TypeError) as exc_info:
                parse_value(0)
            assert (
                str(exc_info.value) == "Boolean cannot represent a non boolean value: 0"
            )
            with raises(TypeError) as exc_info:
                parse_value(1)
            assert (
                str(exc_info.value) == "Boolean cannot represent a non boolean value: 1"
            )
            with raises(TypeError) as exc_info:
                parse_value(nan)
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: nan"
            )
            with raises(TypeError) as exc_info:
                parse_value("")
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: ''"
            )
            with raises(TypeError) as exc_info:
                parse_value("false")
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: 'false'"
            )
            with raises(TypeError) as exc_info:
                parse_value("False")
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: 'False'"
            )
            with raises(TypeError) as exc_info:
                parse_value([False])
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: [False]"
            )
            with raises(TypeError) as exc_info:
                parse_value({"value": False})
            assert (
                str(exc_info.value)
                == "Boolean cannot represent a non boolean value: {'value': False}"
            )

        def parse_literal():
            def parse_literal(s):
                return GraphQLBoolean.parse_literal(parse_value_to_ast(s))

            assert parse_literal("true") is True
            assert parse_literal("false") is False

            assert parse_literal("True") is INVALID
            assert parse_literal("False") is INVALID
            assert parse_literal("null") is INVALID
            assert parse_literal("None") is INVALID
            assert parse_literal("0") is INVALID
            assert parse_literal("1") is INVALID
            assert parse_literal("0.1") is INVALID
            assert parse_literal('""') is INVALID
            assert parse_literal('"false"') is INVALID
            assert parse_literal('"False"') is INVALID
            assert parse_literal("[false]") is INVALID
            assert parse_literal("[False]") is INVALID
            assert parse_literal("{value: false}") is INVALID
            assert parse_literal("{value: False}") is INVALID
            assert parse_literal("ENUM_VALUE") is INVALID
            assert parse_literal("$var") is INVALID

    def describe_graphql_id():
        def parse_value():
            parse_value = GraphQLID.parse_value

            assert parse_value("") == ""
            assert parse_value("1") == "1"
            assert parse_value("foo") == "foo"
            assert parse_value(1) == "1"
            assert parse_value(0) == "0"
            assert parse_value(-1) == "-1"

            # Maximum and minimum safe numbers in JS
            assert parse_value(9007199254740991) == "9007199254740991"
            assert parse_value(-9007199254740991) == "-9007199254740991"

            with raises(TypeError) as exc_info:
                parse_value(INVALID)
            assert str(exc_info.value) == "ID cannot represent value: <INVALID>"
            with raises(TypeError) as exc_info:
                parse_value(None)
            assert str(exc_info.value) == "ID cannot represent value: None"
            with raises(TypeError) as exc_info:
                parse_value(0.1)
            assert str(exc_info.value) == "ID cannot represent value: 0.1"
            with raises(TypeError) as exc_info:
                parse_value(nan)
            assert str(exc_info.value) == "ID cannot represent value: nan"
            with raises(TypeError) as exc_info:
                parse_value(inf)
            assert str(exc_info.value) == "ID cannot represent value: inf"
            with raises(TypeError) as exc_info:
                parse_value(False)
            assert str(exc_info.value) == "ID cannot represent value: False"
            with raises(TypeError) as exc_info:
                parse_value(["1"])
            assert str(exc_info.value) == "ID cannot represent value: ['1']"
            with raises(TypeError) as exc_info:
                parse_value({"value": "1"})
            assert str(exc_info.value) == "ID cannot represent value: {'value': '1'}"

        def parse_literal():
            def parse_literal(s):
                return GraphQLID.parse_literal(parse_value_to_ast(s))

            assert parse_literal('""') == ""
            assert parse_literal('"1"') == "1"
            assert parse_literal('"foo"') == "foo"
            assert parse_literal('"""foo"""') == "foo"
            assert parse_literal("1") == "1"
            assert parse_literal("0") == "0"
            assert parse_literal("-1") == "-1"

            # Support arbitrary long numbers even if they can't be represented in JS
            assert parse_literal("90071992547409910") == "90071992547409910"
            assert parse_literal("-90071992547409910") == "-90071992547409910"

            assert parse_literal("null") is INVALID
            assert parse_literal("None") is INVALID
            assert parse_literal("0.1") is INVALID
            assert parse_literal("false") is INVALID
            assert parse_literal("False") is INVALID
            assert parse_literal('["1"]') is INVALID
            assert parse_literal('{value: "1"}') is INVALID
            assert parse_literal("ENUM_VALUE") is INVALID
            assert parse_literal("$var") is INVALID
