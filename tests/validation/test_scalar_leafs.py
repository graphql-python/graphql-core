from graphql.validation import ScalarLeafsRule
from graphql.validation.rules.scalar_leafs import (
    no_subselection_allowed_message,
    required_subselection_message,
)

from .harness import expect_fails_rule, expect_passes_rule


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
        expect_passes_rule(
            ScalarLeafsRule,
            """
            fragment scalarSelection on Dog {
              barks
            }
            """,
        )

    def object_type_missing_selection():
        expect_fails_rule(
            ScalarLeafsRule,
            """
            query directQueryOnObjectWithoutSubFields {
              human
            }
            """,
            [missing_obj_subselection("human", "Human", 3, 15)],
        )

    def interface_type_missing_selection():
        expect_fails_rule(
            ScalarLeafsRule,
            """
            {
              human { pets }
            }
            """,
            [missing_obj_subselection("pets", "[Pet]", 3, 23)],
        )

    def valid_scalar_selection_with_args():
        expect_passes_rule(
            ScalarLeafsRule,
            """
            fragment scalarSelectionWithArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
            }
            """,
        )

    def scalar_selection_not_allowed_on_boolean():
        expect_fails_rule(
            ScalarLeafsRule,
            """
            fragment scalarSelectionsNotAllowedOnBoolean on Dog {
              barks { sinceWhen }
            }
            """,
            [no_scalar_subselection("barks", "Boolean", 3, 21)],
        )

    def scalar_selection_not_allowed_on_enum():
        expect_fails_rule(
            ScalarLeafsRule,
            """
            fragment scalarSelectionsNotAllowedOnEnum on Cat {
              furColor { inHexdec }
            }
            """,
            [no_scalar_subselection("furColor", "FurColor", 3, 24)],
        )

    def scalar_selection_not_allowed_with_args():
        expect_fails_rule(
            ScalarLeafsRule,
            """
            fragment scalarSelectionsNotAllowedWithArgs on Dog {
              doesKnowCommand(dogCommand: SIT) { sinceWhen }
            }
            """,
            [no_scalar_subselection("doesKnowCommand", "Boolean", 3, 48)],
        )

    def scalar_selection_not_allowed_with_directives():
        expect_fails_rule(
            ScalarLeafsRule,
            """
            fragment scalarSelectionsNotAllowedWithDirectives on Dog {
              name @include(if: true) { isAlsoHumanName }
            }
            """,
            [no_scalar_subselection("name", "String", 3, 39)],
        )

    def scalar_selection_not_allowed_with_directives_and_args():
        expect_fails_rule(
            ScalarLeafsRule,
            """
            fragment scalarSelectionsNotAllowedWithDirectivesAndArgs on Dog {
              doesKnowCommand(dogCommand: SIT) @include(if: true) { sinceWhen }
            }
            """,
            [no_scalar_subselection("doesKnowCommand", "Boolean", 3, 67)],
        )
