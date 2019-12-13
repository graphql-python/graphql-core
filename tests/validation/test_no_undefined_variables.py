from functools import partial

from graphql.validation import NoUndefinedVariablesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, NoUndefinedVariablesRule)

assert_valid = partial(assert_errors, errors=[])


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
            [
                {
                    "message": "Variable '$d' is not defined by operation 'Foo'.",
                    "locations": [(3, 45), (2, 13)],
                },
            ],
        )

    def variable_not_defined_by_unnamed_query():
        assert_errors(
            """
            {
              field(a: $a)
            }
            """,
            [
                {
                    "message": "Variable '$a' is not defined.",
                    "locations": [(3, 24), (2, 13)],
                },
            ],
        )

    def multiple_variables_not_defined():
        assert_errors(
            """
            query Foo($b: String) {
              field(a: $a, b: $b, c: $c)
            }
            """,
            [
                {
                    "message": "Variable '$a' is not defined by operation 'Foo'.",
                    "locations": [(3, 24), (2, 13)],
                },
                {
                    "message": "Variable '$c' is not defined by operation 'Foo'.",
                    "locations": [(3, 38), (2, 13)],
                },
            ],
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
            [
                {
                    "message": "Variable '$a' is not defined.",
                    "locations": [(6, 24), (2, 13)],
                },
            ],
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
            [
                {
                    "message": "Variable '$c' is not defined by operation 'Foo'.",
                    "locations": [(16, 24), (2, 13)],
                },
            ],
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
            [
                {
                    "message": "Variable '$a' is not defined by operation 'Foo'.",
                    "locations": [(6, 24), (2, 13)],
                },
                {
                    "message": "Variable '$c' is not defined by operation 'Foo'.",
                    "locations": [(16, 24), (2, 13)],
                },
            ],
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
            [
                {
                    "message": "Variable '$b' is not defined by operation 'Foo'.",
                    "locations": [(9, 31), (2, 13)],
                },
                {
                    "message": "Variable '$b' is not defined by operation 'Bar'.",
                    "locations": [(9, 31), (5, 13)],
                },
            ],
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
            [
                {
                    "message": "Variable '$a' is not defined by operation 'Foo'.",
                    "locations": [(9, 24), (2, 13)],
                },
                {
                    "message": "Variable '$b' is not defined by operation 'Bar'.",
                    "locations": [(9, 31), (5, 13)],
                },
            ],
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
            [
                {
                    "message": "Variable '$a' is not defined by operation 'Foo'.",
                    "locations": [(9, 24), (2, 13)],
                },
                {
                    "message": "Variable '$b' is not defined by operation 'Bar'.",
                    "locations": [(12, 24), (5, 13)],
                },
            ],
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
                {
                    "message": "Variable '$a' is not defined by operation 'Foo'.",
                    "locations": [(9, 25), (2, 13)],
                },
                {
                    "message": "Variable '$a' is not defined by operation 'Foo'.",
                    "locations": [(11, 25), (2, 13)],
                },
                {
                    "message": "Variable '$c' is not defined by operation 'Foo'.",
                    "locations": [(14, 25), (2, 13)],
                },
                {
                    "message": "Variable '$b' is not defined by operation 'Bar'.",
                    "locations": [(9, 32), (5, 13)],
                },
                {
                    "message": "Variable '$b' is not defined by operation 'Bar'.",
                    "locations": [(11, 32), (5, 13)],
                },
                {
                    "message": "Variable '$c' is not defined by operation 'Bar'.",
                    "locations": [(14, 25), (5, 13)],
                },
            ],
        )
