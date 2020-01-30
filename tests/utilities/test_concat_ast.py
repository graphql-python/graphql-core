from graphql.language import parse, print_ast, Source
from graphql.pyutils import dedent
from graphql.utilities import concat_ast


def describe_concat_ast():
    def concatenates_two_asts_together():
        source_a = Source(
            """
            { a, b, ... Frag }
            """
        )

        source_b = Source(
            """
            fragment Frag on T {
                c
            }
            """
        )

        ast_a = parse(source_a)
        ast_b = parse(source_b)
        ast_c = concat_ast([ast_a, ast_b])

        assert print_ast(ast_c) == dedent(
            """
            {
              a
              b
              ...Frag
            }

            fragment Frag on T {
              c
            }
            """
        )
