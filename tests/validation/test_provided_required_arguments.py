from functools import partial

from graphql.utilities import build_schema
from graphql.validation import ProvidedRequiredArgumentsRule
from graphql.validation.rules.provided_required_arguments import (
    ProvidedRequiredArgumentsOnDirectivesRule,
    missing_field_arg_message,
    missing_directive_arg_message,
)

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, ProvidedRequiredArgumentsRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(
    assert_sdl_validation_errors, ProvidedRequiredArgumentsOnDirectivesRule
)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def missing_field_arg(field_name, arg_name, type_name, line, column):
    return {
        "message": missing_field_arg_message(field_name, arg_name, type_name),
        "locations": [(line, column)],
    }


def missing_directive_arg(directive_name, arg_name, type_name, line, column):
    return {
        "message": missing_directive_arg_message(directive_name, arg_name, type_name),
        "locations": [(line, column)],
    }


def describe_validate_provided_required_arguments():
    def ignores_unknown_arguments():
        assert_valid(
            """
            {
              dog {
                isHousetrained(unknownArgument: true)
              }
            }"""
        )

    def describe_valid_non_nullable_value():
        def arg_on_optional_arg():
            assert_valid(
                """
                {
                  dog {
                    isHousetrained(atOtherHomes: true)
                  }
                }"""
            )

        def no_arg_on_optional_arg():
            assert_valid(
                """
                {
                  dog {
                    isHousetrained
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

        def multiple_reqs_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4)
                  }
                }
                """
            )

        def multiple_reqs_and_one_opt_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5)
                  }
                }
                """
            )

        def all_reqs_and_opts_on_mixed_list():
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
                [missing_field_arg("multipleReqs", "req1", "Int!", 4, 21)],
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
                    missing_field_arg("multipleReqs", "req1", "Int!", 4, 21),
                    missing_field_arg("multipleReqs", "req2", "Int!", 4, 21),
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
                [missing_field_arg("multipleReqs", "req2", "Int!", 4, 21)],
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
                    missing_directive_arg("include", "if", "Boolean!", 3, 23),
                    missing_directive_arg("skip", "if", "Boolean!", 4, 26),
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
                [missing_directive_arg("test", "arg", "String!", 3, 31)],
            )

        def missing_arg_on_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @include
                }
                """,
                [missing_directive_arg("include", "if", "Boolean!", 3, 31)],
            )

        def missing_arg_on_overridden_standard_directive():
            assert_sdl_errors(
                """
                type Query {
                  foo: String @deprecated
                }
                directive @deprecated(reason: String!) on FIELD
                """,
                [missing_directive_arg("deprecated", "reason", "String!", 3, 31)],
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
                [missing_directive_arg("test", "arg", "String!", 4, 36)],
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
                [missing_directive_arg("test", "arg", "String!", 2, 36)],
                schema,
            )
