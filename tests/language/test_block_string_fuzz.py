from pytest import mark

from graphql.language import Source, Lexer, TokenKind
from graphql.language.block_string import (
    print_block_string,
    is_printable_as_block_string,
)

from ..utils import dedent, gen_fuzz_strings


def lex_value(s: str) -> str:
    lexer = Lexer(Source(s))
    value = lexer.advance().value
    assert isinstance(value, str)
    assert lexer.advance().kind == TokenKind.EOF, "Expected EOF"
    return value


def assert_printable_block_string(test_value: str, minimize: bool = False) -> None:
    block_string = print_block_string(test_value, minimize=minimize)
    printed_value = lex_value(block_string)
    assert test_value == printed_value, dedent(
        f"""
        Expected lexValue({block_string!r})
          to equal {test_value!r}
          but got  {printed_value!r}
        """
    )


def assert_non_printable_block_string(test_value: str) -> None:
    block_string = print_block_string(test_value)
    printed_value = lex_value(block_string)
    assert test_value != printed_value, dedent(
        f"""
        Expected lexValue({block_string!r})
          to not equal {test_value!r}
        """
    )


def describe_print_block_string():
    @mark.slow
    @mark.timeout(20)
    def correctly_print_random_strings():
        # Testing with length >7 is taking exponentially more time. However, it is
        # highly recommended testing with increased limit if you make any change.
        for fuzz_str in gen_fuzz_strings(allowed_chars='\n\t "a\\', max_length=7):
            if not is_printable_as_block_string(fuzz_str):
                assert_non_printable_block_string(fuzz_str)
                continue

            assert_printable_block_string(fuzz_str)
            assert_printable_block_string(fuzz_str, minimize=True)
