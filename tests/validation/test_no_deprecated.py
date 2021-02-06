from functools import partial

from graphql.utilities import build_schema
from graphql.validation import NoDeprecatedCustomRule

from .harness import assert_validation_errors

schema = build_schema(
    """
    enum EnumType {
      NORMAL_VALUE
      DEPRECATED_VALUE @deprecated(reason: "Some enum reason.")
      DEPRECATED_VALUE_WITH_NO_REASON @deprecated
    }

    type Query {
      normalField(enumArg: [EnumType]): String
      deprecatedField: String @deprecated(reason: "Some field reason.")
      deprecatedFieldWithNoReason: String @deprecated
    }
    """
)

assert_errors = partial(assert_validation_errors, NoDeprecatedCustomRule, schema=schema)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_no_deprecated():
    def ignores_fields_and_enum_values_that_are_not_deprecated():
        assert_valid(
            """
            {
              normalField(enumArg: [NORMAL_VALUE])
            }
            """
        )

    def ignores_unknown_fields_and_enum_values():
        assert_valid(
            """
            fragment UnknownFragment on UnknownType {
              unknownField(unknownArg: UNKNOWN_VALUE)
            }

            fragment QueryFragment on Query {
              unknownField(unknownArg: UNKNOWN_VALUE)
              normalField(enumArg: UNKNOWN_VALUE)
            }
            """
        )

    def reports_error_when_a_deprecated_field_is_selected():
        assert_errors(
            """
            {
              normalField
              deprecatedField
              deprecatedFieldWithNoReason
            }
            """,
            [
                {
                    "message": "The field Query.deprecatedField is deprecated."
                    " Some field reason.",
                    "locations": [(4, 15)],
                },
                {
                    "message": "The field Query.deprecatedFieldWithNoReason"
                    " is deprecated. No longer supported",
                    "locations": [(5, 15)],
                },
            ],
        )

    def reports_error_when_a_deprecated_enum_value_is_used():
        assert_errors(
            """
            {
              normalField(enumArg: [NORMAL_VALUE, DEPRECATED_VALUE])
              normalField(enumArg: [DEPRECATED_VALUE_WITH_NO_REASON])
            }
            """,
            [
                {
                    "message": "The enum value 'EnumType.DEPRECATED_VALUE'"
                    " is deprecated. Some enum reason.",
                    "locations": [(3, 51)],
                },
                {
                    "message": "The enum value"
                    " 'EnumType.DEPRECATED_VALUE_WITH_NO_REASON'"
                    " is deprecated. No longer supported",
                    "locations": [(4, 37)],
                },
            ],
        )

    def reports_error_when_deprecated_field_or_enum_value_is_used_inside_a_fragment():
        assert_errors(
            """
            fragment QueryFragment on Query {
              deprecatedField
              normalField(enumArg: [NORMAL_VALUE, DEPRECATED_VALUE])
            }
            """,
            [
                {
                    "message": "The field Query.deprecatedField is deprecated."
                    " Some field reason.",
                    "locations": [(3, 15)],
                },
                {
                    "message": "The enum value 'EnumType.DEPRECATED_VALUE'"
                    " is deprecated. Some enum reason.",
                    "locations": [(4, 51)],
                },
            ],
        )
