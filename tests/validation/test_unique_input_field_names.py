from functools import partial

from graphql.validation import UniqueInputFieldNamesRule
from graphql.validation.rules.unique_input_field_names import (
    duplicate_input_field_message,
)

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, UniqueInputFieldNamesRule)

assert_valid = partial(assert_errors, errors=[])


def duplicate_field(name, l1, c1, l2, c2):
    return {
        "message": duplicate_input_field_message(name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_unique_input_field_names():
    def input_object_with_fields():
        assert_valid(
            """
            {
              field(arg: { f: true })
            }
            """
        )

    def same_input_object_within_two_args():
        assert_valid(
            """
            {
              field(arg1: { f: true }, arg2: { f: true })
            }
            """
        )

    def multiple_input_object_fields():
        assert_valid(
            """
            {
              field(arg: { f1: "value", f2: "value", f3: "value" })
            }
            """
        )

    def allows_for_nested_input_objects_with_similar_fields():
        assert_valid(
            """
            {
              field(arg: {
                deep: {
                  deep: {
                    id: 1
                  }
                  id: 1
                }
                id: 1
              })
            }
            """
        )

    def duplicate_input_object_fields():
        assert_errors(
            """
            {
              field(arg: { f1: "value", f1: "value" })
            }
            """,
            [duplicate_field("f1", 3, 28, 3, 41)],
        )

    def many_duplicate_input_object_fields():
        assert_errors(
            """
            {
              field(arg: { f1: "value", f1: "value", f1: "value" })
            }
            """,
            [duplicate_field("f1", 3, 28, 3, 41), duplicate_field("f1", 3, 28, 3, 54)],
        )

    def nested_duplicate_input_object_fields():
        assert_errors(
            """
            {
              field(arg: { f1: {f2: "value", f2: "value" }})
            }
            """,
            [duplicate_field("f2", 3, 33, 3, 46)],
        )
