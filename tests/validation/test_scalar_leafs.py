from functools import partial

from graphql.validation import ScalarLeafsRule
from graphql.validation.rules.scalar_leafs import (
    no_subselection_allowed_message,
    required_subselection_message,
)

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, ScalarLeafsRule)

assert_valid = partial(assert_errors, errors=[])


def no_scalar_subselection(field, type_, line, column):
    return {
        "message": no_subselection_allowed_message(field, type_),
        "locations": [(line, column)],
    }


def missing_obj_subselection(field, type_, line, column):
    return {
        "message": required_subselection_message(field, type_),
        "locations": [(line, column)],
    }


def describe_validate_scalar_leafs():
    def valid_scalar_selection():
        assert_valid(
            """
            fragment scalarSelection on Dog {
              barks
            }
            """
        )

    def object_type_missing_selection():
        assert_errors(
            """
            query directQueryOnObjectWithoutSubFields {
              human
            }
            """,
            [missing_obj_subselection("human", "Human", 3, 15)],
        )

    def interface_type_missing_selection():
        assert_errors(
            """
            {
              human { pets }
            }
            """,
            [missing_obj_subselection("pets", "[Pet]", 3, 23)],
        )

    def valid_scalar_selection_with_args():
        assert_valid(
            """
            fragment scalarSelectionWithArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
            }
            """
        )

    def scalar_selection_not_allowed_on_boolean():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedOnBoolean on Dog {
              barks { sinceWhen }
            }
            """,
            [no_scalar_subselection("barks", "Boolean", 3, 21)],
        )

    def scalar_selection_not_allowed_on_enum():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedOnEnum on Cat {
              furColor { inHexdec }
            }
            """,
            [no_scalar_subselection("furColor", "FurColor", 3, 24)],
        )

    def scalar_selection_not_allowed_with_args():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedWithArgs on Dog {
              doesKnowCommand(dogCommand: SIT) { sinceWhen }
            }
            """,
            [no_scalar_subselection("doesKnowCommand", "Boolean", 3, 48)],
        )

    def scalar_selection_not_allowed_with_directives():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedWithDirectives on Dog {
              name @include(if: true) { isAlsoHumanName }
            }
            """,
            [no_scalar_subselection("name", "String", 3, 39)],
        )

    def scalar_selection_not_allowed_with_directives_and_args():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedWithDirectivesAndArgs on Dog {
              doesKnowCommand(dogCommand: SIT) @include(if: true) { sinceWhen }
            }
            """,
            [no_scalar_subselection("doesKnowCommand", "Boolean", 3, 67)],
        )
