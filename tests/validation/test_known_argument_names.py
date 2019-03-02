from functools import partial

from graphql.utilities import build_schema
from graphql.validation import KnownArgumentNamesRule
from graphql.validation.rules.known_argument_names import (
    KnownArgumentNamesOnDirectivesRule,
    unknown_arg_message,
    unknown_directive_arg_message,
)

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, KnownArgumentNamesRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(
    assert_sdl_validation_errors, KnownArgumentNamesOnDirectivesRule
)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def unknown_arg(arg_name, field_name, type_name, suggested_args, line, column):
    return {
        "message": unknown_arg_message(arg_name, field_name, type_name, suggested_args),
        "locations": [(line, column)],
    }


def unknown_directive_arg(arg_name, directive_name, suggested_args, line, column):
    return {
        "message": unknown_directive_arg_message(
            arg_name, directive_name, suggested_args
        ),
        "locations": [(line, column)],
    }


def describe_validate_known_argument_names():
    def single_arg_is_known():
        assert_valid(
            """
            fragment argOnRequiredArg on Dog {
              doesKnowCommand(dogCommand: SIT)
            }
            """
        )

    def multiple_args_are_known():
        assert_valid(
            """
            fragment multipleArgs on ComplicatedArgs {
              multipleReqs(req1: 1, req2: 2)
            }
            """
        )

    def ignore_args_of_unknown_fields():
        assert_valid(
            """
            fragment argOnUnknownField on Dog {
              unknownField(unknownArg: SIT)
            }
            """
        )

    def multiple_args_in_reverse_order_are_known():
        assert_valid(
            """
            fragment multipleArgsReverseOrder on ComplicatedArgs {
              multipleReqs(req2: 2, req1: 1)
            }
            """
        )

    def no_args_on_optional_arg():
        assert_valid(
            """
            fragment noArgOnOptionalArg on Dog {
              isHousetrained
            }
            """
        )

    def args_are_known_deeply():
        assert_valid(
            """
            {
              dog {
                doesKnowCommand(dogCommand: SIT)
              }
              human {
                pet {
                  ... on Dog {
                      doesKnowCommand(dogCommand: SIT)
                  }
                }
              }
            }
            """
        )

    def directive_args_are_known():
        assert_valid(
            """
            {
              dog @skip(if: true)
            }
            """
        )

    def field_args_are_invalid():
        assert_errors(
            """
            {
              dog @skip(unless: true)
            }
            """,
            [unknown_directive_arg("unless", "skip", [], 3, 25)],
        )

    def misspelled_directive_args_are_reported():
        assert_errors(
            """
            {
              dog @skip(iff: true)
            }
            """,
            [unknown_directive_arg("iff", "skip", ["if"], 3, 25)],
        )

    def invalid_arg_name():
        assert_errors(
            """
            fragment invalidArgName on Dog {
              doesKnowCommand(unknown: true)
            }
            """,
            [unknown_arg("unknown", "doesKnowCommand", "Dog", [], 3, 31)],
        )

    def misspelled_args_name_is_reported():
        assert_errors(
            """
            fragment invalidArgName on Dog {
              doesKnowCommand(dogcommand: true)
            }
            """,
            [
                unknown_arg(
                    "dogcommand", "doesKnowCommand", "Dog", ["dogCommand"], 3, 31
                )
            ],
        )

    def unknown_args_amongst_known_args():
        assert_errors(
            """
            fragment oneGoodArgOneInvalidArg on Dog {
              doesKnowCommand(whoknows: 1, dogCommand: SIT, unknown: true)
            }
            """,
            [
                unknown_arg("whoknows", "doesKnowCommand", "Dog", [], 3, 31),
                unknown_arg("unknown", "doesKnowCommand", "Dog", [], 3, 61),
            ],
        )

    def unknown_args_deeply():
        assert_errors(
            """
            {
              dog {
                doesKnowCommand(unknown: true)
              }
              human {
                pet {
                  ... on Dog {
                    doesKnowCommand(unknown: true)
                  }
                }
              }
            }
            """,
            [
                unknown_arg("unknown", "doesKnowCommand", "Dog", [], 4, 33),
                unknown_arg("unknown", "doesKnowCommand", "Dog", [], 9, 37),
            ],
        )

    def describe_within_sdl():
        def known_arg_on_directive_inside_sdl():
            assert_sdl_valid(
                """
                type Query {
                  foo: String @test(arg: "")
                }

                directive @test(arg: String) on FIELD_DEFINITION
                """
            )

        def unknown_arg_on_directive_defined_inside_sdl():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @test(unknown: "")
                }

                directive @test(arg: String) on FIELD_DEFINITION
                """,
                [unknown_directive_arg("unknown", "test", [], 3, 37)],
            )

        def misspelled_arg_name_is_reported_on_directive_defined_inside_sdl():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @test(agr: "")
                }

                directive @test(arg: String) on FIELD_DEFINITION
                """,
                [unknown_directive_arg("agr", "test", ["arg"], 3, 37)],
            )

        def unknown_arg_on_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @deprecated(unknown: "")
                }
                """,
                [unknown_directive_arg("unknown", "deprecated", [], 3, 43)],
            )

        def unknown_arg_on_overridden_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @deprecated(reason: "")
                }
                directive @deprecated(arg: String) on FIELD
                """,
                [unknown_directive_arg("reason", "deprecated", [], 3, 43)],
            )

        def unknown_arg_on_directive_defined_in_schema_extension():
            schema = build_schema(
                """
                type Query {
                  foo: String
                }
                """
            )
            assert_sdl_errors(
                """
                directive @test(arg: String) on OBJECT

                extend type Query  @test(unknown: "")
                """,
                [unknown_directive_arg("unknown", "test", [], 4, 42)],
                schema,
            )

        def unknown_arg_on_directive_used_in_schema_extension():
            schema = build_schema(
                """
                directive @test(arg: String) on OBJECT

                type Query {
                  foo: String
                }
                """
            )
            assert_sdl_errors(
                """
                extend type Query @test(unknown: "")
                """,
                [unknown_directive_arg("unknown", "test", [], 2, 41)],
                schema,
            )
