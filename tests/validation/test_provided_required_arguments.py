from functools import partial

from graphql.utilities import build_schema
from graphql.validation import ProvidedRequiredArgumentsRule
from graphql.validation.rules.provided_required_arguments import (
    ProvidedRequiredArgumentsOnDirectivesRule,
)

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, ProvidedRequiredArgumentsRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(
    assert_sdl_validation_errors, ProvidedRequiredArgumentsOnDirectivesRule
)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def describe_validate_provided_required_arguments():
    def ignores_unknown_arguments():
        assert_valid(
            """
            {
              dog {
                isHouseTrained(unknownArgument: true)
              }
            }"""
        )

    def describe_valid_non_nullable_value():
        def arg_on_optional_arg():
            assert_valid(
                """
                {
                  dog {
                    isHouseTrained(atOtherHomes: true)
                  }
                }"""
            )

        def no_arg_on_optional_arg():
            assert_valid(
                """
                {
                  dog {
                    isHouseTrained
                  }
                }"""
            )

        def no_arg_on_non_null_field_with_default():
            assert_valid(
                """
                {
                  complicatedArgs {
                    nonNullFieldWithDefault
                  }
                }"""
            )

        def multiple_args():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleReqs(req1: 1, req2: 2)
                  }
                }
                """
            )

        def multiple_args_reverse_order():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleReqs(req2: 2, req1: 1)
                  }
                }
                """
            )

        def no_args_on_multiple_optional():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOpts
                  }
                }
                """
            )

        def one_arg_on_multiple_optional():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOpts(opt1: 1)
                  }
                }
                """
            )

        def second_arg_on_multiple_optional():
            assert_valid(
                """
                {
                    complicatedArgs {
                        multipleOpts(opt2: 1)
                    }
                }
                """
            )

        def multiple_required_args_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4)
                  }
                }
                """
            )

        def multiple_required_and_one_optional_arg_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5)
                  }
                }
                """
            )

        def all_required_and_optional_args_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5, opt2: 6)
                  }
                }
                """
            )

    def describe_invalid_non_nullable_value():
        def missing_one_non_nullable_argument():
            assert_errors(
                """
                {
                  complicatedArgs {
                    multipleReqs(req2: 2)
                  }
                }
                """,
                [
                    {
                        "message": "Field 'multipleReqs' argument 'req1'"
                        " of type 'Int!' is required, but it was not provided.",
                        "locations": [(4, 21)],
                    },
                ],
            )

        def missing_multiple_non_nullable_arguments():
            assert_errors(
                """
                {
                  complicatedArgs {
                    multipleReqs
                  }
                }
                """,
                [
                    {
                        "message": "Field 'multipleReqs' argument 'req1'"
                        " of type 'Int!' is required, but it was not provided.",
                        "locations": [(4, 21)],
                    },
                    {
                        "message": "Field 'multipleReqs' argument 'req2'"
                        " of type 'Int!' is required, but it was not provided.",
                        "locations": [(4, 21)],
                    },
                ],
            )

        def incorrect_value_and_missing_argument():
            assert_errors(
                """
                {
                  complicatedArgs {
                    multipleReqs(req1: "one")
                  }
                }
                """,
                [
                    {
                        "message": "Field 'multipleReqs' argument 'req2'"
                        " of type 'Int!' is required, but it was not provided.",
                        "locations": [(4, 21)],
                    },
                ],
            )

    def describe_directive_arguments():
        def ignores_unknown_directives():
            assert_valid(
                """
                {
                  dog @unknown
                }
                """
            )

        def with_directives_of_valid_type():
            assert_valid(
                """
                {
                  dog @include(if: true) {
                    name
                  }
                  human @skip(if: false) {
                    name
                  }
                }
                """
            )

        def with_directive_with_missing_types():
            assert_errors(
                """
                {
                  dog @include {
                    name @skip
                  }
                }
                """,
                [
                    {
                        "message": "Directive '@include' argument 'if' of type"
                        " 'Boolean!' is required, but it was not provided.",
                        "locations": [(3, 23)],
                    },
                    {
                        "message": "Directive '@skip' argument 'if' of type"
                        " 'Boolean!' is required, but it was not provided.",
                        "locations": [(4, 26)],
                    },
                ],
            )

    def describe_within_sdl():
        def missing_optional_args_on_directive_defined_inside_sdl():
            assert_sdl_valid(
                """
                type Query {
                foo: String @test
                }

                directive @test(arg1: String, arg2: String! = "") on FIELD_DEFINITION
                """
            )

        def missing_arg_on_directive_defined_inside_sdl():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @test
                }

                directive @test(arg: String!) on FIELD_DEFINITION
                """,
                [
                    {
                        "message": "Directive '@test' argument 'arg' of type"
                        " 'String!' is required, but it was not provided.",
                        "locations": [(3, 31)],
                    },
                ],
            )

        def missing_arg_on_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @include
                }
                """,
                [
                    {
                        "message": "Directive '@include' argument 'if' of type"
                        " 'Boolean!' is required, but it was not provided.",
                        "locations": [(3, 31)],
                    },
                ],
            )

        def missing_arg_on_overridden_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @deprecated
                }
                directive @deprecated(reason: String!) on FIELD
                """,
                [
                    {
                        "message": "Directive '@deprecated' argument 'reason' of type"
                        " 'String!' is required, but it was not provided.",
                        "locations": [(3, 31)],
                    },
                ],
            )

        def missing_arg_on_directive_defined_in_schema_extension():
            schema = build_schema(
                """
                type Query {
                  foo: String
                }
                """
            )
            assert_sdl_errors(
                """
                directive @test(arg: String!) on OBJECT

                extend type Query  @test
                """,
                [
                    {
                        "message": "Directive '@test' argument 'arg' of type"
                        " 'String!' is required, but it was not provided.",
                        "locations": [(4, 36)],
                    },
                ],
                schema,
            )

        def missing_arg_on_directive_used_in_schema_extension():
            schema = build_schema(
                """
                directive @test(arg: String!) on OBJECT

                type Query {
                  foo: String
                }
                """
            )
            assert_sdl_errors(
                """
                extend type Query  @test
                """,
                [
                    {
                        "message": "Directive '@test' argument 'arg' of type"
                        " 'String!' is required, but it was not provided.",
                        "locations": [(2, 36)],
                    },
                ],
                schema,
            )
