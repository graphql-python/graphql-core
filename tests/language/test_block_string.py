from typing import cast, Collection, Optional

from graphql.language.block_string import (
    is_printable_as_block_string,
    dedent_block_string_lines,
    print_block_string,
)


def join_lines(*args: str) -> str:
    return "\n".join(args)


def describe_dedent_block_string_lines():
    def _assert_dedent(lines: Collection[str], expected: Collection[str]) -> None:
        assert dedent_block_string_lines(lines) == expected

    def handles_empty_string():
        _assert_dedent([""], [])

    def does_not_dedent_first_line():
        _assert_dedent(["  a"], ["  a"])
        _assert_dedent([" a", "  b"], [" a", "b"])

    def removes_minimal_indentation_length():
        _assert_dedent(["", " a", "  b"], ["a", " b"])
        _assert_dedent(["", "  a", " b"], [" a", "b"])
        _assert_dedent(["", "  a", " b", "c"], ["  a", " b", "c"])

    def dedent_both_tab_and_space_as_single_character():
        _assert_dedent(["", "\ta", "          b"], ["a", "         b"])
        _assert_dedent(["", "\t a", "          b"], ["a", "        b"])
        _assert_dedent(["", " \t a", "          b"], ["a", "       b"])

    def removes_uniform_indentation_from_a_string():
        lines = ["", "    Hello,", "      World!", "", "    Yours,", "      GraphQL."]
        _assert_dedent(lines, ["Hello,", "  World!", "", "Yours,", "  GraphQL."])

    def removes_empty_leading_and_trailing_lines():
        lines = [
            "",
            "",
            "    Hello,",
            "      World!",
            "",
            "    Yours,",
            "      GraphQL.",
            "",
            "",
        ]
        _assert_dedent(lines, ["Hello,", "  World!", "", "Yours,", "  GraphQL."])

    def removes_blank_leading_and_trailing_lines():
        lines = [
            "  ",
            "        ",
            "    Hello,",
            "      World!",
            "",
            "    Yours,",
            "      GraphQL.",
            "        ",
            "  ",
        ]
        _assert_dedent(lines, ["Hello,", "  World!", "", "Yours,", "  GraphQL."])

    def retains_indentation_from_first_line():
        lines = ["    Hello,", "      World!", "", "    Yours,", "      GraphQL."]
        _assert_dedent(lines, ["    Hello,", "  World!", "", "Yours,", "  GraphQL."])

    def does_not_alter_trailing_spaces():
        lines = [
            "               ",
            "    Hello,     ",
            "      World!   ",
            "               ",
            "    Yours,     ",
            "      GraphQL. ",
            "               ",
        ]
        _assert_dedent(
            lines,
            [
                "Hello,     ",
                "  World!   ",
                "           ",
                "Yours,     ",
                "  GraphQL. ",
            ],
        )


def describe_is_printable_as_block_string():
    def _assert_printable(s: str) -> None:
        assert is_printable_as_block_string(s) is True, s

    def _assert_non_printable(s: str) -> None:
        assert is_printable_as_block_string(s) is False, s

    def accepts_valid_strings():
        _assert_printable("")
        _assert_printable(" a")
        _assert_printable('\t"\n"')
        _assert_non_printable('\t"\n \n\t"')

    def rejects_strings_with_only_whitespace():
        _assert_non_printable(" ")
        _assert_non_printable("\t")
        _assert_non_printable("\t ")
        _assert_non_printable(" \t")

    def rejects_strings_with_non_printable_characters():
        _assert_non_printable("\x00")
        _assert_non_printable("a\x00b")

    def rejects_strings_with_only_empty_lines():
        _assert_non_printable("\n")
        _assert_non_printable("\n\n")
        _assert_non_printable("\n\n\n")
        _assert_non_printable(" \n  \n")
        _assert_non_printable("\t\n\t\t\n")

    def rejects_strings_with_carriage_return():
        _assert_non_printable("\r")
        _assert_non_printable("\n\r")
        _assert_non_printable("\r\n")
        _assert_non_printable("a\rb")

    def rejects_strings_with_leading_empty_lines():
        _assert_non_printable("\na")
        _assert_non_printable(" \na")
        _assert_non_printable("\t\na")
        _assert_non_printable("\n\na")

    def rejects_strings_with_trailing_empty_lines():
        _assert_non_printable("a\n")
        _assert_non_printable("a\n ")
        _assert_non_printable("a\n\t")
        _assert_non_printable("a\n\n")

    def can_check_lazy_stings():
        class LazyString:
            def __init__(self, string: str) -> None:
                self.string = string

            def __str__(self) -> str:
                return self.string

        _assert_printable(cast(str, LazyString("")))
        _assert_non_printable(cast(str, LazyString(" ")))


def describe_print_block_string():
    def _assert_block_string(
        s: str, readable: str, minimize: Optional[str] = None
    ) -> None:
        assert print_block_string(s) == readable
        assert print_block_string(s, minimize=True) == minimize or readable

    def does_not_escape_characters():
        s = '" \\ / \b \f \n \r \t'
        _assert_block_string(s, f'"""\n{s}\n"""', f'"""\n{s}"""')

    def by_default_print_block_strings_as_single_line():
        s = "one liner"
        _assert_block_string(s, '"""one liner"""')

    def by_default_print_block_strings_ending_with_triple_quotation_as_multi_line():
        s = 'triple quotation """'
        _assert_block_string(
            s, '"""\ntriple quotation \\"""\n"""', '"""triple quotation \\""""""'
        )

    def correctly_prints_single_line_with_leading_space():
        s = "    space-led string"
        _assert_block_string(s, '"""    space-led string"""')

    def correctly_prints_single_line_with_leading_space_and_trailing_quotation():
        s = '    space-led value "quoted string"'
        _assert_block_string(s, '"""    space-led value "quoted string"\n"""')

    def correctly_prints_single_line_with_trailing_backslash():
        s = "backslash \\"
        _assert_block_string(s, '"""\nbackslash \\\n"""', '"""\nbackslash \\\n"""')

    def correctly_prints_multi_line_with_internal_indent():
        s = "no indent\n with indent"
        _assert_block_string(
            s, '"""\nno indent\n with indent\n"""', '"""\nno indent\n with indent"""'
        )

    def correctly_prints_string_with_a_first_line_indentation():
        s = join_lines("    first  ", "  line     ", "indentation", "     string")

        _assert_block_string(
            s,
            join_lines(
                '"""', "    first  ", "  line     ", "indentation", "     string", '"""'
            ),
            join_lines(
                '"""    first  ',
                "  line     ",
                "indentation",
                '     string"""',
            ),
        )

    def correctly_prints_lazy_stings():
        class LazyString:
            def __str__(self) -> str:
                return "lazy"

        _assert_block_string(cast(str, LazyString()), '"""lazy"""')
