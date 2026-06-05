from functools import partial

from graphql.validation import NoUnusedVariablesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, NoUnusedVariablesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_no_unused_variables():
    def fragment_defined_arguments_are_not_unused_variables():
        assert_valid(
            """
            query Foo {
              ...FragA
            }
            fragment FragA($a: String) on Type {
              field1(a: $a)
            }
            """
        )

    def defined_variables_used_as_fragment_arguments_are_not_unused():
        assert_valid(
            """
            query Foo($b: String) {
              ...FragA(a: $b)
            }
            fragment FragA($a: String) on Type {
              field1(a: $a)
            }
            """
        )

    def unused_fragment_variables_are_reported():
        assert_errors(
            """
            query Foo {
              ...FragA(a: "value")
            }
            fragment FragA($a: String) on Type {
              field1
            }
            """,
            [
                {
                    "message": "Variable '$a' is never used in fragment 'FragA'.",
                    "locations": [(5, 28)],
                },
            ],
        )

    def uses_all_variables():
        assert_valid(
            """
            query ($a: String, $b: String, $c: String) {
              field(a: $a, b: $b, c: $c)
            }
            """
        )

    def uses_all_variables_deeply():
        assert_valid(
            """
            query Foo($a: String, $b: String, $c: String) {
              field(a: $a) {
                field(b: $b) {
                  field(c: $c)
                }
              }
            }
            """
        )

    def uses_all_variables_deeply_in_inline_fragments():
        assert_valid(
            """
            query Foo($a: String, $b: String, $c: String) {
              ... on Type {
                field(a: $a) {
                  field(b: $b) {
                    ... on Type {
                      field(c: $c)
                    }
                  }
                }
              }
            }
            """
        )

    def uses_all_variables_in_fragment():
        assert_valid(
            """
            query Foo($a: String, $b: String, $c: String) {
              ...FragA
            }
            fragment FragA on Type {
              field(a: $a) {
                ...FragB
              }
            }
            fragment FragB on Type {
              field(b: $b) {
                ...FragC
              }
            }
            fragment FragC on Type {
              field(c: $c)
            }
            """
        )

    def variable_used_by_fragment_in_multiple_operations():
        assert_valid(
            """
            query Foo($a: String) {
              ...FragA
            }
            query Bar($b: String) {
              ...FragB
            }
            fragment FragA on Type {
              field(a: $a)
            }
            fragment FragB on Type {
              field(b: $b)
            }
            """
        )

    def variable_used_by_recursive_fragment():
        assert_valid(
            """
            query Foo($a: String) {
              ...FragA
            }
            fragment FragA on Type {
              field(a: $a) {
                ...FragA
              }
            }
            """
        )

    def variable_not_used():
        assert_errors(
            """
            query ($a: String, $b: String, $c: String) {
              field(a: $a, b: $b)
            }
            """,
            [{"message": "Variable '$c' is never used.", "locations": [(2, 44)]}],
        )

    def multiple_variables_not_used():
        assert_errors(
            """
            query Foo($a: String, $b: String, $c: String) {
              field(b: $b)
            }
            """,
            [
                {
                    "message": "Variable '$a' is never used in operation 'Foo'.",
                    "locations": [(2, 23)],
                },
                {
                    "message": "Variable '$c' is never used in operation 'Foo'.",
                    "locations": [(2, 47)],
                },
            ],
        )

    def variable_not_used_in_fragments():
        assert_errors(
            """
            query Foo($a: String, $b: String, $c: String) {
              ...FragA
            }
            fragment FragA on Type {
              field(a: $a) {
                ...FragB
              }
            }
            fragment FragB on Type {
              field(b: $b) {
                ...FragC
              }
            }
            fragment FragC on Type {
              field
            }
            """,
            [
                {
                    "message": "Variable '$c' is never used in operation 'Foo'.",
                    "locations": [(2, 47)],
                },
            ],
        )

    def multiple_variables_not_used_in_fragments():
        assert_errors(
            """
            query Foo($a: String, $b: String, $c: String) {
              ...FragA
            }
            fragment FragA on Type {
              field {
                ...FragB
              }
            }
            fragment FragB on Type {
              field(b: $b) {
                ...FragC
              }
            }
            fragment FragC on Type {
              field
            }
            """,
            [
                {
                    "message": "Variable '$a' is never used in operation 'Foo'.",
                    "locations": [(2, 23)],
                },
                {
                    "message": "Variable '$c' is never used in operation 'Foo'.",
                    "locations": [(2, 47)],
                },
            ],
        )

    def variable_not_used_by_unreferenced_fragment():
        assert_errors(
            """
            query Foo($b: String) {
              ...FragA
            }
            fragment FragA on Type {
              field(a: $a)
            }
            fragment FragB on Type {
              field(b: $b)
            }
            """,
            [
                {
                    "message": "Variable '$b' is never used in operation 'Foo'.",
                    "locations": [(2, 23)],
                },
            ],
        )

    def variable_not_used_by_fragment_used_by_other_operation():
        assert_errors(
            """
            query Foo($b: String) {
              ...FragA
            }
            query Bar($a: String) {
              ...FragB
            }
            fragment FragA on Type {
              field(a: $a)
            }
            fragment FragB on Type {
              field(b: $b)
            }
            """,
            [
                {
                    "message": "Variable '$b' is never used in operation 'Foo'.",
                    "locations": [(2, 23)],
                },
                {
                    "message": "Variable '$a' is never used in operation 'Bar'.",
                    "locations": [(5, 23)],
                },
            ],
        )
