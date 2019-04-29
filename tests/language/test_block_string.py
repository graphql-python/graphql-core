from graphql.language.block_string import dedent_block_string_value, print_block_string


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


def describe_print_block_string():
    def describe_single_line():
        def simple():
            assert print_block_string("single line") == '"""single line"""'

        def with_leading_whitespace():
            assert print_block_string("  single line") == '"""  single line"""'

        def with_indentation():
            assert (
                print_block_string("single line", indentation=" ")
                == '"""single line"""'
            )

        def with_indentation_and_leading_whitespace():
            assert (
                print_block_string(" single line", indentation="  ")
                == '""" single line"""'
            )

        def with_trailing_quote():
            assert print_block_string('single "line"') == '"""\nsingle "line"\n"""'

        def prefer_multiple_lines():
            assert (
                print_block_string("single line", prefer_multiple_lines=True)
                == '"""\nsingle line\n"""'
            )

    def describe_multiple_lines():
        def simple():
            assert print_block_string("multiple\nlines") == '"""\nmultiple\nlines\n"""'

        def with_leading_whitespace():
            assert (
                print_block_string(" multiple\nlines") == '"""\n multiple\nlines\n"""'
            )

        def with_indentation():
            assert (
                print_block_string("multiple\nlines", indentation="  ")
                == '"""\n  multiple\n  lines\n"""'
            )

        def with_indentation_and_leading_whitespace():
            assert (
                print_block_string(" multiple\nlines", indentation="  ")
                == '"""\n   multiple\n  lines\n"""'
            )

        def with_trailing_quote():
            assert (
                print_block_string('multiple\n"line"') == '"""\nmultiple\n"line"\n"""'
            )

        def do_not_prefer_multiple_lines():
            assert (
                print_block_string("multiple\nlines", prefer_multiple_lines=False)
                == '"""\nmultiple\nlines\n"""'
            )
