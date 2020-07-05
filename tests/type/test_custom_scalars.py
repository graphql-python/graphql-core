from typing import Any, Dict, NamedTuple

from graphql import graphql_sync
from graphql.error import GraphQLError
from graphql.language import ValueNode
from graphql.pyutils import inspect, is_finite
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLFloat,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
)
from graphql.utilities import value_from_ast_untyped

# this test is not (yet) part of GraphQL.js, see
# https://github.com/graphql/graphql-js/issues/2657


class Money(NamedTuple):
    amount: float
    currency: str


def serialize_money(output_value: Any) -> Dict[str, float]:
    if not isinstance(output_value, Money):
        raise GraphQLError("Cannot serialize money value: " + inspect(output_value))
    return output_value._asdict()


def parse_money_value(input_value: Any) -> Money:
    if not isinstance(input_value, Money):
        raise GraphQLError("Cannot parse money value: " + inspect(input_value))
    return input_value


def parse_money_literal(value_node: ValueNode, variables=None) -> Money:
    money = value_from_ast_untyped(value_node, variables)
    if variables is not None and (
        # variables are not set when checked with ValuesIOfCorrectTypeRule
        not money
        or not is_finite(money.get("amount"))
        or not isinstance(money.get("currency"), str)
    ):
        raise GraphQLError("Cannot parse literal money value: " + inspect(money))
    return Money(**money)


MoneyScalar = GraphQLScalarType(
    name="Money",
    serialize=serialize_money,
    parse_value=parse_money_value,
    parse_literal=parse_money_literal,
)


def resolve_balance(root, _info):
    return root


def resolve_to_euros(_root, _info, money):
    amount = money.amount
    currency = money.currency
    if not amount or currency == "EUR":
        return amount
    if currency == "DM":
        return amount * 0.5
    raise ValueError("Cannot convert to euros: " + inspect(money))


schema = GraphQLSchema(
    query=GraphQLObjectType(
        name="RootQueryType",
        fields={
            "balance": GraphQLField(MoneyScalar, resolve=resolve_balance),
            "toEuros": GraphQLField(
                GraphQLFloat,
                args={"money": GraphQLArgument(MoneyScalar)},
                resolve=resolve_to_euros,
            ),
        },
    )
)


def describe_custom_scalar():
    def serialize():
        source = """
            {
              balance
            }
            """

        result = graphql_sync(schema, source, root_value=Money(42, "DM"))
        assert result == ({"balance": {"amount": 42, "currency": "DM"}}, None)

    def serialize_with_error():
        source = """
            {
              balance
            }
            """

        result = graphql_sync(schema, source, root_value=21)
        assert result == (
            {"balance": None},
            [
                {
                    "message": "Cannot serialize money value: 21",
                    "locations": [(3, 15)],
                    "path": ["balance"],
                }
            ],
        )

    def parse_value():
        source = """
            query Money($money: Money!) {
              toEuros(money: $money)
            }
            """

        result = graphql_sync(
            schema, source, variable_values={"money": Money(24, "EUR")}
        )
        assert result == ({"toEuros": 24}, None)

        result = graphql_sync(
            schema, source, variable_values={"money": Money(42, "DM")}
        )
        assert result == ({"toEuros": 21}, None)

    def parse_value_with_error():
        source = """
            query Money($money: Money!) {
              toEuros(money: $money)
            }
            """

        result = graphql_sync(
            schema, source, variable_values={"money": Money(42, "USD")}
        )
        assert result == (
            {"toEuros": None},
            [
                {
                    "message": "Cannot convert to euros: (42, 'USD')",
                    "locations": [(3, 15)],
                }
            ],
        )

        result = graphql_sync(schema, source, variable_values={"money": 21})
        assert result == (
            None,
            [
                {
                    "message": "Variable '$money' got invalid value 21;"
                    " Cannot parse money value: 21",
                    "locations": [(2, 25)],
                }
            ],
        )

    def parse_literal():
        source = """
            query Money($amount: Float!, $currency: String!) {
              toEuros(money: {amount: $amount, currency: $currency})
            }
            """

        variable_values = {"amount": 42, "currency": "DM"}
        result = graphql_sync(schema, source, variable_values=variable_values)
        assert result == ({"toEuros": 21}, None)

    def parse_literal_with_errors():
        source = """
            query Money($amount: String!, $currency: Float!) {
              toEuros(money: {amount: $amount, currency: $currency})
            }
            """

        variable_values = {"amount": "DM", "currency": 42}
        result = graphql_sync(schema, source, variable_values=variable_values)
        assert result == (
            {"toEuros": None},
            [
                {
                    "message": "Argument 'money' has invalid value"
                    " {amount: $amount, currency: $currency}.",
                    "locations": [(3, 30)],
                },
            ],
        )
