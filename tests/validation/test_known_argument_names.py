from functools import partial

from graphql.utilities import build_schema
from graphql.validation import KnownArgumentNamesRule
from graphql.validation.rules.known_argument_names import (
    KnownArgumentNamesOnDirectivesRule,
)

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, KnownArgumentNamesRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(
    assert_sdl_validation_errors, KnownArgumentNamesOnDirectivesRule
)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


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
              isHouseTrained
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
            [
                {
                    "message": "Unknown argument 'unless' on directive '@skip'.",
                    "locations": [(3, 25)],
                }
            ],
        )

    def directive_without_args_is_valid():
        assert_valid(
            """
            {
                dog @onField
            }
            """
        )

    def arg_passed_to_directive_without_args_is_reported():
        assert_errors(
            """
            {
                dog @onField(if: true)
            }
            """,
            [
                {
                    "message": "Unknown argument 'if' on directive '@onField'.",
                    "locations": [(3, 30)],
                }
            ],
        )

    def misspelled_directive_args_are_reported():
        assert_errors(
            """
            {
              dog @skip(iff: true)
            }
            """,
            [
                {
                    "message": "Unknown argument 'iff' on directive '@skip'."
                    " Did you mean 'if'?",
                    "locations": [(3, 25)],
                }
            ],
        )

    def invalid_arg_name():
        assert_errors(
            """
            fragment invalidArgName on Dog {
              doesKnowCommand(unknown: true)
            }
            """,
            [
                {
                    "message": "Unknown argument 'unknown'"
                    " on field 'Dog.doesKnowCommand'.",
                    "locations": [(3, 31)],
                },
            ],
        )

    def misspelled_arg_name_is_reported():
        assert_errors(
            """
            fragment invalidArgName on Dog {
              doesKnowCommand(DogCommand: true)
            }
            """,
            [
                {
                    "message": "Unknown argument 'DogCommand'"
                    " on field 'Dog.doesKnowCommand'."
                    " Did you mean 'dogCommand'?",
                    "locations": [(3, 31)],
                }
            ],
        )

    def unknown_args_amongst_known_args():
        assert_errors(
            """
            fragment oneGoodArgOneInvalidArg on Dog {
              doesKnowCommand(whoKnows: 1, dogCommand: SIT, unknown: true)
            }
            """,
            [
                {
                    "message": "Unknown argument 'whoKnows'"
                    " on field 'Dog.doesKnowCommand'.",
                    "locations": [(3, 31)],
                },
                {
                    "message": "Unknown argument 'unknown'"
                    " on field 'Dog.doesKnowCommand'.",
                    "locations": [(3, 61)],
                },
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
                {
                    "message": "Unknown argument 'unknown'"
                    " on field 'Dog.doesKnowCommand'.",
                    "locations": [(4, 33)],
                },
                {
                    "message": "Unknown argument 'unknown'"
                    " on field 'Dog.doesKnowCommand'.",
                    "locations": [(9, 37)],
                },
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
                [
                    {
                        "message": "Unknown argument 'unknown' on directive '@test'.",
                        "locations": [(3, 37)],
                    },
                ],
            )

        def misspelled_arg_name_is_reported_on_directive_defined_inside_sdl():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @test(agr: "")
                }

                directive @test(arg: String) on FIELD_DEFINITION
                """,
                [
                    {
                        "message": "Unknown argument 'agr' on directive '@test'."
                        " Did you mean 'arg'?",
                        "locations": [(3, 37)],
                    },
                ],
            )

        def unknown_arg_on_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @deprecated(unknown: "")
                }
                """,
                [
                    {
                        "message": "Unknown argument 'unknown'"
                        " on directive '@deprecated'.",
                        "locations": [(3, 43)],
                    },
                ],
            )

        def unknown_arg_on_overridden_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @deprecated(reason: "")
                }
                directive @deprecated(arg: String) on FIELD
                """,
                [
                    {
                        "message": "Unknown argument 'reason'"
                        " on directive '@deprecated'.",
                        "locations": [(3, 43)],
                    },
                ],
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
                [
                    {
                        "message": "Unknown argument 'unknown' on directive '@test'.",
                        "locations": [(4, 42)],
                    },
                ],
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
                [
                    {
                        "message": "Unknown argument 'unknown' on directive '@test'.",
                        "locations": [(2, 41)],
                    },
                ],
                schema,
            )
