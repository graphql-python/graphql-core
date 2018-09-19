from graphql.language import parse, print_ast
from graphql.pyutils import dedent
from graphql.utilities import separate_operations


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

        separated_asts = separate_operations(ast)

        assert list(separated_asts) == ["", "One", "Two"]

        assert print_ast(separated_asts[""]) == dedent(
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
        )

        assert print_ast(separated_asts["One"]) == dedent(
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
        )

        assert print_ast(separated_asts["Two"]) == dedent(
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
        )

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

        separated_asts = separate_operations(ast)

        assert list(separated_asts) == ["One", "Two"]

        assert print_ast(separated_asts["One"]) == dedent(
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
        )

        assert print_ast(separated_asts["Two"]) == dedent(
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
        )
