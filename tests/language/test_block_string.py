from graphql.language.block_string import (
    dedent_block_string_value,
    print_block_string,
    get_block_string_indentation,
)


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

    def correctly_prints_string_with_a_first_line_indentation():
        s = join_lines("    first  ", "  line     ", "indentation", "     string")

        assert print_block_string(s) == join_lines(
            '"""', "    first  ", "  line     ", "indentation", "     string", '"""'
        )
