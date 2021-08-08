from graphql.language import parse, print_ast
from graphql.utilities import separate_operations

from ..utils import dedent


def separated_asts(ast):
    return {name: print_ast(node) for name, node in separate_operations(ast).items()}


def describe_separate_operations():
    def separates_one_ast_into_multiple_maintaining_document_order():
        ast = parse(
            """
            {
              ...Y
              ...X
            }

            query One {
              foo
              bar
              ...A
              ...X
            }

            fragment A on T {
              field
              ...B
            }

            fragment X on T {
              fieldX
            }

            query Two {
              ...A
              ...Y
              baz
            }

            fragment Y on T {
              fieldY
            }

            fragment B on T {
              something
            }

            """
        )

        assert separated_asts(ast) == {
            "": dedent(
                """
                {
                  ...Y
                  ...X
                }

                fragment X on T {
                  fieldX
                }

                fragment Y on T {
                  fieldY
                }
                """
            ),
            "One": dedent(
                """
                query One {
                  foo
                  bar
                  ...A
                  ...X
                }

                fragment A on T {
                  field
                  ...B
                }

                fragment X on T {
                  fieldX
                }

                fragment B on T {
                  something
                }
                """
            ),
            "Two": dedent(
                """
                fragment A on T {
                  field
                  ...B
                }

                query Two {
                  ...A
                  ...Y
                  baz
                }

                fragment Y on T {
                  fieldY
                }

                fragment B on T {
                  something
                }
                """
            ),
        }

    def survives_circular_dependencies():
        ast = parse(
            """
            query One {
              ...A
            }

            fragment A on T {
              ...B
            }

            fragment B on T {
              ...A
            }

            query Two {
              ...B
            }
            """
        )

        assert separated_asts(ast) == {
            "One": dedent(
                """
                query One {
                  ...A
                }

                fragment A on T {
                  ...B
                }

                fragment B on T {
                  ...A
                }
                """
            ),
            "Two": dedent(
                """
                fragment A on T {
                  ...B
                }

                fragment B on T {
                  ...A
                }

                query Two {
                  ...B
                }
                """
            ),
        }

    def distinguishes_query_and_fragment_names():
        ast = parse(
            """
            {
              ...NameClash
            }

            fragment NameClash on T {
              oneField
            }

            query NameClash {
              ...ShouldBeSkippedInFirstQuery
            }

            fragment ShouldBeSkippedInFirstQuery on T {
              twoField
            }
            """
        )

        assert separated_asts(ast) == {
            "": dedent(
                """
                {
                  ...NameClash
                }

                fragment NameClash on T {
                  oneField
                }
                """
            ),
            "NameClash": dedent(
                """
                query NameClash {
                  ...ShouldBeSkippedInFirstQuery
                }

                fragment ShouldBeSkippedInFirstQuery on T {
                  twoField
                }
                """
            ),
        }

    def handles_unknown_fragments():
        ast = parse(
            """
            {
              ...Unknown
              ...Known
            }

            fragment Known on T {
              someField
            }
            """
        )

        assert separated_asts(ast) == {
            "": dedent(
                """
                {
                  ...Unknown
                  ...Known
                }

                fragment Known on T {
                  someField
                }
                """
            )
        }
