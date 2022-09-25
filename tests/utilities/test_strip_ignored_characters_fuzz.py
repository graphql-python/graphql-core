from json import dumps
from typing import Optional

from pytest import mark

from graphql.error import GraphQLSyntaxError
from graphql.language import Lexer, Source, TokenKind
from graphql.utilities import strip_ignored_characters

from ..utils import dedent, gen_fuzz_strings


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


def lex_value(s: str) -> Optional[str]:
    lexer = Lexer(Source(s))
    value = lexer.advance().value
    assert lexer.advance().kind == TokenKind.EOF, "Expected EOF"
    return value


def describe_strip_ignored_characters():
    @mark.slow
    @mark.timeout(10)
    def strips_documents_with_random_combination_of_ignored_characters():
        for ignored in ignored_tokens:
            ExpectStripped(ignored).to_equal("")

            for another_ignored in ignored_tokens:
                ExpectStripped(ignored + another_ignored).to_equal("")

        ExpectStripped("".join(ignored_tokens)).to_equal("")

    @mark.slow
    @mark.timeout(10)
    def strips_random_leading_and_trailing_ignored_tokens():
        for token in punctuator_tokens + non_punctuator_tokens:
            for ignored in ignored_tokens:
                ExpectStripped(ignored + token).to_equal(token)
                ExpectStripped(token + ignored).to_equal(token)

                for another_ignored in ignored_tokens:
                    ExpectStripped(token + ignored + ignored).to_equal(token)
                    ExpectStripped(ignored + another_ignored + token).to_equal(token)

            ExpectStripped("".join(ignored_tokens) + token).to_equal(token)
            ExpectStripped(token + "".join(ignored_tokens)).to_equal(token)

    @mark.slow
    @mark.timeout(10)
    def strips_random_ignored_tokens_between_punctuator_tokens():
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

    @mark.slow
    @mark.timeout(10)
    def strips_random_ignored_tokens_between_punctuator_and_non_punctuator_tokens():
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

    @mark.slow
    @mark.timeout(10)
    def strips_random_ignored_tokens_between_non_punctuator_and_punctuator_tokens():
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

    @mark.slow
    @mark.timeout(10)
    def replace_random_ignored_tokens_between_non_punctuator_and_spread_with_space():
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

    @mark.slow
    @mark.timeout(10)
    def replace_random_ignored_tokens_between_non_punctuator_tokens_with_space():
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

    @mark.slow
    @mark.timeout(10)
    def does_not_strip_random_ignored_tokens_embedded_in_the_string():
        for ignored in ignored_tokens:
            ExpectStripped(dumps(ignored)).to_stay_the_same()

            for another_ignored in ignored_tokens:
                ExpectStripped(dumps(ignored + another_ignored)).to_stay_the_same()

        ExpectStripped(dumps("".join(ignored_tokens))).to_stay_the_same()

    @mark.slow
    @mark.timeout(10)
    def does_not_strip_random_ignored_tokens_embedded_in_the_block_string():
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
