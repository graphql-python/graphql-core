from graphql.language.block_string import (
    dedent_block_string_value,
    print_block_string,
    get_block_string_indentation,
)


def join_lines(*args: str) -> str:
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
        assert get_block_string_indentation("") == 0

    def do_not_take_first_line_into_account():
        assert get_block_string_indentation("  a") == 0
        assert get_block_string_indentation(" a\n  b") == 2

    def returns_minimal_indentation_length():
        assert get_block_string_indentation("\n a\n  b") == 1
        assert get_block_string_indentation("\n  a\n b") == 1
        assert get_block_string_indentation("\n  a\n b\nc") == 0

    def count_both_tab_and_space_as_single_character():
        assert get_block_string_indentation("\n\ta\n          b") == 1
        assert get_block_string_indentation("\n\t a\n          b") == 2
        assert get_block_string_indentation("\n \t a\n          b") == 3

    def do_not_take_empty_lines_into_account():
        assert get_block_string_indentation("a\n ") == 0
        assert get_block_string_indentation("a\n\t") == 0
        assert get_block_string_indentation("a\n\n b") == 1
        assert get_block_string_indentation("a\n \n  b") == 2

    def treat_carriage_returns_like_newlines():
        assert get_block_string_indentation(" a\r  b") == 2
        assert get_block_string_indentation(" a\r\n  b") == 2
        assert get_block_string_indentation("\r  a\r b") == 1
        assert get_block_string_indentation("\r\n  a\r\n b") == 1
        assert get_block_string_indentation("\r \t a\r          b") == 3
        assert get_block_string_indentation("\r\n \t a\r\n          b") == 3
        assert get_block_string_indentation("a\r \r  b") == 2
        assert get_block_string_indentation("a\r\n \r\n  b") == 2


def describe_print_block_string():
    def do_not_escape_characters():
        s = '" \\ / \b \f \n \r \t'
        assert print_block_string(s) == f'"""\n{s}\n"""'

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
