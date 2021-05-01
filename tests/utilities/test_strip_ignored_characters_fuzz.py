from typing import Optional

from pytest import mark

from graphql.error import GraphQLSyntaxError
from graphql.language import Lexer, Source, TokenKind
from graphql.utilities import strip_ignored_characters

from ..utils import dedent, gen_fuzz_strings


def lex_value(s: str) -> Optional[str]:
    lexer = Lexer(Source(s))
    value = lexer.advance().value
    assert lexer.advance().kind == TokenKind.EOF, "Expected EOF"
    return value


def describe_strip_ignored_characters():
    @mark.slow
    @mark.timeout(20)
    def strips_ignored_characters_inside_random_block_strings():
        # Testing with length >7 is taking exponentially more time. However it is
        # highly recommended to test with increased limit if you make any change.
        for fuzz_str in gen_fuzz_strings(allowed_chars='\n\t "a\\', max_length=7):
            test_str = f'"""{fuzz_str}"""'

            try:
                test_value = lex_value(test_str)
            except (AssertionError, GraphQLSyntaxError):
                continue  # skip invalid values

            stripped_value = lex_value(strip_ignored_characters(test_str))

            assert test_value == stripped_value, dedent(
                f"""
                Expected lexValue(stripIgnoredCharacters({test_str!r})
                  to equal {test_value!r}
                  but got {stripped_value!r}
                """
            )
