from graphql.language import parse
from graphql.utilities import build_schema, find_deprecated_usages


def describe_find_deprecated_usages():

    schema = build_schema(
        """
        enum EnumType {
          NORMAL_VALUE
          DEPRECATED_VALUE @deprecated(reason: "Some enum reason.")
        }

        type Query {
          normalField(enumArg: EnumType): String
          deprecatedField: String @deprecated(reason: "Some field reason.")
        }
        """
    )

    def should_report_empty_set_for_no_deprecated_usages():
        errors = find_deprecated_usages(
            schema, parse("{ normalField(enumArg: [NORMAL_VALUE]) }")
        )

        assert errors == []

    def should_ignore_unknown_stuff():
        errors = find_deprecated_usages(
            schema,
            parse(
                """
                {
                  unknownField(unknownArg: UNKNOWN_VALUE)
                  normalField(enumArg: UNKNOWN_VALUE)
                }
                """
            ),
        )

        assert errors == []

    def should_report_usage_of_deprecated_fields():
        errors = find_deprecated_usages(
            schema, parse("{ normalField, deprecatedField }")
        )

        error_messages = [err.message for err in errors]

        assert error_messages == [
            "The field 'Query.deprecatedField' is deprecated. Some field reason."
        ]

    def should_report_usage_of_deprecated_enums():
        errors = find_deprecated_usages(
            schema,
            parse(
                """
                {
                  normalField(enumArg: [NORMAL_VALUE, DEPRECATED_VALUE])
                }
                """
            ),
        )

        error_messages = [err.message for err in errors]

        assert error_messages == [
            "The enum value 'EnumType.DEPRECATED_VALUE' is deprecated."
            " Some enum reason."
        ]
