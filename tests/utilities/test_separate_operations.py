from graphql.language import parse, print_ast
from graphql.utilities import separate_operations

from ..utils import dedent


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

        separated_asts = {
            name: print_ast(node) for name, node in separate_operations(ast).items()
        }

        assert list(separated_asts) == ["", "One", "Two"]

        assert separated_asts == {
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

        separated_asts = {
            name: print_ast(node) for name, node in separate_operations(ast).items()
        }

        assert list(separated_asts) == ["One", "Two"]

        assert separated_asts == {
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
