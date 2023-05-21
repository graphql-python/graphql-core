from functools import partial

from graphql.validation import StreamDirectiveOnListField

from .harness import assert_validation_errors


assert_errors = partial(assert_validation_errors, StreamDirectiveOnListField)

assert_valid = partial(assert_errors, errors=[])


def describe_stream_directive_on_list_field():
    def stream_on_list_field():
        assert_valid(
            """
            fragment objectFieldSelection on Human {
              pets @stream(initialCount: 0) {
                name
              }
            }
            """
        )

    def stream_on_non_null_list_field():
        assert_valid(
            """
            fragment objectFieldSelection on Human {
              relatives @stream(initialCount: 0) {
                name
              }
            }
            """
        )

    def does_not_validate_other_directives_on_list_fields():
        assert_valid(
            """
            fragment objectFieldSelection on Human {
              pets @include(if: true) {
                name
              }
            }
            """
        )

    def does_not_validate_other_directives_on_non_list_fields():
        assert_valid(
            """
            fragment objectFieldSelection on Human {
              pets {
                name @include(if: true)
              }
            }
            """
        )

    def does_not_validate_misplaced_stream_directives():
        assert_valid(
            """
            fragment objectFieldSelection on Human {
              ... @stream(initialCount: 0) {
                name
              }
            }
            """
        )

    def reports_errors_when_stream_is_used_on_non_list_field():
        assert_errors(
            """
            fragment objectFieldSelection on Human {
              name @stream(initialCount: 0)
            }
            """,
            [
                {
                    "message": "Stream directive cannot be used"
                    " on non-list field 'name' on type 'Human'.",
                    "locations": [(3, 20)],
                },
            ],
        )
