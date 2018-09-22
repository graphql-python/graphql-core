from graphql.language import parse
from graphql.type import (
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLString,
    GraphQLArgument,
)
from graphql.utilities import find_deprecated_usages


def describe_find_deprecated_usages():

    enum_type = GraphQLEnumType(
        "EnumType",
        {
            "ONE": GraphQLEnumValue(),
            "TWO": GraphQLEnumValue(deprecation_reason="Some enum reason."),
        },
    )

    schema = GraphQLSchema(
        GraphQLObjectType(
            "Query",
            {
                "normalField": GraphQLField(
                    GraphQLString, args={"enumArg": GraphQLArgument(enum_type)}
                ),
                "deprecatedField": GraphQLField(
                    GraphQLString, deprecation_reason="Some field reason."
                ),
            },
        )
    )

    def should_report_empty_set_for_no_deprecated_usages():
        errors = find_deprecated_usages(schema, parse("{ normalField(enumArg: ONE) }"))

        assert errors == []

    def should_report_usage_of_deprecated_fields():
        errors = find_deprecated_usages(
            schema, parse("{ normalField, deprecatedField }")
        )

        error_messages = [err.message for err in errors]

        assert error_messages == [
            "The field Query.deprecatedField is deprecated. Some field reason."
        ]

    def should_report_usage_of_deprecated_enums():
        errors = find_deprecated_usages(schema, parse("{ normalField(enumArg: TWO) }"))

        error_messages = [err.message for err in errors]

        assert error_messages == [
            "The enum value EnumType.TWO is deprecated. Some enum reason."
        ]
