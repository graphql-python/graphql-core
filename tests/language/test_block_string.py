from typing import Optional

from graphql.error import GraphQLSyntaxError
from graphql.language import Source, Lexer, TokenKind
from graphql.language.block_string import (
    dedent_block_string_value,
    print_block_string,
    get_block_string_indentation,
)

from ..utils import dedent, gen_fuzz_strings


def join_lines(*args):
    return "\n".join(args)


def describe_dedent_block_string_value():
    def removes_uniform_indentation_from_a_string():
        raw_value = join_lines(
            "", "    Hello,", "      World!", "", "    Yours,", "      GraphQL."
        )
        assert dedent_block_string_value(raw_value) == join_lines(
            "Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def removes_empty_leading_and_trailing_lines():
        raw_value = join_lines(
            "",
            "",
            "    Hello,",
            "      World!",
            "",
            "    Yours,",
            "      GraphQL.",
            "",
            "",
        )
        assert dedent_block_string_value(raw_value) == join_lines(
            "Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def removes_blank_leading_and_trailing_lines():
        raw_value = join_lines(
            "  ",
            "        ",
            "    Hello,",
            "      World!",
            "",
            "    Yours,",
            "      GraphQL.",
            "        ",
            "  ",
        )
        assert dedent_block_string_value(raw_value) == join_lines(
            "Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def retains_indentation_from_first_line():
        raw_value = join_lines(
            "    Hello,", "      World!", "", "    Yours,", "      GraphQL."
        )
        assert dedent_block_string_value(raw_value) == join_lines(
            "    Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def does_not_alter_trailing_spaces():
        raw_value = join_lines(
            "               ",
            "    Hello,     ",
            "      World!   ",
            "               ",
            "    Yours,     ",
            "      GraphQL. ",
            "               ",
        )
        assert dedent_block_string_value(raw_value) == join_lines(
            "Hello,     ", "  World!   ", "           ", "Yours,     ", "  GraphQL. "
        )


def describe_get_block_string_indentation():
    def returns_zero_for_an_empty_list():
        assert get_block_string_indentation([]) == 0

    def do_not_take_first_line_into_account():
        assert get_block_string_indentation(["  a"]) == 0
        assert get_block_string_indentation([" a", "  b"]) == 2

    def returns_minimal_indentation_length():
        assert get_block_string_indentation(["", " a", "  b"]) == 1
        assert get_block_string_indentation(["", "  a", " b"]) == 1
        assert get_block_string_indentation(["", "  a", " b", "c"]) == 0

    def count_both_tab_and_space_as_single_character():
        assert get_block_string_indentation(["", "\ta", "          b"]) == 1
        assert get_block_string_indentation(["", "\t a", "          b"]) == 2
        assert get_block_string_indentation(["", " \t a", "          b"]) == 3

    def do_not_take_empty_lines_into_account():
        assert get_block_string_indentation((["a", "\t"])) == 0
        assert get_block_string_indentation((["a", " "])) == 0
        assert get_block_string_indentation((["a", " ", "  b"])) == 2
        assert get_block_string_indentation((["a", " ", "  b"])) == 2
        assert get_block_string_indentation((["a", "", " b"])) == 1


def describe_print_block_string():
    def by_default_print_block_strings_as_single_line():
        s = "one liner"
        assert print_block_string(s) == '"""one liner"""'
        assert print_block_string(s, "", True) == '"""\none liner\n"""'

    def correctly_prints_single_line_with_leading_space():
        s = "    space-led string"
        assert print_block_string(s) == '"""    space-led string"""'
        assert print_block_string(s, "", True) == '"""    space-led string\n"""'

    def correctly_prints_single_line_with_leading_space_and_quotation():
        s = '    space-led value "quoted string"'

        assert print_block_string(s) == '"""    space-led value "quoted string"\n"""'

        assert (
            print_block_string(s, "", True)
            == '"""    space-led value "quoted string"\n"""'
        )

    def correctly_prints_single_line_with_trailing_backslash():
        s = "backslash \\"

        assert print_block_string(s) == '"""\nbackslash \\\n"""'
        assert print_block_string(s, "", True) == '"""\nbackslash \\\n"""'

    def correctly_prints_string_with_a_first_line_indentation():
        s = join_lines("    first  ", "  line     ", "indentation", "     string")

        assert print_block_string(s) == join_lines(
            '"""', "    first  ", "  line     ", "indentation", "     string", '"""'
        )

    def correctly_print_random_strings():
        def lex_value(s: str) -> Optional[str]:
            lexer = Lexer(Source(s))
            value = lexer.advance().value
            assert lexer.advance().kind == TokenKind.EOF, "Expected EOF"
            return value

        # Testing with length >5 is taking exponentially more time. However it is
        # highly recommended to test with increased limit if you make any change.
        for fuzz_str in gen_fuzz_strings(allowed_chars='\n\t "a\\', max_length=5):
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
