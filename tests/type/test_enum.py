from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from graphql import graphql_sync
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInt,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import introspection_from_schema

ColorType = GraphQLEnumType("Color", values={"RED": 0, "GREEN": 1, "BLUE": 2})


class ColorTypeEnumValues(Enum):
    RED = 0
    GREEN = 1
    BLUE = 2


class Complex1:
    # noinspection PyMethodMayBeStatic
    some_random_object = datetime.now()


class Complex2:
    some_random_value = 123


complex1 = Complex1()
complex2 = Complex2()

ComplexEnum = GraphQLEnumType("Complex", {"ONE": complex1, "TWO": complex2})

ColorType2 = GraphQLEnumType("Color", ColorTypeEnumValues)

QueryType = GraphQLObjectType(
    "Query",
    {
        "colorEnum": GraphQLField(
            ColorType,
            args={
                "fromEnum": GraphQLArgument(ColorType),
                "fromInt": GraphQLArgument(GraphQLInt),
                "fromString": GraphQLArgument(GraphQLString),
            },
            resolve=lambda _source, info, **args: args.get("fromInt")
            or args.get("fromString")
            or args.get("fromEnum"),
        ),
        "colorInt": GraphQLField(
            GraphQLInt,
            args={
                "fromEnum": GraphQLArgument(ColorType),
                "fromInt": GraphQLArgument(GraphQLInt),
            },
            resolve=lambda _source, info, **args: args.get("fromEnum"),
        ),
        "complexEnum": GraphQLField(
            ComplexEnum,
            args={
                # Note: default_value is provided an *internal* representation for
                # Enums, rather than the string name.
                "fromEnum": GraphQLArgument(ComplexEnum, default_value=complex1),
                "provideGoodValue": GraphQLArgument(GraphQLBoolean),
                "provideBadValue": GraphQLArgument(GraphQLBoolean),
            },
            resolve=lambda _source, info, **args:
            # Note: this is one of the references of the internal values
            # which ComplexEnum allows.
            complex2 if args.get("provideGoodValue")
            # Note: similar object, but not the same *reference* as
            # complex2 above. Enum internal values require object equality.
            else Complex2() if args.get("provideBadValue") else args.get("fromEnum"),
        ),
    },
)

MutationType = GraphQLObjectType(
    "Mutation",
    {
        "favoriteEnum": GraphQLField(
            ColorType,
            args={"color": GraphQLArgument(ColorType)},
            resolve=lambda _source, info, color=None: color,
        )
    },
)

SubscriptionType = GraphQLObjectType(
    "Subscription",
    {
        "subscribeToEnum": GraphQLField(
            ColorType,
            args={"color": GraphQLArgument(ColorType)},
            resolve=lambda _source, info, color=None: color,
        )
    },
)

schema = GraphQLSchema(
    query=QueryType, mutation=MutationType, subscription=SubscriptionType
)


def execute_query(source: str, variable_values: Optional[Dict[str, Any]] = None):
    return graphql_sync(schema, source, variable_values=variable_values)


def describe_type_system_enum_values():
    def can_use_python_enums_instead_of_dicts():
        assert ColorType2.values == ColorType.values
        keys = [key for key in ColorType.values]
        keys2 = [key for key in ColorType2.values]
        assert keys2 == keys
        values = [value.value for value in ColorType.values.values()]
        values2 = [value.value for value in ColorType2.values.values()]
        assert values2 == values

    def accepts_enum_literals_as_input():
        result = execute_query("{ colorInt(fromEnum: GREEN) }")

        assert result == ({"colorInt": 1}, None)

    def enum_may_be_output_type():
        result = execute_query("{ colorEnum(fromInt: 1) }")

        assert result == ({"colorEnum": "GREEN"}, None)

    def enum_may_be_both_input_and_output_type():
        result = execute_query("{ colorEnum(fromEnum: GREEN) }")

        assert result == ({"colorEnum": "GREEN"}, None)

    def does_not_accept_string_literals():
        result = execute_query('{ colorEnum(fromEnum: "GREEN") }')

        assert result == (
            None,
            [
                {
                    "message": "Enum 'Color' cannot represent non-enum value:"
                    ' "GREEN".'
                    " Did you mean the enum value 'GREEN'?",
                    "locations": [(1, 23)],
                }
            ],
        )

    def does_not_accept_values_not_in_the_enum():
        result = execute_query("{ colorEnum(fromEnum: GREENISH) }")

        assert result == (
            None,
            [
                {
                    "message": "Value 'GREENISH' does not exist in 'Color' enum."
                    " Did you mean the enum value 'GREEN'?",
                    "locations": [(1, 23)],
                }
            ],
        )

    def does_not_accept_values_with_incorrect_casing():
        result = execute_query("{ colorEnum(fromEnum: green) }")

        assert result == (
            None,
            [
                {
                    "message": "Value 'green' does not exist in 'Color' enum."
                    " Did you mean the enum value 'GREEN' or 'RED'?",
                    "locations": [(1, 23)],
                }
            ],
        )

    def does_not_accept_incorrect_internal_value():
        result = execute_query('{ colorEnum(fromString: "GREEN") }')

        assert result == (
            {"colorEnum": None},
            [
                {
                    "message": "Enum 'Color' cannot represent value: 'GREEN'",
                    "locations": [(1, 3)],
                    "path": ["colorEnum"],
                }
            ],
        )

    def does_not_accept_internal_value_in_place_of_enum_literal():
        result = execute_query("{ colorEnum(fromEnum: 1) }")

        assert result == (
            None,
            [
                {
                    "message": "Enum 'Color' cannot represent non-enum value: 1.",
                    "locations": [(1, 23)],
                }
            ],
        )

    def does_not_accept_enum_literal_in_place_of_int():
        result = execute_query("{ colorEnum(fromInt: GREEN) }")

        assert result == (
            None,
            [
                {
                    "message": "Int cannot represent non-integer value: GREEN",
                    "locations": [(1, 22)],
                }
            ],
        )

    def accepts_json_string_as_enum_variable():
        doc = "query ($color: Color!) { colorEnum(fromEnum: $color) }"
        result = execute_query(doc, {"color": "BLUE"})

        assert result == ({"colorEnum": "BLUE"}, None)

    def accepts_enum_literals_as_input_arguments_to_mutations():
        doc = "mutation ($color: Color!) { favoriteEnum(color: $color) }"
        result = execute_query(doc, {"color": "GREEN"})

        assert result == ({"favoriteEnum": "GREEN"}, None)

    def accepts_enum_literals_as_input_arguments_to_subscriptions():
        doc = "subscription ($color: Color!) { subscribeToEnum(color: $color) }"
        result = execute_query(doc, {"color": "GREEN"})

        assert result == ({"subscribeToEnum": "GREEN"}, None)

    def does_not_accept_internal_value_as_enum_variable():
        doc = "query ($color: Color!) { colorEnum(fromEnum: $color) }"
        result = execute_query(doc, {"color": 2})

        assert result == (
            None,
            [
                {
                    "message": "Variable '$color' got invalid value 2;"
                    " Enum 'Color' cannot represent non-string value: 2.",
                    "locations": [(1, 8)],
                }
            ],
        )

    def does_not_accept_string_variables_as_enum_input():
        doc = "query ($color: String!) { colorEnum(fromEnum: $color) }"
        result = execute_query(doc, {"color": "BLUE"})

        assert result == (
            None,
            [
                {
                    "message": "Variable '$color' of type 'String!'"
                    " used in position expecting type 'Color'.",
                    "locations": [(1, 8), (1, 47)],
                }
            ],
        )

    def does_not_accept_internal_value_variable_as_enum_input():
        doc = "query ($color: Int!) { colorEnum(fromEnum: $color) }"
        result = execute_query(doc, {"color": 2})

        assert result == (
            None,
            [
                {
                    "message": "Variable '$color' of type 'Int!'"
                    " used in position expecting type 'Color'.",
                    "locations": [(1, 8), (1, 44)],
                }
            ],
        )

    def enum_value_may_have_an_internal_value_of_0():
        result = execute_query(
            """
            {
              colorEnum(fromEnum: RED)
              colorInt(fromEnum: RED)
            }
            """
        )

        assert result == ({"colorEnum": "RED", "colorInt": 0}, None)

    def enum_inputs_may_be_nullable():
        result = execute_query(
            """
            {
              colorEnum
              colorInt
            }
            """
        )

        assert result == ({"colorEnum": None, "colorInt": None}, None)

    def presents_a_values_property_for_complex_enums():
        values = ComplexEnum.values
        assert isinstance(values, dict)
        assert all(isinstance(value, GraphQLEnumValue) for value in values.values())
        assert {key: value.value for key, value in values.items()} == {
            "ONE": complex1,
            "TWO": complex2,
        }

    def may_be_internally_represented_with_complex_values():
        result = execute_query(
            """
            {
              first: complexEnum
              second: complexEnum(fromEnum: TWO)
              good: complexEnum(provideGoodValue: true)
              bad: complexEnum(provideBadValue: true)
            }
            """
        )

        assert result == (
            {"first": "ONE", "second": "TWO", "good": "TWO", "bad": None},
            [
                {
                    "message": "Enum 'Complex' cannot represent value:"
                    " <Complex2 instance>",
                    "locations": [(6, 15)],
                    "path": ["bad"],
                }
            ],
        )

    def can_be_introspected_without_error():
        introspection_from_schema(schema)
