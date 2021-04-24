from functools import partial
from typing import Callable, List, Tuple

from graphql.utilities import build_schema
from graphql.validation import NoDeprecatedCustomRule

from .harness import assert_validation_errors


def build_assertions(
    sdl_str: str,
) -> Tuple[Callable[[str], None], Callable[[str, List], None]]:
    schema = build_schema(sdl_str)
    assert_errors = partial(
        assert_validation_errors, NoDeprecatedCustomRule, schema=schema
    )
    assert_valid = partial(assert_errors, errors=[])
    return (
        assert_valid,
        assert_errors,
    )  # type: ignore


def describe_validate_no_deprecated():
    def describe_no_deprecated_fields():
        _assert_valid, _assert_errors = build_assertions(
            """
            type Query {
              normalField: String
              deprecatedField: String @deprecated(reason: "Some field reason.")
            }
            """
        )

        def ignores_fields_and_enum_values_that_are_not_deprecated():
            _assert_valid(
                """
                {
                  normalField
                }
                """
            )

        def ignores_unknown_fields():
            _assert_valid(
                """
                {
                  unknownField
                }

                fragment UnknownFragment on UnknownType {
                  unknownField
                }
                """
            )

        def reports_error_when_a_deprecated_field_is_selected():
            message = (
                "The field Query.deprecatedField is deprecated. Some field reason."
            )
            _assert_errors(
                """
                {
                  deprecatedField
                }

                fragment QueryFragment on Query {
                  deprecatedField
                }
                """,
                [
                    {
                        "message": message,
                        "locations": [(3, 19)],
                    },
                    {
                        "message": message,
                        "locations": [(7, 19)],
                    },
                ],
            )

    def describe_no_deprecated_enum_values():
        _assert_valid, _assert_errors = build_assertions(
            """
            enum EnumType {
              NORMAL_VALUE
              DEPRECATED_VALUE @deprecated(reason: "Some enum reason.")
            }

            type Query {
              someField(enumArg: EnumType): String
            }
            """
        )

        def ignores_enum_values_that_are_not_deprecated():
            _assert_valid(
                """
                {
                  normalField(enumArg: NORMAL_VALUE)
                }
                """
            )

        def ignores_unknown_enum_values():
            _assert_valid(
                """
                query (
                  $unknownValue: EnumType = UNKNOWN_VALUE
                  $unknownType: UnknownType = UNKNOWN_VALUE
                ) {
                  someField(enumArg: UNKNOWN_VALUE)
                  someField(unknownArg: UNKNOWN_VALUE)
                  unknownField(unknownArg: UNKNOWN_VALUE)
                }

                fragment SomeFragment on Query {
                  someField(enumArg: UNKNOWN_VALUE)
                }
                """
            )

        def reports_error_when_a_deprecated_enum_value_is_used():
            message = (
                "The enum value 'EnumType.DEPRECATED_VALUE' is deprecated."
                " Some enum reason."
            )
            _assert_errors(
                """
                query (
                  $variable: EnumType = DEPRECATED_VALUE
                ) {
                  someField(enumArg: DEPRECATED_VALUE)
                }

                fragment QueryFragment on Query {
                  someField(enumArg: DEPRECATED_VALUE)
                }
                """,
                [
                    {
                        "message": message,
                        "locations": [(3, 41)],
                    },
                    {
                        "message": message,
                        "locations": [(5, 38)],
                    },
                    {
                        "message": message,
                        "locations": [(9, 38)],
                    },
                ],
            )
