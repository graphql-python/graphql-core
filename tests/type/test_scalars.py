import pickle
from math import inf, nan, pi
from typing import Any

import pytest

from graphql.error import GraphQLError
from graphql.language import parse_const_value as parse_const_value_to_ast
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLScalarType,
    GraphQLString,
)


def describe_type_system_specified_scalar_types():
    def describe_graphql_int():
        def coerce_input_value():
            _coerce_input_value = GraphQLInt.coerce_input_value

            def _coerce_input_value_raises(s: Any, message: str):
                with pytest.raises(GraphQLError) as exc_info:
                    _coerce_input_value(s)
                assert str(exc_info.value) == message

            assert _coerce_input_value(1) == 1
            assert _coerce_input_value(0) == 0
            assert _coerce_input_value(-1) == -1

            _coerce_input_value_raises(
                9876504321,
                "Int cannot represent non 32-bit signed integer value: 9876504321",
            )
            _coerce_input_value_raises(
                -9876504321,
                "Int cannot represent non 32-bit signed integer value: -9876504321",
            )
            _coerce_input_value_raises(
                0.1, "Int cannot represent non-integer value: 0.1"
            )
            _coerce_input_value_raises(
                nan, "Int cannot represent non-integer value: nan"
            )
            _coerce_input_value_raises(
                inf, "Int cannot represent non-integer value: inf"
            )
            _coerce_input_value_raises(
                Undefined, "Int cannot represent non-integer value: Undefined"
            )
            _coerce_input_value_raises(
                None, "Int cannot represent non-integer value: None"
            )
            _coerce_input_value_raises("", "Int cannot represent non-integer value: ''")
            _coerce_input_value_raises(
                "123", "Int cannot represent non-integer value: '123'"
            )
            _coerce_input_value_raises(
                False, "Int cannot represent non-integer value: False"
            )
            _coerce_input_value_raises(
                True, "Int cannot represent non-integer value: True"
            )
            _coerce_input_value_raises(
                [1], "Int cannot represent non-integer value: [1]"
            )
            _coerce_input_value_raises(
                {"value": 1}, "Int cannot represent non-integer value: {'value': 1}"
            )

        def coerce_input_literal():
            def _parse_literal(s: str):
                # to be removed in v18 when all custom scalars have a default method
                return GraphQLInt.coerce_input_literal(  # type: ignore
                    parse_const_value_to_ast(s)
                )

            def _parse_literal_raises(s: str, message: str):
                with pytest.raises(GraphQLError) as exc_info:
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
                "{value: 1}", "Int cannot represent non-integer value: { value: 1 }"
            )
            _parse_literal_raises(
                "ENUM_VALUE", "Int cannot represent non-integer value: ENUM_VALUE"
            )

        def coerce_output_value():
            coerce_output_value = GraphQLInt.coerce_output_value

            assert coerce_output_value(1) == 1
            assert coerce_output_value("123") == 123
            assert coerce_output_value(0) == 0
            assert coerce_output_value(-1) == -1
            assert coerce_output_value(1e5) == 100000
            assert coerce_output_value(False) == 0
            assert coerce_output_value(True) == 1
            assert coerce_output_value(type("Int", (int,), {})(5)) == 5

            # The GraphQL specification does not allow serializing non-integer
            # values as Int to avoid accidental data loss.
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(0.1)
            assert str(exc_info.value) == "Int cannot represent non-integer value: 0.1"
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(1.1)
            assert str(exc_info.value) == "Int cannot represent non-integer value: 1.1"
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(-1.1)
            assert str(exc_info.value) == "Int cannot represent non-integer value: -1.1"
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value("-1.1")
            assert (
                str(exc_info.value) == "Int cannot represent non-integer value: '-1.1'"
            )
            # Maybe a safe JavaScript int, but bigger than 2^32, so not
            # representable as a GraphQL Int
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(9876504321)
            assert str(exc_info.value) == (
                "Int cannot represent non 32-bit signed integer value: 9876504321"
            )
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(-9876504321)
            assert str(exc_info.value) == (
                "Int cannot represent non 32-bit signed integer value: -9876504321"
            )
            # Too big to represent as an Int in JavaScript or GraphQL
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(1e100)
            assert str(exc_info.value) == (
                "Int cannot represent non 32-bit signed integer value: 1e+100"
            )
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(-1e100)
            assert str(exc_info.value) == (
                "Int cannot represent non 32-bit signed integer value: -1e+100"
            )
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value("one")
            assert (
                str(exc_info.value) == "Int cannot represent non-integer value: 'one'"
            )
            # Doesn't represent number
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value("")
            assert str(exc_info.value) == "Int cannot represent non-integer value: ''"
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(nan)
            assert str(exc_info.value) == "Int cannot represent non-integer value: nan"
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(inf)
            assert str(exc_info.value) == "Int cannot represent non-integer value: inf"
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value([5])
            assert str(exc_info.value) == "Int cannot represent non-integer value: [5]"

        def cannot_be_redefined():
            with pytest.raises(TypeError, match="Redefinition of reserved type 'Int'"):
                GraphQLScalarType(name="Int")

        def pickles():
            assert pickle.loads(pickle.dumps(GraphQLInt)) is GraphQLInt

    def describe_graphql_float():
        def coerce_input_value():
            _coerce_input_value = GraphQLFloat.coerce_input_value

            def _coerce_input_value_raises(s: Any, message: str):
                with pytest.raises(GraphQLError) as exc_info:
                    _coerce_input_value(s)
                assert str(exc_info.value) == message

            assert _coerce_input_value(1) == 1
            assert _coerce_input_value(0) == 0
            assert _coerce_input_value(-1) == -1
            assert _coerce_input_value(0.1) == 0.1
            assert _coerce_input_value(pi) == pi

            _coerce_input_value_raises(
                nan, "Float cannot represent non numeric value: nan"
            )
            _coerce_input_value_raises(
                inf, "Float cannot represent non numeric value: inf"
            )
            _coerce_input_value_raises(
                "", "Float cannot represent non numeric value: ''"
            )
            _coerce_input_value_raises(
                "123", "Float cannot represent non numeric value: '123'"
            )
            _coerce_input_value_raises(
                "123.5", "Float cannot represent non numeric value: '123.5'"
            )
            _coerce_input_value_raises(
                False, "Float cannot represent non numeric value: False"
            )
            _coerce_input_value_raises(
                True, "Float cannot represent non numeric value: True"
            )
            _coerce_input_value_raises(
                [0.1], "Float cannot represent non numeric value: [0.1]"
            )
            _coerce_input_value_raises(
                {"value": 0.1},
                "Float cannot represent non numeric value: {'value': 0.1}",
            )

        def coerce_input_literal():
            def _parse_literal(s: str):
                # to be removed in v18 when all custom scalars have a default method
                return GraphQLFloat.coerce_input_literal(  # type: ignore
                    parse_const_value_to_ast(s)
                )

            def _parse_literal_raises(s: str, message: str):
                with pytest.raises(GraphQLError) as exc_info:
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
                "{value: 0.1}",
                "Float cannot represent non numeric value: { value: 0.1 }",
            )
            _parse_literal_raises(
                "ENUM_VALUE", "Float cannot represent non numeric value: ENUM_VALUE"
            )

        def coerce_output_value():
            coerce_output_value = GraphQLFloat.coerce_output_value

            assert coerce_output_value(1) == 1.0
            assert coerce_output_value(0) == 0.0
            assert coerce_output_value("123.5") == 123.5
            assert coerce_output_value(-1) == -1.0
            assert coerce_output_value(0.1) == 0.1
            assert coerce_output_value(1.1) == 1.1
            assert coerce_output_value(-1.1) == -1.1
            assert coerce_output_value("-1.1") == -1.1
            assert coerce_output_value(False) == 0
            assert coerce_output_value(True) == 1
            assert coerce_output_value(type("Float", (float,), {})(5.5)) == 5.5

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(nan)
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: nan"
            )
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(inf)
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: inf"
            )
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value("one")
            assert str(exc_info.value) == (
                "Float cannot represent non numeric value: 'one'"
            )
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value("")
            assert str(exc_info.value) == "Float cannot represent non numeric value: ''"
            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value([5])
            assert (
                str(exc_info.value) == "Float cannot represent non numeric value: [5]"
            )

        def cannot_be_redefined():
            with pytest.raises(
                TypeError, match="Redefinition of reserved type 'Float'"
            ):
                GraphQLScalarType(name="Float")

        def pickles():
            assert pickle.loads(pickle.dumps(GraphQLFloat)) is GraphQLFloat

    def describe_graphql_string():
        def coerce_input_value():
            _coerce_input_value = GraphQLString.coerce_input_value

            def _coerce_input_value_raises(s: Any, message: str):
                with pytest.raises(GraphQLError) as exc_info:
                    _coerce_input_value(s)
                assert str(exc_info.value) == message

            assert _coerce_input_value("foo") == "foo"

            _coerce_input_value_raises(
                Undefined, "String cannot represent a non string value: Undefined"
            )
            _coerce_input_value_raises(
                None, "String cannot represent a non string value: None"
            )
            _coerce_input_value_raises(
                1, "String cannot represent a non string value: 1"
            )
            _coerce_input_value_raises(
                nan, "String cannot represent a non string value: nan"
            )
            _coerce_input_value_raises(
                False, "String cannot represent a non string value: False"
            )
            _coerce_input_value_raises(
                ["foo"], "String cannot represent a non string value: ['foo']"
            )
            _coerce_input_value_raises(
                {"value": "foo"},
                "String cannot represent a non string value: {'value': 'foo'}",
            )

        def coerce_input_literal():
            def _parse_literal(s: str):
                # to be removed in v18 when all custom scalars have a default method
                return GraphQLString.coerce_input_literal(  # type: ignore
                    parse_const_value_to_ast(s)
                )

            def _parse_literal_raises(s: str, message: str):
                with pytest.raises(GraphQLError) as exc_info:
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
                'String cannot represent a non string value: { value: "foo" }',
            )
            _parse_literal_raises(
                "ENUM_VALUE", "String cannot represent a non string value: ENUM_VALUE"
            )

        def coerce_output_value():
            coerce_output_value = GraphQLString.coerce_output_value

            assert coerce_output_value("string") == "string"
            assert coerce_output_value(1) == "1"
            assert coerce_output_value(-1.1) == "-1.1"
            assert coerce_output_value(True) == "true"
            assert coerce_output_value(False) == "false"

            class StringableObjValue:
                def __str__(self):
                    return "something useful"

            assert coerce_output_value(StringableObjValue()) == "something useful"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(nan)
            assert str(exc_info.value) == "String cannot represent value: nan"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value([1])
            assert str(exc_info.value) == "String cannot represent value: [1]"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value({})
            assert str(exc_info.value) == "String cannot represent value: {}"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value({"value_of": "value_of string"})
            assert (
                str(exc_info.value) == "String cannot represent value:"
                " {'value_of': 'value_of string'}"
            )

        def cannot_be_redefined():
            with pytest.raises(
                TypeError, match="Redefinition of reserved type 'String'"
            ):
                GraphQLScalarType(name="String")

        def pickles():
            assert pickle.loads(pickle.dumps(GraphQLString)) is GraphQLString

    def describe_graphql_boolean():
        def coerce_input_value():
            _coerce_input_value = GraphQLBoolean.coerce_input_value

            def _coerce_input_value_raises(s: Any, message: str):
                with pytest.raises(GraphQLError) as exc_info:
                    _coerce_input_value(s)
                assert str(exc_info.value) == message

            assert _coerce_input_value(True) is True
            assert _coerce_input_value(False) is False

            _coerce_input_value_raises(
                Undefined, "Boolean cannot represent a non boolean value: Undefined"
            )
            _coerce_input_value_raises(
                None, "Boolean cannot represent a non boolean value: None"
            )
            _coerce_input_value_raises(
                0, "Boolean cannot represent a non boolean value: 0"
            )
            _coerce_input_value_raises(
                1, "Boolean cannot represent a non boolean value: 1"
            )
            _coerce_input_value_raises(
                nan, "Boolean cannot represent a non boolean value: nan"
            )
            _coerce_input_value_raises(
                "", "Boolean cannot represent a non boolean value: ''"
            )
            _coerce_input_value_raises(
                "false", "Boolean cannot represent a non boolean value: 'false'"
            )
            _coerce_input_value_raises(
                "False", "Boolean cannot represent a non boolean value: 'False'"
            )
            _coerce_input_value_raises(
                [False], "Boolean cannot represent a non boolean value: [False]"
            )
            _coerce_input_value_raises(
                {"value": False},
                "Boolean cannot represent a non boolean value: {'value': False}",
            )

        def coerce_input_literal():
            def _parse_literal(s: str):
                # to be removed in v18 when all custom scalars have a default method
                return GraphQLBoolean.coerce_input_literal(  # type: ignore
                    parse_const_value_to_ast(s)
                )

            def _parse_literal_raises(s: str, message: str):
                with pytest.raises(GraphQLError) as exc_info:
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
                "Boolean cannot represent a non boolean value: { value: false }",
            )
            _parse_literal_raises(
                "{value: False}",
                "Boolean cannot represent a non boolean value: { value: False }",
            )
            _parse_literal_raises(
                "ENUM_VALUE", "Boolean cannot represent a non boolean value: ENUM_VALUE"
            )

        def coerce_output_value():
            coerce_output_value = GraphQLBoolean.coerce_output_value

            assert coerce_output_value(1) is True
            assert coerce_output_value(0) is False
            assert coerce_output_value(True) is True
            assert coerce_output_value(False) is False
            with pytest.raises(TypeError, match="not an acceptable base type"):
                # you can't subclass bool in Python
                assert coerce_output_value(type("Boolean", (bool,), {})(True)) is True

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(nan)
            assert str(exc_info.value) == (
                "Boolean cannot represent a non boolean value: nan"
            )

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value("")
            assert str(exc_info.value) == (
                "Boolean cannot represent a non boolean value: ''"
            )

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value("True")
            assert str(exc_info.value) == (
                "Boolean cannot represent a non boolean value: 'True'"
            )

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value([False])
            assert str(exc_info.value) == (
                "Boolean cannot represent a non boolean value: [False]"
            )

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value({})
            assert str(exc_info.value) == (
                "Boolean cannot represent a non boolean value: {}"
            )

        def cannot_be_redefined():
            with pytest.raises(
                TypeError, match="Redefinition of reserved type 'Boolean'"
            ):
                GraphQLScalarType(name="Boolean")

        def pickles():
            assert pickle.loads(pickle.dumps(GraphQLBoolean)) is GraphQLBoolean

    def describe_graphql_id():
        def coerce_input_value():
            _coerce_input_value = GraphQLID.coerce_input_value

            def _coerce_input_value_raises(s: Any, message: str):
                with pytest.raises(GraphQLError) as exc_info:
                    _coerce_input_value(s)
                assert str(exc_info.value) == message

            assert _coerce_input_value("") == ""
            assert _coerce_input_value("1") == "1"
            assert _coerce_input_value("foo") == "foo"
            assert _coerce_input_value(1) == "1"
            assert _coerce_input_value(0) == "0"
            assert _coerce_input_value(-1) == "-1"
            assert _coerce_input_value(1.0) == "1"

            # Maximum and minimum safe numbers in JS
            assert _coerce_input_value(9007199254740991) == "9007199254740991"
            assert _coerce_input_value(-9007199254740991) == "-9007199254740991"

            _coerce_input_value_raises(
                Undefined, "ID cannot represent value: Undefined"
            )
            _coerce_input_value_raises(None, "ID cannot represent value: None")
            _coerce_input_value_raises(0.1, "ID cannot represent value: 0.1")
            _coerce_input_value_raises(nan, "ID cannot represent value: nan")
            _coerce_input_value_raises(inf, "ID cannot represent value: inf")
            _coerce_input_value_raises(False, "ID cannot represent value: False")
            _coerce_input_value_raises(["1"], "ID cannot represent value: ['1']")
            _coerce_input_value_raises(
                {"value": "1"}, "ID cannot represent value: {'value': '1'}"
            )

        def coerce_input_literal():
            def _parse_literal(s: str):
                # to be removed in v18 when all custom scalars have a default method
                return GraphQLID.coerce_input_literal(  # type: ignore
                    parse_const_value_to_ast(s)
                )

            def _parse_literal_raises(s: str, message: str):
                with pytest.raises(GraphQLError) as exc_info:
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
                '{ value: "1" }',
                "ID cannot represent a non-string and non-integer value:"
                ' { value: "1" }',
            )
            _parse_literal_raises(
                "ENUM_VALUE",
                "ID cannot represent a non-string and non-integer value: ENUM_VALUE",
            )

        def coerce_output_value():
            coerce_output_value = GraphQLID.coerce_output_value

            assert coerce_output_value("string") == "string"
            assert coerce_output_value("false") == "false"
            assert coerce_output_value("") == ""
            assert coerce_output_value(123) == "123"
            assert coerce_output_value(42.0) == "42"
            assert coerce_output_value(0) == "0"
            assert coerce_output_value(-1) == "-1"

            class ObjValue:
                def __init__(self, value):
                    self._id = value

                def __str__(self):
                    return str(self._id)

            obj_value = ObjValue(123)
            assert coerce_output_value(obj_value) == "123"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(True)
            assert str(exc_info.value) == "ID cannot represent value: True"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(3.14)
            assert str(exc_info.value) == "ID cannot represent value: 3.14"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value({})
            assert str(exc_info.value) == "ID cannot represent value: {}"

            with pytest.raises(GraphQLError) as exc_info:
                coerce_output_value(["abc"])
            assert str(exc_info.value) == "ID cannot represent value: ['abc']"

        def cannot_be_redefined():
            with pytest.raises(TypeError, match="Redefinition of reserved type 'ID'"):
                GraphQLScalarType(name="ID")

        def pickles():
            assert pickle.loads(pickle.dumps(GraphQLID)) is GraphQLID
