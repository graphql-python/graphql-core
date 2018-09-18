from graphql.language.block_string_value import block_string_value


def join(*args):
    return "\n".join(args)


def describe_block_string_value():
    def removes_uniform_indentation_from_a_string():
        raw_value = join(
            "", "    Hello,", "      World!", "", "    Yours,", "      GraphQL."
        )
        assert block_string_value(raw_value) == join(
            "Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def removes_empty_leading_and_trailing_lines():
        raw_value = join(
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
        assert block_string_value(raw_value) == join(
            "Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def removes_blank_leading_and_trailing_lines():
        raw_value = join(
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
        assert block_string_value(raw_value) == join(
            "Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def retains_indentation_from_first_line():
        raw_value = join(
            "    Hello,", "      World!", "", "    Yours,", "      GraphQL."
        )
        assert block_string_value(raw_value) == join(
            "    Hello,", "  World!", "", "Yours,", "  GraphQL."
        )

    def does_not_alter_trailing_spaces():
        raw_value = join(
            "               ",
            "    Hello,     ",
            "      World!   ",
            "               ",
            "    Yours,     ",
            "      GraphQL. ",
            "               ",
        )
        assert block_string_value(raw_value) == join(
            "Hello,     ", "  World!   ", "           ", "Yours,     ", "  GraphQL. "
        )
