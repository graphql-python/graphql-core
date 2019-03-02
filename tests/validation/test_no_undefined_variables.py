from functools import partial

from graphql.validation import NoUndefinedVariablesRule
from graphql.validation.rules.no_undefined_variables import undefined_var_message

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, NoUndefinedVariablesRule)

assert_valid = partial(assert_errors, errors=[])


def undef_var(var_name, l1, c1, op_name, l2, c2):
    return {
        "message": undefined_var_message(var_name, op_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_no_undefined_variables():
    def all_variables_defined():
        assert_valid(
            """
            query Foo($a: String, $b: String, $c: String) {
              field(a: $a, b: $b, c: $c)
            }
            """
        )

    def all_variables_deeply_defined():
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

    def all_variables_deeply_in_inline_fragments_defined():
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

    def all_variables_in_fragments_deeply_defined():
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

    def variable_within_single_fragment_defined_in_multiple_operations():
        assert_valid(
            """
            query Foo($a: String) {
              ...FragA
            }
            query Bar($a: String) {
              ...FragA
            }
            fragment FragA on Type {
              field(a: $a)
            }
            """
        )

    def variable_within_fragments_defined_in_operations():
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

    def variable_within_recursive_fragment_defined():
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

    def variable_not_defined():
        assert_errors(
            """
            query Foo($a: String, $b: String, $c: String) {
              field(a: $a, b: $b, c: $c, d: $d)
            }
            """,
            [undef_var("d", 3, 45, "Foo", 2, 13)],
        )

    def variable_not_defined_by_unnamed_query():
        assert_errors(
            """
            {
              field(a: $a)
            }
            """,
            [undef_var("a", 3, 24, "", 2, 13)],
        )

    def multiple_variables_not_defined():
        assert_errors(
            """
            query Foo($b: String) {
              field(a: $a, b: $b, c: $c)
            }
            """,
            [undef_var("a", 3, 24, "Foo", 2, 13), undef_var("c", 3, 38, "Foo", 2, 13)],
        )

    def variable_in_fragment_not_defined_by_unnamed_query():
        assert_errors(
            """
            {
              ...FragA
            }
            fragment FragA on Type {
              field(a: $a)
            }
            """,
            [undef_var("a", 6, 24, "", 2, 13)],
        )

    def variable_in_fragment_not_defined_by_operation():
        assert_errors(
            """
            query Foo($a: String, $b: String) {
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
            [undef_var("c", 16, 24, "Foo", 2, 13)],
        )

    def multiple_variables_in_fragments_not_defined():
        assert_errors(
            """
            query Foo($b: String) {
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
            [undef_var("a", 6, 24, "Foo", 2, 13), undef_var("c", 16, 24, "Foo", 2, 13)],
        )

    def single_variable_in_fragment_not_defined_by_multiple_operations():
        assert_errors(
            """
            query Foo($a: String) {
              ...FragAB
            }
            query Bar($a: String) {
              ...FragAB
            }
            fragment FragAB on Type {
              field(a: $a, b: $b)
            }
            """,
            [undef_var("b", 9, 31, "Foo", 2, 13), undef_var("b", 9, 31, "Bar", 5, 13)],
        )

    def variables_in_fragment_not_defined_by_multiple_operations():
        assert_errors(
            """
            query Foo($b: String) {
              ...FragAB
            }
            query Bar($a: String) {
              ...FragAB
            }
            fragment FragAB on Type {
              field(a: $a, b: $b)
            }
            """,
            [undef_var("a", 9, 24, "Foo", 2, 13), undef_var("b", 9, 31, "Bar", 5, 13)],
        )

    def variable_in_fragment_used_by_other_operation():
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
            [undef_var("a", 9, 24, "Foo", 2, 13), undef_var("b", 12, 24, "Bar", 5, 13)],
        )

    def multiple_undefined_variables_produce_multiple_errors():
        assert_errors(
            """
            query Foo($b: String) {
              ...FragAB
            }
            query Bar($a: String) {
              ...FragAB
            }
            fragment FragAB on Type {
              field1(a: $a, b: $b)
              ...FragC
              field3(a: $a, b: $b)
            }
            fragment FragC on Type {
              field2(c: $c)
            }
            """,
            [
                undef_var("a", 9, 25, "Foo", 2, 13),
                undef_var("a", 11, 25, "Foo", 2, 13),
                undef_var("c", 14, 25, "Foo", 2, 13),
                undef_var("b", 9, 32, "Bar", 5, 13),
                undef_var("b", 11, 32, "Bar", 5, 13),
                undef_var("c", 14, 25, "Bar", 5, 13),
            ],
        )
