from graphql.validation import NoUnusedVariablesRule
from graphql.validation.rules.no_unused_variables import unused_variable_message

from .harness import expect_fails_rule, expect_passes_rule


def unused_var(var_name, op_name, line, column):
    return {
        "message": unused_variable_message(var_name, op_name),
        "locations": [(line, column)],
    }


def describe_validate_no_unused_variables():
    def uses_all_variables():
        expect_passes_rule(
            NoUnusedVariablesRule,
            """
            query ($a: String, $b: String, $c: String) {
              field(a: $a, b: $b, c: $c)
            }
            """,
        )

    def uses_all_variables_deeply():
        expect_passes_rule(
            NoUnusedVariablesRule,
            """
            query Foo($a: String, $b: String, $c: String) {
              field(a: $a) {
                field(b: $b) {
                  field(c: $c)
                }
              }
            }
            """,
        )

    def uses_all_variables_deeply_in_inline_fragments():
        expect_passes_rule(
            NoUnusedVariablesRule,
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
            """,
        )

    def uses_all_variables_in_fragment():
        expect_passes_rule(
            NoUnusedVariablesRule,
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
            """,
        )

    def variable_used_by_fragment_in_multiple_operations():
        expect_passes_rule(
            NoUnusedVariablesRule,
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
            """,
        )

    def variable_used_by_recursive_fragment():
        expect_passes_rule(
            NoUnusedVariablesRule,
            """
            query Foo($a: String) {
              ...FragA
            }
            fragment FragA on Type {
              field(a: $a) {
                ...FragA
              }
            }
            """,
        )

    def variable_not_used():
        expect_fails_rule(
            NoUnusedVariablesRule,
            """
            query ($a: String, $b: String, $c: String) {
              field(a: $a, b: $b)
            }
        """,
            [unused_var("c", None, 2, 44)],
        )

    def multiple_variables_not_used():
        expect_fails_rule(
            NoUnusedVariablesRule,
            """
            query Foo($a: String, $b: String, $c: String) {
              field(b: $b)
            }
            """,
            [unused_var("a", "Foo", 2, 23), unused_var("c", "Foo", 2, 47)],
        )

    def variable_not_used_in_fragments():
        expect_fails_rule(
            NoUnusedVariablesRule,
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
            [unused_var("c", "Foo", 2, 47)],
        )

    def multiple_variables_not_used_in_fragments():
        expect_fails_rule(
            NoUnusedVariablesRule,
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
            [unused_var("a", "Foo", 2, 23), unused_var("c", "Foo", 2, 47)],
        )

    def variable_not_used_by_unreferenced_fragment():
        expect_fails_rule(
            NoUnusedVariablesRule,
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
            [unused_var("b", "Foo", 2, 23)],
        )

    def variable_not_used_by_fragment_used_by_other_operation():
        expect_fails_rule(
            NoUnusedVariablesRule,
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
            [unused_var("b", "Foo", 2, 23), unused_var("a", "Bar", 5, 23)],
        )
