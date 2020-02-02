from math import inf, nan, pi

from pytest import raises  # type: ignore

from graphql.error import GraphQLError
from graphql.language import parse_value as parse_value_to_ast
from graphql.pyutils import Undefined
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
            _parse_value = GraphQLInt.parse_value

            def _parse_value_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_value(s)
                assert str(exc_info.value) == message

            assert _parse_value(1) == 1
            assert _parse_value(0) == 0
            assert _parse_value(-1) == -1

            _parse_value_raises(
                9876504321,
                "Int cannot represent non 32-bit signed integer value: 9876504321",
            )
            _parse_value_raises(
                -9876504321,
                "Int cannot represent non 32-bit signed integer value: -9876504321",
            )
            _parse_value_raises(0.1, "Int cannot represent non-integer value: 0.1")
            _parse_value_raises(nan, "Int cannot represent non-integer value: nan")
            _parse_value_raises(inf, "Int cannot represent non-integer value: inf")
            _parse_value_raises(
                Undefined, "Int cannot represent non-integer value: Undefined"
            )
            _parse_value_raises(None, "Int cannot represent non-integer value: None")
            _parse_value_raises("", "Int cannot represent non-integer value: ''")
            _parse_value_raises("123", "Int cannot represent non-integer value: '123'")
            _parse_value_raises(False, "Int cannot represent non-integer value: False")
            _parse_value_raises(True, "Int cannot represent non-integer value: True")
            _parse_value_raises([1], "Int cannot represent non-integer value: [1]")
            _parse_value_raises(
                {"value": 1}, "Int cannot represent non-integer value: {'value': 1}"
            )

        def parse_literal():
            def _parse_literal(s):
                return GraphQLInt.parse_literal(parse_value_to_ast(s))

            def _parse_literal_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_literal(s)
                assert str(exc_info.value).startswith(message + "\n")

            assert _parse_literal("1") == 1
            assert _parse_literal("0") == 0
            assert _parse_literal("-1") == -1

            _parse_literal_raises(
                "9876504321",
                "Int cannot represent non 32-bit signed integer value: 9876504321",
            )
            _parse_literal_raises(
                "-9876504321",
                "Int cannot represent non 32-bit signed integer value: -9876504321",
            )
            _parse_literal_raises("1.0", "Int cannot represent non-integer value: 1.0")
            _parse_literal_raises(
                "null", "Int cannot represent non-integer value: null"
            )
            _parse_literal_raises(
                "None", "Int cannot represent non-integer value: None"
            )
            _parse_literal_raises('""', 'Int cannot represent non-integer value: ""')
            _parse_literal_raises(
                '"123"', 'Int cannot represent non-integer value: "123"'
            )
            _parse_literal_raises(
                "false", "Int cannot represent non-integer value: false"
            )
            _parse_literal_raises(
                "False", "Int cannot represent non-integer value: False"
            )
            _parse_literal_raises("[1]", "Int cannot represent non-integer value: [1]")
            _parse_literal_raises(
                "{value: 1}", "Int cannot represent non-integer value: {value: 1}"
            )
            _parse_literal_raises(
                "ENUM_VALUE", "Int cannot represent non-integer value: ENUM_VALUE"
            )
            _parse_literal_raises(
                "$var", "Int cannot represent non-integer value: $var"
            )

    def describe_graphql_float():
        def parse_value():
            _parse_value = GraphQLFloat.parse_value

            def _parse_value_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_value(s)
                assert str(exc_info.value) == message

            assert _parse_value(1) == 1
            assert _parse_value(0) == 0
            assert _parse_value(-1) == -1
            assert _parse_value(0.1) == 0.1
            assert _parse_value(pi) == pi

            _parse_value_raises(nan, "Float cannot represent non numeric value: nan")
            _parse_value_raises(inf, "Float cannot represent non numeric value: inf")
            _parse_value_raises("", "Float cannot represent non numeric value: ''")
            _parse_value_raises(
                "123", "Float cannot represent non numeric value: '123'"
            )
            _parse_value_raises(
                "123.5", "Float cannot represent non numeric value: '123.5'"
            )
            _parse_value_raises(
                False, "Float cannot represent non numeric value: False"
            )
            _parse_value_raises(True, "Float cannot represent non numeric value: True")
            _parse_value_raises(
                [0.1], "Float cannot represent non numeric value: [0.1]"
            )
            _parse_value_raises(
                {"value": 0.1},
                "Float cannot represent non numeric value: {'value': 0.1}",
            )

        def parse_literal():
            def _parse_literal(s):
                return GraphQLFloat.parse_literal(parse_value_to_ast(s))

            def _parse_literal_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_literal(s)
                assert str(exc_info.value).startswith(message + "\n")

            assert _parse_literal("1") == 1
            assert _parse_literal("0") == 0
            assert _parse_literal("-1") == -1
            assert _parse_literal("0.1") == 0.1
            assert _parse_literal(str(pi)) == pi

            _parse_literal_raises(
                "null", "Float cannot represent non numeric value: null"
            )
            _parse_literal_raises(
                "None", "Float cannot represent non numeric value: None"
            )
            _parse_literal_raises('""', 'Float cannot represent non numeric value: ""')
            _parse_literal_raises(
                '"123"', 'Float cannot represent non numeric value: "123"'
            )
            _parse_literal_raises(
                '"123.5"', 'Float cannot represent non numeric value: "123.5"'
            )
            _parse_literal_raises(
                "false", "Float cannot represent non numeric value: false"
            )
            _parse_literal_raises(
                "False", "Float cannot represent non numeric value: False"
            )
            _parse_literal_raises(
                "[0.1]", "Float cannot represent non numeric value: [0.1]"
            )
            _parse_literal_raises(
                "{value: 0.1}", "Float cannot represent non numeric value: {value: 0.1}"
            )
            _parse_literal_raises(
                "ENUM_VALUE", "Float cannot represent non numeric value: ENUM_VALUE"
            )
            _parse_literal_raises(
                "$var", "Float cannot represent non numeric value: $var"
            )

    def describe_graphql_string():
        def parse_value():
            _parse_value = GraphQLString.parse_value

            def _parse_value_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_value(s)
                assert str(exc_info.value) == message

            assert _parse_value("foo") == "foo"

            _parse_value_raises(
                Undefined, "String cannot represent a non string value: Undefined"
            )
            _parse_value_raises(
                None, "String cannot represent a non string value: None"
            )
            _parse_value_raises(1, "String cannot represent a non string value: 1")
            _parse_value_raises(nan, "String cannot represent a non string value: nan")
            _parse_value_raises(
                False, "String cannot represent a non string value: False"
            )
            _parse_value_raises(
                ["foo"], "String cannot represent a non string value: ['foo']"
            )
            _parse_value_raises(
                {"value": "foo"},
                "String cannot represent a non string value: {'value': 'foo'}",
            )

        def parse_literal():
            def _parse_literal(s):
                return GraphQLString.parse_literal(parse_value_to_ast(s))

            def _parse_literal_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_literal(s)
                assert str(exc_info.value).startswith(message + "\n")

            assert _parse_literal('"foo"') == "foo"
            assert _parse_literal('"""bar"""') == "bar"

            _parse_literal_raises(
                "null", "String cannot represent a non string value: null"
            )
            _parse_literal_raises(
                "None", "String cannot represent a non string value: None"
            )
            _parse_literal_raises("1", "String cannot represent a non string value: 1")
            _parse_literal_raises(
                "0.1", "String cannot represent a non string value: 0.1"
            )
            _parse_literal_raises(
                "false", "String cannot represent a non string value: false"
            )
            _parse_literal_raises(
                "False", "String cannot represent a non string value: False"
            )
            _parse_literal_raises(
                '["foo"]', 'String cannot represent a non string value: ["foo"]'
            )
            _parse_literal_raises(
                '{value: "foo"}',
                'String cannot represent a non string value: {value: "foo"}',
            )
            _parse_literal_raises(
                "ENUM_VALUE", "String cannot represent a non string value: ENUM_VALUE"
            )
            _parse_literal_raises(
                "$var", "String cannot represent a non string value: $var"
            )

    def describe_graphql_boolean():
        def parse_value():
            _parse_value = GraphQLBoolean.parse_value

            def _parse_value_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_value(s)
                assert str(exc_info.value) == message

            assert _parse_value(True) is True
            assert _parse_value(False) is False

            _parse_value_raises(
                Undefined, "Boolean cannot represent a non boolean value: Undefined"
            )
            _parse_value_raises(
                None, "Boolean cannot represent a non boolean value: None"
            )
            _parse_value_raises(0, "Boolean cannot represent a non boolean value: 0")
            _parse_value_raises(1, "Boolean cannot represent a non boolean value: 1")
            _parse_value_raises(
                nan, "Boolean cannot represent a non boolean value: nan"
            )
            _parse_value_raises("", "Boolean cannot represent a non boolean value: ''")
            _parse_value_raises(
                "false", "Boolean cannot represent a non boolean value: 'false'"
            )
            _parse_value_raises(
                "False", "Boolean cannot represent a non boolean value: 'False'"
            )
            _parse_value_raises(
                [False], "Boolean cannot represent a non boolean value: [False]"
            )
            _parse_value_raises(
                {"value": False},
                "Boolean cannot represent a non boolean value: {'value': False}",
            )

        def parse_literal():
            def _parse_literal(s):
                return GraphQLBoolean.parse_literal(parse_value_to_ast(s))

            def _parse_literal_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_literal(s)
                assert str(exc_info.value).startswith(message + "\n")

            assert _parse_literal("true") is True
            assert _parse_literal("false") is False

            _parse_literal_raises(
                "True", "Boolean cannot represent a non boolean value: True"
            )
            _parse_literal_raises(
                "False", "Boolean cannot represent a non boolean value: False"
            )
            _parse_literal_raises(
                "null", "Boolean cannot represent a non boolean value: null"
            )
            _parse_literal_raises(
                "None", "Boolean cannot represent a non boolean value: None"
            )
            _parse_literal_raises(
                "0", "Boolean cannot represent a non boolean value: 0"
            )
            _parse_literal_raises(
                "1", "Boolean cannot represent a non boolean value: 1"
            )
            _parse_literal_raises(
                "0.1", "Boolean cannot represent a non boolean value: 0.1"
            )
            _parse_literal_raises(
                '""', 'Boolean cannot represent a non boolean value: ""'
            )
            _parse_literal_raises(
                '"false"', 'Boolean cannot represent a non boolean value: "false"'
            )
            _parse_literal_raises(
                '"False"', 'Boolean cannot represent a non boolean value: "False"'
            )
            _parse_literal_raises(
                "[false]", "Boolean cannot represent a non boolean value: [false]"
            )
            _parse_literal_raises(
                "[False]", "Boolean cannot represent a non boolean value: [False]"
            )
            _parse_literal_raises(
                "{value: false}",
                "Boolean cannot represent a non boolean value: {value: false}",
            )
            _parse_literal_raises(
                "{value: False}",
                "Boolean cannot represent a non boolean value: {value: False}",
            )
            _parse_literal_raises(
                "ENUM_VALUE", "Boolean cannot represent a non boolean value: ENUM_VALUE"
            )
            _parse_literal_raises(
                "$var", "Boolean cannot represent a non boolean value: $var"
            )

    def describe_graphql_id():
        def parse_value():
            _parse_value = GraphQLID.parse_value

            def _parse_value_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_value(s)
                assert str(exc_info.value) == message

            assert _parse_value("") == ""
            assert _parse_value("1") == "1"
            assert _parse_value("foo") == "foo"
            assert _parse_value(1) == "1"
            assert _parse_value(0) == "0"
            assert _parse_value(-1) == "-1"

            # Maximum and minimum safe numbers in JS
            assert _parse_value(9007199254740991) == "9007199254740991"
            assert _parse_value(-9007199254740991) == "-9007199254740991"

            _parse_value_raises(Undefined, "ID cannot represent value: Undefined")
            _parse_value_raises(None, "ID cannot represent value: None")
            _parse_value_raises(0.1, "ID cannot represent value: 0.1")
            _parse_value_raises(nan, "ID cannot represent value: nan")
            _parse_value_raises(inf, "ID cannot represent value: inf")
            _parse_value_raises(False, "ID cannot represent value: False")
            _parse_value_raises(["1"], "ID cannot represent value: ['1']")
            _parse_value_raises(
                {"value": "1"}, "ID cannot represent value: {'value': '1'}"
            )

        def parse_literal():
            def _parse_literal(s):
                return GraphQLID.parse_literal(parse_value_to_ast(s))

            def _parse_literal_raises(s, message):
                with raises(GraphQLError) as exc_info:
                    _parse_literal(s)
                assert str(exc_info.value).startswith(message + "\n")

            assert _parse_literal('""') == ""
            assert _parse_literal('"1"') == "1"
            assert _parse_literal('"foo"') == "foo"
            assert _parse_literal('"""foo"""') == "foo"
            assert _parse_literal("1") == "1"
            assert _parse_literal("0") == "0"
            assert _parse_literal("-1") == "-1"

            # Support arbitrary long numbers even if they can't be represented in JS
            assert _parse_literal("90071992547409910") == "90071992547409910"
            assert _parse_literal("-90071992547409910") == "-90071992547409910"

            _parse_literal_raises(
                "null", "ID cannot represent a non-string and non-integer value: null"
            )
            _parse_literal_raises(
                "None", "ID cannot represent a non-string and non-integer value: None"
            )
            _parse_literal_raises(
                "0.1", "ID cannot represent a non-string and non-integer value: 0.1"
            )
            _parse_literal_raises(
                "false", "ID cannot represent a non-string and non-integer value: false"
            )
            _parse_literal_raises(
                "False", "ID cannot represent a non-string and non-integer value: False"
            )
            _parse_literal_raises(
                '["1"]', 'ID cannot represent a non-string and non-integer value: ["1"]'
            )
            _parse_literal_raises(
                '{value: "1"}',
                "ID cannot represent a non-string and non-integer value:"
                ' {value: "1"}',
            )
            _parse_literal_raises(
                "ENUM_VALUE",
                "ID cannot represent a non-string and non-integer value: ENUM_VALUE",
            )
            _parse_literal_raises(
                "$var", "ID cannot represent a non-string and non-integer value: $var"
            )
