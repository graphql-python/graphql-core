from typing import Optional

from pytest import mark

from graphql.error import GraphQLSyntaxError
from graphql.language import Source, Lexer, TokenKind
from graphql.language.block_string import print_block_string

from ..utils import dedent, gen_fuzz_strings


def lex_value(s: str) -> Optional[str]:
    lexer = Lexer(Source(s))
    value = lexer.advance().value
    assert lexer.advance().kind == TokenKind.EOF, "Expected EOF"
    return value


def describe_print_block_string():
    @mark.slow
    @mark.timeout(20)
    def correctly_print_random_strings():
        # Testing with length >7 is taking exponentially more time. However it is
        # highly recommended to test with increased limit if you make any change.
        for fuzz_str in gen_fuzz_strings(allowed_chars='\n\t "a\\', max_length=7):
            test_str = f'"""{fuzz_str}"""'

            try:
                test_value = lex_value(test_str)
            except (AssertionError, GraphQLSyntaxError):
                continue  # skip invalid values
            assert isinstance(test_value, str)

            printed_value = lex_value(print_block_string(test_value))

            assert test_value == printed_value, dedent(
                f"""
                Expected lex_value(print_block_string({test_value!r})
                  to equal {test_value!r}
                  but got {printed_value!r}
                """
            )

            printed_multiline_string = lex_value(
                print_block_string(test_value, " ", True)
            )

            assert test_value == printed_multiline_string, dedent(
                f"""
                Expected lex_value(print_block_string({test_value!r}, ' ', True)
                  to equal {test_value!r}
                  but got {printed_multiline_string!r}
                """
            )
