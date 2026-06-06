from functools import partial

from graphql.language import (
    DocumentNode,
    FieldNode,
    NameNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)
from graphql.validation import ScalarLeafsRule
from graphql.validation.validate import validate

from .harness import assert_validation_errors, test_schema

assert_errors = partial(assert_validation_errors, ScalarLeafsRule)

assert_valid = partial(assert_errors, errors=[])


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
            [
                {
                    "message": "Field 'human' of type 'Human'"
                    " must have a selection of subfields."
                    " Did you mean 'human { ... }'?",
                    "locations": [(3, 15)],
                },
            ],
        )

    def interface_type_missing_selection():
        assert_errors(
            """
            {
              human { pets }
            }
            """,
            [
                {
                    "message": "Field 'pets' of type '[Pet]'"
                    " must have a selection of subfields."
                    " Did you mean 'pets { ... }'?",
                    "locations": [(3, 23)],
                },
            ],
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
            [
                {
                    "message": "Field 'barks' must not have a selection"
                    " since type 'Boolean' has no subfields.",
                    "locations": [(3, 21)],
                },
            ],
        )

    def scalar_selection_not_allowed_on_enum():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedOnEnum on Cat {
              furColor { inHexDec }
            }
            """,
            [
                {
                    "message": "Field 'furColor' must not have a selection"
                    " since type 'FurColor' has no subfields.",
                    "locations": [(3, 24)],
                },
            ],
        )

    def scalar_selection_not_allowed_with_args():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedWithArgs on Dog {
              doesKnowCommand(dogCommand: SIT) { sinceWhen }
            }
            """,
            [
                {
                    "message": "Field 'doesKnowCommand' must not have a selection"
                    " since type 'Boolean' has no subfields.",
                    "locations": [(3, 48)],
                },
            ],
        )

    def scalar_selection_not_allowed_with_directives():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedWithDirectives on Dog {
              name @include(if: true) { isAlsoHumanName }
            }
            """,
            [
                {
                    "message": "Field 'name' must not have a selection"
                    " since type 'String' has no subfields.",
                    "locations": [(3, 39)],
                },
            ],
        )

    def scalar_selection_not_allowed_with_directives_and_args():
        assert_errors(
            """
            fragment scalarSelectionsNotAllowedWithDirectivesAndArgs on Dog {
              doesKnowCommand(dogCommand: SIT) @include(if: true) { sinceWhen }
            }
            """,
            [
                {
                    "message": "Field 'doesKnowCommand' must not have a selection"
                    " since type 'Boolean' has no subfields.",
                    "locations": [(3, 67)],
                },
            ],
        )

    def object_type_having_only_one_selection():
        # We can't leverage assert_errors since it doesn't support passing in the
        # document node directly. We have to do this because this is technically
        # an invalid document.
        doc = DocumentNode(
            definitions=(
                OperationDefinitionNode(
                    operation=OperationType.QUERY,
                    selection_set=SelectionSetNode(
                        selections=(
                            FieldNode(
                                name=NameNode(value="human"),
                                selection_set=SelectionSetNode(selections=()),
                            ),
                        ),
                    ),
                ),
            ),
        )
        errors = validate(test_schema, doc, [ScalarLeafsRule])
        assert errors == [
            {
                "message": "Field 'human' of type 'Human'"
                " must have at least one field selected.",
            },
        ]
