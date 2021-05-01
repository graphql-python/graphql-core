from json import dumps
from typing import Optional

from pytest import raises

from graphql.error import GraphQLSyntaxError
from graphql.language import Lexer, Source, TokenKind, parse
from graphql.utilities import strip_ignored_characters

from ..fixtures import kitchen_sink_query, kitchen_sink_sdl  # noqa: F401
from ..utils import dedent

ignored_tokens = [
    # UnicodeBOM
    "\uFEFF",  # Byte Order Mark (U+FEFF)
    # WhiteSpace
    "\t",  # Horizontal Tab (U+0009)
    " ",  # Space (U+0020)
    # LineTerminator
    "\n",  # "New Line (U+000A)"
    "\r",  # "Carriage Return (U+000D)" [ lookahead ! "New Line (U+000A)" ]
    "\r\n",  # "Carriage Return (U+000D)" "New Line (U+000A)"
    # Comment
    '# "Comment" string\n',  # `#` CommentChar*
    # Comma
    ",",  # ,
]

punctuator_tokens = ["!", "$", "(", ")", "...", ":", "=", "@", "[", "]", "{", "|", "}"]

non_punctuator_tokens = [
    "name_token",  # Name
    "1",  # IntValue
    "3.14",  # FloatValue
    '"some string value"',  # StringValue
    '"""block\nstring\nvalue"""',  # StringValue(BlockString)
]


def lex_value(s: str) -> Optional[str]:
    lexer = Lexer(Source(s))
    value = lexer.advance().value
    assert lexer.advance().kind == TokenKind.EOF, "Expected EOF"
    return value


class ExpectStripped:
    def __init__(self, doc_string: str):
        self.doc_string = doc_string

    def to_equal(self, expected: str):
        doc_string = self.doc_string
        stripped = strip_ignored_characters(doc_string)

        assert stripped == expected, dedent(
            f"""
            Expected strip_ignored_characters({doc_string!r})
              to equal {expected!r}
              but got {stripped!r}
            """
        )

        stripped_twice = strip_ignored_characters(stripped)

        assert stripped == stripped_twice, dedent(
            f""""
            Expected strip_ignored_characters({stripped!r})"
              to equal {stripped!r}
              but got {stripped_twice!r}
            """
        )

    def to_stay_the_same(self):
        self.to_equal(self.doc_string)


def describe_strip_ignored_characters():
    def strips_ignored_characters_from_graphql_query_document():
        query = dedent(
            """
            query SomeQuery($foo: String!, $bar: String) {
              someField(foo: $foo, bar: $bar) {
                a
                b {
                  c
                  d
                }
              }
            }
            """
        )

        assert strip_ignored_characters(query) == (
            "query SomeQuery($foo:String!$bar:String)"
            "{someField(foo:$foo bar:$bar){a b{c d}}}"
        )

    def strips_ignored_characters_from_graphql_sdl_document():
        sdl = dedent(
            '''
            """
            Type description
            """
            type Foo {
              """
              Field description
              """
              bar: String
            }
          '''
        )

        assert strip_ignored_characters(sdl) == (
            '"""Type description""" type Foo{"""Field description""" bar:String}'
        )

    def report_document_with_invalid_token():
        with raises(GraphQLSyntaxError) as exc_info:
            strip_ignored_characters('{ foo(arg: "\n"')

        assert str(exc_info.value) + "\n" == dedent(
            """
            Syntax Error: Unterminated string.

            GraphQL request:1:13
            1 | { foo(arg: "
              |             ^
            2 | "
            """
        )

    def strips_non_parsable_document():
        ExpectStripped('{ foo(arg: "str"').to_equal('{foo(arg:"str"')

    def strips_documents_with_only_ignored_characters():
        ExpectStripped("\n").to_equal("")
        ExpectStripped(",").to_equal("")
        ExpectStripped(",,").to_equal("")
        ExpectStripped("#comment\n, \n").to_equal("")

        for ignored in ignored_tokens:
            ExpectStripped(ignored).to_equal("")

            for another_ignored in ignored_tokens:
                ExpectStripped(ignored + another_ignored).to_equal("")

        ExpectStripped("".join(ignored_tokens)).to_equal("")

    def strips_leading_and_trailing_ignored_tokens():
        ExpectStripped("\n1").to_equal("1")
        ExpectStripped(",1").to_equal("1")
        ExpectStripped(",,1").to_equal("1")
        ExpectStripped("#comment\n, \n1").to_equal("1")

        ExpectStripped("1\n").to_equal("1")
        ExpectStripped("1,").to_equal("1")
        ExpectStripped("1,,").to_equal("1")
        ExpectStripped("1#comment\n, \n").to_equal("1")

        for token in punctuator_tokens + non_punctuator_tokens:
            for ignored in ignored_tokens:
                ExpectStripped(ignored + token).to_equal(token)
                ExpectStripped(token + ignored).to_equal(token)

                for another_ignored in ignored_tokens:
                    ExpectStripped(token + ignored + ignored).to_equal(token)
                    ExpectStripped(ignored + another_ignored + token).to_equal(token)

            ExpectStripped("".join(ignored_tokens) + token).to_equal(token)
            ExpectStripped(token + "".join(ignored_tokens)).to_equal(token)

    def strips_ignored_tokens_between_punctuator_tokens():
        ExpectStripped("[,)").to_equal("[)")
        ExpectStripped("[\r)").to_equal("[)")
        ExpectStripped("[\r\r)").to_equal("[)")
        ExpectStripped("[\r,)").to_equal("[)")
        ExpectStripped("[,\n)").to_equal("[)")

        for left in punctuator_tokens:
            for right in punctuator_tokens:
                for ignored in ignored_tokens:
                    ExpectStripped(left + ignored + right).to_equal(left + right)

                    for another_ignored in ignored_tokens:
                        ExpectStripped(
                            left + ignored + another_ignored + right
                        ).to_equal(left + right)

                ExpectStripped(left + "".join(ignored_tokens) + right).to_equal(
                    left + right
                )

    def strips_ignored_tokens_between_punctuator_and_non_punctuator_tokens():
        ExpectStripped("[,1").to_equal("[1")
        ExpectStripped("[\r1").to_equal("[1")
        ExpectStripped("[\r\r1").to_equal("[1")
        ExpectStripped("[\r,1").to_equal("[1")
        ExpectStripped("[,\n1").to_equal("[1")

        for non_punctuator in non_punctuator_tokens:
            for punctuator in punctuator_tokens:
                for ignored in ignored_tokens:
                    ExpectStripped(punctuator + ignored + non_punctuator).to_equal(
                        punctuator + non_punctuator
                    )

                    for another_ignored in ignored_tokens:
                        ExpectStripped(
                            punctuator + ignored + another_ignored + non_punctuator
                        ).to_equal(punctuator + non_punctuator)

                ExpectStripped(
                    punctuator + "".join(ignored_tokens) + non_punctuator
                ).to_equal(punctuator + non_punctuator)

    def strips_ignored_tokens_between_non_punctuator_and_punctuator_tokens():
        ExpectStripped("1,[").to_equal("1[")
        ExpectStripped("1\r[").to_equal("1[")
        ExpectStripped("1\r\r[").to_equal("1[")
        ExpectStripped("1\r,[").to_equal("1[")
        ExpectStripped("1,\n[").to_equal("1[")

        for non_punctuator in non_punctuator_tokens:
            for punctuator in punctuator_tokens:
                # Special case for that is handled in the below test
                if punctuator == "...":
                    continue

                for ignored in ignored_tokens:
                    ExpectStripped(non_punctuator + ignored + punctuator).to_equal(
                        non_punctuator + punctuator
                    )

                    for another_ignored in ignored_tokens:
                        ExpectStripped(
                            non_punctuator + ignored + another_ignored + punctuator
                        ).to_equal(non_punctuator + punctuator)

                ExpectStripped(
                    non_punctuator + "".join(ignored_tokens) + punctuator
                ).to_equal(non_punctuator + punctuator)

    def replace_ignored_tokens_between_non_punctuator_tokens_and_spread_with_space():
        ExpectStripped("a ...").to_equal("a ...")
        ExpectStripped("1 ...").to_equal("1 ...")
        ExpectStripped("1 ... ...").to_equal("1 ......")

        for non_punctuator in non_punctuator_tokens:
            for ignored in ignored_tokens:
                ExpectStripped(non_punctuator + ignored + "...").to_equal(
                    non_punctuator + " ..."
                )

                for another_ignored in ignored_tokens:
                    ExpectStripped(
                        non_punctuator + ignored + another_ignored + " ..."
                    ).to_equal(non_punctuator + " ...")

            ExpectStripped(non_punctuator + "".join(ignored_tokens) + "...").to_equal(
                non_punctuator + " ..."
            )

    def replace_ignored_tokens_between_non_punctuator_tokens_with_space():
        ExpectStripped("1 2").to_stay_the_same()
        ExpectStripped('"" ""').to_stay_the_same()
        ExpectStripped("a b").to_stay_the_same()

        ExpectStripped("a,1").to_equal("a 1")
        ExpectStripped("a,,1").to_equal("a 1")
        ExpectStripped("a  1").to_equal("a 1")
        ExpectStripped("a \t 1").to_equal("a 1")

        for left in non_punctuator_tokens:
            for right in non_punctuator_tokens:
                for ignored in ignored_tokens:
                    ExpectStripped(left + ignored + right).to_equal(left + " " + right)

                    for another_ignored in ignored_tokens:
                        ExpectStripped(
                            left + ignored + another_ignored + right
                        ).to_equal(left + " " + right)

                ExpectStripped(left + "".join(ignored_tokens) + right).to_equal(
                    left + " " + right
                )

    def does_not_strip_ignored_tokens_embedded_in_the_string():
        ExpectStripped('" "').to_stay_the_same()
        ExpectStripped('","').to_stay_the_same()
        ExpectStripped('",,"').to_stay_the_same()
        ExpectStripped('",|"').to_stay_the_same()

        for ignored in ignored_tokens:
            ExpectStripped(dumps(ignored)).to_stay_the_same()

            for another_ignored in ignored_tokens:
                ExpectStripped(dumps(ignored + another_ignored)).to_stay_the_same()

        ExpectStripped(dumps("".join(ignored_tokens))).to_stay_the_same()

    def does_not_strip_ignored_tokens_embedded_in_the_block_string():
        ExpectStripped('""","""').to_stay_the_same()
        ExpectStripped('""",,"""').to_stay_the_same()
        ExpectStripped('""",|"""').to_stay_the_same()

        ignored_tokens_without_formatting = [
            token
            for token in ignored_tokens
            if token not in ["\n", "\r", "\r\n", "\t", " "]
        ]

        for ignored in ignored_tokens_without_formatting:
            ExpectStripped('"""|' + ignored + '|"""').to_stay_the_same()

            for another_ignored in ignored_tokens_without_formatting:
                ExpectStripped(
                    '"""|' + ignored + another_ignored + '|"""'
                ).to_stay_the_same()

        ExpectStripped(
            '"""|' + "".join(ignored_tokens_without_formatting) + '|"""'
        ).to_stay_the_same()

    def strips_ignored_characters_inside_block_strings():
        # noinspection PyShadowingNames
        def expect_stripped_string(block_str: str):
            original_value = lex_value(block_str)
            stripped_value = lex_value(strip_ignored_characters(block_str))

            assert original_value == stripped_value, dedent(
                f"""
                Expected lexValue(stripIgnoredCharacters({block_str!r})
                  to equal {original_value!r}
                  but got {stripped_value!r}
                """
            )
            return ExpectStripped(block_str)

        expect_stripped_string('""""""').to_stay_the_same()
        expect_stripped_string('""" """').to_equal('""""""')

        expect_stripped_string('"""a"""').to_stay_the_same()
        expect_stripped_string('""" a"""').to_equal('""" a"""')
        expect_stripped_string('""" a """').to_equal('""" a """')

        expect_stripped_string('"""\n"""').to_equal('""""""')
        expect_stripped_string('"""a\nb"""').to_equal('"""a\nb"""')
        expect_stripped_string('"""a\rb"""').to_equal('"""a\nb"""')
        expect_stripped_string('"""a\r\nb"""').to_equal('"""a\nb"""')
        expect_stripped_string('"""a\r\n\nb"""').to_equal('"""a\n\nb"""')

        expect_stripped_string('"""\\\n"""').to_stay_the_same()
        expect_stripped_string('""""\n"""').to_stay_the_same()
        expect_stripped_string('"""\\"""\n"""').to_equal('"""\\""""""')

        expect_stripped_string('"""\na\n b"""').to_stay_the_same()
        expect_stripped_string('"""\n a\n b"""').to_equal('"""a\nb"""')
        expect_stripped_string('"""\na\n b\nc"""').to_equal('"""a\n b\nc"""')

    # noinspection PyShadowingNames
    def strips_kitchen_sink_query_but_maintains_the_exact_same_ast(
        kitchen_sink_query,  # noqa: F811
    ):
        stripped_query = strip_ignored_characters(kitchen_sink_query)
        assert strip_ignored_characters(stripped_query) == stripped_query

        query_ast = parse(kitchen_sink_query, no_location=True)
        stripped_ast = parse(stripped_query, no_location=True)
        assert stripped_ast == query_ast

    # noinspection PyShadowingNames
    def strips_kitchen_sink_sdl_but_maintains_the_exact_same_ast(
        kitchen_sink_sdl,  # noqa: F811
    ):
        stripped_sdl = strip_ignored_characters(kitchen_sink_sdl)
        assert strip_ignored_characters(stripped_sdl) == stripped_sdl

        sdl_ast = parse(kitchen_sink_sdl, no_location=True)
        stripped_ast = parse(stripped_sdl, no_location=True)
        assert stripped_ast == sdl_ast
