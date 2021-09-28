from typing import List, Optional, Tuple

from pytest import raises

from graphql.error import GraphQLSyntaxError
from graphql.language import Lexer, Source, SourceLocation, Token, TokenKind
from graphql.language.lexer import is_punctuator_token_kind
from graphql.pyutils import inspect

from ..utils import dedent

Location = Optional[Tuple[int, int]]


def lex_one(s: str) -> Token:
    lexer = Lexer(Source(s))
    return lexer.advance()


def lex_second(s: str) -> Token:
    lexer = Lexer(Source(s))
    lexer.advance()
    return lexer.advance()


def assert_syntax_error(text: str, message: str, location: Location) -> None:
    with raises(GraphQLSyntaxError) as exc_info:
        lex_second(text)
    error = exc_info.value
    assert error.message == f"Syntax Error: {message}"
    assert error.description == message
    assert error.locations == [location]


def describe_lexer():
    def ignores_bom_header():
        token = lex_one("\uFEFF foo")
        assert token == Token(TokenKind.NAME, 2, 5, 1, 3, "foo")

    def tracks_line_breaks():
        assert lex_one("foo") == Token(TokenKind.NAME, 0, 3, 1, 1, "foo")
        assert lex_one("\nfoo") == Token(TokenKind.NAME, 1, 4, 2, 1, "foo")
        assert lex_one("\rfoo") == Token(TokenKind.NAME, 1, 4, 2, 1, "foo")
        assert lex_one("\r\nfoo") == Token(TokenKind.NAME, 2, 5, 2, 1, "foo")
        assert lex_one("\n\rfoo") == Token(TokenKind.NAME, 2, 5, 3, 1, "foo")
        assert lex_one("\r\r\n\nfoo") == Token(TokenKind.NAME, 4, 7, 4, 1, "foo")
        assert lex_one("\n\n\r\rfoo") == Token(TokenKind.NAME, 4, 7, 5, 1, "foo")

    def records_line_and_column():
        token = lex_one("\n \r\n \r  foo\n")
        assert token == Token(TokenKind.NAME, 8, 11, 4, 3, "foo")

    def can_be_stringified_or_pyutils_inspected():
        token = lex_one("foo")
        assert token.desc == "Name 'foo'"
        assert str(token) == token.desc
        assert repr(token) == "<Token Name 'foo' 1:1>"
        assert inspect(token) == repr(token)

    def skips_whitespace_and_comments():
        token = lex_one("\n\n    foo\n\n\n")
        assert token == Token(TokenKind.NAME, 6, 9, 3, 5, "foo")
        token = lex_one("\r\n\r\n  foo\r\n\r\n")
        assert token == Token(TokenKind.NAME, 6, 9, 3, 3, "foo")
        token = lex_one("\r\r  foo\r\r")
        assert token == Token(TokenKind.NAME, 4, 7, 3, 3, "foo")
        token = lex_one("\t\tfoo\t\t")
        assert token == Token(TokenKind.NAME, 2, 5, 1, 3, "foo")
        token = lex_one("\n    #comment\n    foo#comment\n")
        assert token == Token(TokenKind.NAME, 18, 21, 3, 5, "foo")
        token = lex_one(",,,foo,,,")
        assert token == Token(TokenKind.NAME, 3, 6, 1, 4, "foo")

    def errors_respect_whitespace():
        with raises(GraphQLSyntaxError) as exc_info:
            lex_one("\n\n    ?\n")

        assert str(exc_info.value) == dedent(
            """
            Syntax Error: Unexpected character: '?'.

            GraphQL request:3:5
            2 |
            3 |     ?
              |     ^
            4 |
            """
        )

    def updates_line_numbers_in_error_for_file_context():
        s = "\n\n     ?\n\n"
        source = Source(s, "foo.js", SourceLocation(11, 12))
        with raises(GraphQLSyntaxError) as exc_info:
            Lexer(source).advance()
        assert str(exc_info.value) == dedent(
            """
            Syntax Error: Unexpected character: '?'.

            foo.js:13:6
            12 |
            13 |      ?
               |      ^
            14 |
            """
        )

    def updates_column_numbers_in_error_for_file_context():
        source = Source("?", "foo.js", SourceLocation(1, 5))
        with raises(GraphQLSyntaxError) as exc_info:
            Lexer(source).advance()
        assert str(exc_info.value) == dedent(
            """
            Syntax Error: Unexpected character: '?'.

            foo.js:1:5
            1 |     ?
              |     ^
            """
        )

    # noinspection PyArgumentEqualDefault
    def lexes_empty_string():
        token = lex_one('""')
        assert token == Token(TokenKind.STRING, 0, 2, 1, 1, "")
        assert token.value == ""

    # noinspection PyArgumentEqualDefault
    def lexes_strings():
        assert lex_one('""') == Token(TokenKind.STRING, 0, 2, 1, 1, "")
        assert lex_one('"simple"') == Token(TokenKind.STRING, 0, 8, 1, 1, "simple")
        assert lex_one('" white space "') == Token(
            TokenKind.STRING, 0, 15, 1, 1, " white space "
        )
        assert lex_one('"quote \\""') == Token(TokenKind.STRING, 0, 10, 1, 1, 'quote "')
        assert lex_one('"escaped \\n\\r\\b\\t\\f"') == Token(
            TokenKind.STRING, 0, 20, 1, 1, "escaped \n\r\b\t\f"
        )
        assert lex_one('"slashes \\\\ \\/"') == Token(
            TokenKind.STRING, 0, 15, 1, 1, "slashes \\ /"
        )
        assert lex_one('"unescaped surrogate pair \uD83D\uDE00"') == Token(
            TokenKind.STRING, 0, 29, 1, 1, "unescaped surrogate pair \uD83D\uDE00"
        )
        assert lex_one('"unescaped unicode outside BMP \U0001f600"') == Token(
            TokenKind.STRING, 0, 33, 1, 1, "unescaped unicode outside BMP \U0001f600"
        )
        assert lex_one('"unescaped maximal unicode outside BMP \U0010ffff"') == Token(
            TokenKind.STRING,
            0,
            41,
            1,
            1,
            "unescaped maximal unicode outside BMP \U0010ffff",
        )
        assert lex_one('"unicode \\u1234\\u5678\\u90AB\\uCDEF"') == Token(
            TokenKind.STRING, 0, 34, 1, 1, "unicode \u1234\u5678\u90AB\uCDEF"
        )
        assert lex_one('"unicode \\u{1234}\\u{5678}\\u{90AB}\\u{CDEF}"') == Token(
            TokenKind.STRING, 0, 42, 1, 1, "unicode \u1234\u5678\u90AB\uCDEF"
        )
        assert lex_one('"string with unicode escape outside BMP \\u{1F600}"') == Token(
            TokenKind.STRING,
            0,
            50,
            1,
            1,
            "string with unicode escape outside BMP \U0001F600",
        )
        assert lex_one('"string with minimal unicode escape \\u{0}"') == Token(
            TokenKind.STRING, 0, 42, 1, 1, "string with minimal unicode escape \u0000"
        )
        assert lex_one('"string with maximal unicode escape \\u{10FFFF}"') == Token(
            TokenKind.STRING,
            0,
            47,
            1,
            1,
            "string with maximal unicode escape \U0010FFFF",
        )
        assert lex_one(
            '"string with maximal minimal unicode escape \\u{00000000}"'
        ) == Token(
            TokenKind.STRING,
            0,
            57,
            1,
            1,
            "string with maximal minimal unicode escape \u0000",
        )
        assert lex_one(
            '"string with unicode surrogate pair escape \\uD83D\\uDE00"'
        ) == Token(
            TokenKind.STRING,
            0,
            56,
            1,
            1,
            "string with unicode surrogate pair escape \U0001f600",
        )
        assert lex_one(
            '"string with unicode surrogate pair escape \\uD800\\uDC00"'
        ) == Token(
            TokenKind.STRING,
            0,
            56,
            1,
            1,
            "string with unicode surrogate pair escape \U00010000",
        )
        assert lex_one(
            '"string with unicode surrogate pair escape \\uDBFF\\uDFFF"'
        ) == Token(
            TokenKind.STRING,
            0,
            56,
            1,
            1,
            "string with unicode surrogate pair escape \U0010FFFF",
        )

    def lex_reports_useful_string_errors():
        assert_syntax_error('"', "Unterminated string.", (1, 2))
        assert_syntax_error('"""', "Unterminated string.", (1, 4))
        assert_syntax_error('""""', "Unterminated string.", (1, 5))
        assert_syntax_error('"no end quote', "Unterminated string.", (1, 14))
        assert_syntax_error(
            "'single quotes'",
            "Unexpected single quote character ('), "
            'did you mean to use a double quote (")?',
            (1, 1),
        )
        assert_syntax_error(
            '"bad surrogate \uDEAD"',
            "Invalid character within String: U+DEAD.",
            (1, 16),
        )
        assert_syntax_error(
            '"bad high surrogate pair \uDEAD\uDEAD"',
            "Invalid character within String: U+DEAD.",
            (1, 26),
        )
        assert_syntax_error(
            '"bad low surrogate pair \uD800\uD800"',
            "Invalid character within String: U+D800.",
            (1, 25),
        )
        assert_syntax_error('"multi\nline"', "Unterminated string.", (1, 7))
        assert_syntax_error('"multi\rline"', "Unterminated string.", (1, 7))
        assert_syntax_error(
            '"bad \\z esc"', "Invalid character escape sequence: '\\z'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\x esc"', "Invalid character escape sequence: '\\x'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\u1 esc"', "Invalid Unicode escape sequence: '\\u1 es'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\u0XX1 esc"', "Invalid Unicode escape sequence: '\\u0XX1'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\uXXXX esc"', "Invalid Unicode escape sequence: '\\uXXXX'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\uFXXX esc"', "Invalid Unicode escape sequence: '\\uFXXX'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\uXXXF esc"', "Invalid Unicode escape sequence: '\\uXXXF'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\u{} esc"', "Invalid Unicode escape sequence: '\\u{}'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\u{FXXX} esc"', "Invalid Unicode escape sequence: '\\u{FX'.", (1, 6)
        )
        assert_syntax_error(
            '"bad \\u{FFFF esc"',
            "Invalid Unicode escape sequence: '\\u{FFFF '.",
            (1, 6),
        )
        assert_syntax_error(
            '"bad \\u{FFFF"', "Invalid Unicode escape sequence: '\\u{FFFF\"'.", (1, 6)
        )
        assert_syntax_error(
            '"too high \\u{110000} esc"',
            "Invalid Unicode escape sequence: '\\u{110000}'.",
            (1, 11),
        )
        assert_syntax_error(
            '"way too high \\u{12345678} esc"',
            "Invalid Unicode escape sequence: '\\u{12345678}'.",
            (1, 15),
        )
        assert_syntax_error(
            '"too long \\u{000000000} esc"',
            "Invalid Unicode escape sequence: '\\u{000000000'.",
            (1, 11),
        )
        assert_syntax_error(
            '"bad surrogate \\uDEAD esc"',
            "Invalid Unicode escape sequence: '\\uDEAD'.",
            (1, 16),
        )
        assert_syntax_error(
            '"bad surrogate \\u{DEAD} esc"',
            "Invalid Unicode escape sequence: '\\u{DEAD}'.",
            (1, 16),
        )
        assert_syntax_error(
            '"cannot use braces for surrogate pair \\u{D83D}\\u{DE00} esc"',
            "Invalid Unicode escape sequence: '\\u{D83D}'.",
            (1, 39),
        )
        assert_syntax_error(
            '"bad high surrogate pair \\uDEAD\\uDEAD esc"',
            "Invalid Unicode escape sequence: '\\uDEAD'.",
            (1, 26),
        )
        assert_syntax_error(
            '"bad low surrogate pair \\uD800\\uD800 esc"',
            "Invalid Unicode escape sequence: '\\uD800'.",
            (1, 25),
        )
        assert_syntax_error(
            '"cannot escape half a pair \uD83D\\uDE00 esc"',
            "Invalid character within String: U+D83D.",
            (1, 28),
        )
        assert_syntax_error(
            '"cannot escape half a pair \\uD83D\uDE00 esc"',
            "Invalid Unicode escape sequence: '\\uD83D'.",
            (1, 28),
        )
        assert_syntax_error(
            '"bad \\uD83D\\not an escape"',
            "Invalid Unicode escape sequence: '\\uD83D'.",
            (1, 6),
        )

    # noinspection PyArgumentEqualDefault
    def lexes_block_strings():
        assert lex_one('""""""') == Token(TokenKind.BLOCK_STRING, 0, 6, 1, 1, "")
        assert lex_one('"""simple"""') == Token(
            TokenKind.BLOCK_STRING, 0, 12, 1, 1, "simple"
        )
        assert lex_one('""" white space """') == Token(
            TokenKind.BLOCK_STRING, 0, 19, 1, 1, " white space "
        )
        assert lex_one('"""contains " quote"""') == Token(
            TokenKind.BLOCK_STRING, 0, 22, 1, 1, 'contains " quote'
        )
        assert lex_one('"""contains \\""" triple-quote"""') == Token(
            TokenKind.BLOCK_STRING, 0, 32, 1, 1, 'contains """ triple-quote'
        )
        assert lex_one('"""multi\nline"""') == Token(
            TokenKind.BLOCK_STRING, 0, 16, 2, -8, "multi\nline"
        )
        assert lex_one('"""multi\rline\r\nnormalized"""') == Token(
            TokenKind.BLOCK_STRING, 0, 28, 3, -14, "multi\nline\nnormalized"
        )
        assert lex_one('"""unescaped \\n\\r\\b\\t\\f\\u1234"""') == Token(
            TokenKind.BLOCK_STRING,
            0,
            32,
            1,
            1,
            "unescaped \\n\\r\\b\\t\\f\\u1234",
        )
        assert lex_one('"""unescaped surrogate pair \uD83D\uDE00"""') == Token(
            TokenKind.BLOCK_STRING,
            0,
            33,
            1,
            1,
            "unescaped surrogate pair \uD83D\uDE00",
        )
        assert lex_one('"""unescaped unicode outside BMP \U0001f600"""') == Token(
            TokenKind.BLOCK_STRING,
            0,
            37,
            1,
            1,
            "unescaped unicode outside BMP \U0001f600",
        )
        assert lex_one('"""slashes \\\\ \\/"""') == Token(
            TokenKind.BLOCK_STRING, 0, 19, 1, 1, "slashes \\\\ \\/"
        )
        assert lex_one(
            '"""\n\n        spans\n          multiple\n'
            '            lines\n\n        """'
        ) == Token(
            TokenKind.BLOCK_STRING, 0, 68, 7, -56, "spans\n  multiple\n    lines"
        )

    def advance_line_after_lexing_multiline_block_string():
        assert (
            lex_second(
                '''"""

        spans
          multiple
            lines

        \n """ second_token'''
            )
            == Token(TokenKind.NAME, 71, 83, 8, 6, "second_token")
        )

    def lex_reports_useful_block_string_errors():
        assert_syntax_error('"""', "Unterminated string.", (1, 4))
        assert_syntax_error('"""no end quote', "Unterminated string.", (1, 16))
        assert_syntax_error(
            '"""contains invalid surrogate \uDEAD"""',
            "Invalid character within String: U+DEAD.",
            (1, 31),
        )

    # noinspection PyArgumentEqualDefault
    def lexes_numbers():
        assert lex_one("0") == Token(TokenKind.INT, 0, 1, 1, 1, "0")
        assert lex_one("1") == Token(TokenKind.INT, 0, 1, 1, 1, "1")
        assert lex_one("4") == Token(TokenKind.INT, 0, 1, 1, 1, "4")
        assert lex_one("9") == Token(TokenKind.INT, 0, 1, 1, 1, "9")
        assert lex_one("42") == Token(TokenKind.INT, 0, 2, 1, 1, "42")
        assert lex_one("4.123") == Token(TokenKind.FLOAT, 0, 5, 1, 1, "4.123")
        assert lex_one("-4") == Token(TokenKind.INT, 0, 2, 1, 1, "-4")
        assert lex_one("-42") == Token(TokenKind.INT, 0, 3, 1, 1, "-42")
        assert lex_one("-4.123") == Token(TokenKind.FLOAT, 0, 6, 1, 1, "-4.123")
        assert lex_one("0.123") == Token(TokenKind.FLOAT, 0, 5, 1, 1, "0.123")
        assert lex_one("123e4") == Token(TokenKind.FLOAT, 0, 5, 1, 1, "123e4")
        assert lex_one("123E4") == Token(TokenKind.FLOAT, 0, 5, 1, 1, "123E4")
        assert lex_one("123e-4") == Token(TokenKind.FLOAT, 0, 6, 1, 1, "123e-4")
        assert lex_one("123e+4") == Token(TokenKind.FLOAT, 0, 6, 1, 1, "123e+4")
        assert lex_one("-1.123e4") == Token(TokenKind.FLOAT, 0, 8, 1, 1, "-1.123e4")
        assert lex_one("-1.123E4") == Token(TokenKind.FLOAT, 0, 8, 1, 1, "-1.123E4")
        assert lex_one("-1.123e-4") == Token(TokenKind.FLOAT, 0, 9, 1, 1, "-1.123e-4")
        assert lex_one("-1.123e+4") == Token(TokenKind.FLOAT, 0, 9, 1, 1, "-1.123e+4")
        assert lex_one("-1.123e4567") == Token(
            TokenKind.FLOAT, 0, 11, 1, 1, "-1.123e4567"
        )

    def lex_reports_useful_number_errors():
        assert_syntax_error(
            "00", "Invalid number, unexpected digit after 0: '0'.", (1, 2)
        )
        assert_syntax_error(
            "01", "Invalid number, unexpected digit after 0: '1'.", (1, 2)
        )
        assert_syntax_error(
            "01.23", "Invalid number, unexpected digit after 0: '1'.", (1, 2)
        )
        assert_syntax_error("+1", "Unexpected character: '+'.", (1, 1))
        assert_syntax_error(
            "1.", "Invalid number, expected digit but got: <EOF>.", (1, 3)
        )
        assert_syntax_error(
            "1e", "Invalid number, expected digit but got: <EOF>.", (1, 3)
        )
        assert_syntax_error(
            "1E", "Invalid number, expected digit but got: <EOF>.", (1, 3)
        )
        assert_syntax_error(
            "1.e1", "Invalid number, expected digit but got: 'e'.", (1, 3)
        )
        assert_syntax_error(".123", "Unexpected character: '.'.", (1, 1))
        assert_syntax_error(
            "1.A", "Invalid number, expected digit but got: 'A'.", (1, 3)
        )
        assert_syntax_error(
            "-A", "Invalid number, expected digit but got: 'A'.", (1, 2)
        )
        assert_syntax_error(
            "1.0e", "Invalid number, expected digit but got: <EOF>.", (1, 5)
        )
        assert_syntax_error(
            "1.0eA", "Invalid number, expected digit but got: 'A'.", (1, 5)
        )

        assert_syntax_error(
            '1.0e"', "Invalid number, expected digit but got: '\"'.", (1, 5)
        )

        assert_syntax_error(
            "1.2e3e", "Invalid number, expected digit but got: 'e'.", (1, 6)
        )
        assert_syntax_error(
            "1.2e3.4", "Invalid number, expected digit but got: '.'.", (1, 6)
        )
        assert_syntax_error(
            "1.23.4", "Invalid number, expected digit but got: '.'.", (1, 5)
        )

    def lex_does_not_allow_name_start_after_a_number():
        assert_syntax_error(
            "0xF1", "Invalid number, expected digit but got: 'x'.", (1, 2)
        )
        assert_syntax_error(
            "0b10", "Invalid number, expected digit but got: 'b'.", (1, 2)
        )
        assert_syntax_error(
            "123abc", "Invalid number, expected digit but got: 'a'.", (1, 4)
        )
        assert_syntax_error(
            "1_234", "Invalid number, expected digit but got: '_'.", (1, 2)
        )
        assert_syntax_error("1\xdf", "Unexpected character: U+00DF.", (1, 2))
        assert_syntax_error(
            "1.23f", "Invalid number, expected digit but got: 'f'.", (1, 5)
        )
        assert_syntax_error(
            "1.234_5", "Invalid number, expected digit but got: '_'.", (1, 6)
        )

    # noinspection PyArgumentEqualDefault
    def lexes_punctuation():
        assert lex_one("!") == Token(TokenKind.BANG, 0, 1, 1, 1, None)
        assert lex_one("$") == Token(TokenKind.DOLLAR, 0, 1, 1, 1, None)
        assert lex_one("(") == Token(TokenKind.PAREN_L, 0, 1, 1, 1, None)
        assert lex_one(")") == Token(TokenKind.PAREN_R, 0, 1, 1, 1, None)
        assert lex_one("...") == Token(TokenKind.SPREAD, 0, 3, 1, 1, None)
        assert lex_one(":") == Token(TokenKind.COLON, 0, 1, 1, 1, None)
        assert lex_one("=") == Token(TokenKind.EQUALS, 0, 1, 1, 1, None)
        assert lex_one("@") == Token(TokenKind.AT, 0, 1, 1, 1, None)
        assert lex_one("[") == Token(TokenKind.BRACKET_L, 0, 1, 1, 1, None)
        assert lex_one("]") == Token(TokenKind.BRACKET_R, 0, 1, 1, 1, None)
        assert lex_one("{") == Token(TokenKind.BRACE_L, 0, 1, 1, 1, None)
        assert lex_one("}") == Token(TokenKind.BRACE_R, 0, 1, 1, 1, None)
        assert lex_one("|") == Token(TokenKind.PIPE, 0, 1, 1, 1, None)

    def lex_reports_useful_unknown_character_error():
        assert_syntax_error("..", "Unexpected character: '.'.", (1, 1))
        assert_syntax_error("?", "Unexpected character: '?'.", (1, 1))
        assert_syntax_error("\x00", "Unexpected character: U+0000.", (1, 1))
        assert_syntax_error("\b", "Unexpected character: U+0008.", (1, 1))
        assert_syntax_error("\xAA", "Unexpected character: U+00AA.", (1, 1))
        assert_syntax_error("\u0AAA", "Unexpected character: U+0AAA.", (1, 1))
        assert_syntax_error("\u203B", "Unexpected character: U+203B.", (1, 1))
        assert_syntax_error("\U0001f600", "Unexpected character: U+1F600.", (1, 1))
        assert_syntax_error("\uD83D\uDE00", "Unexpected character: U+1F600.", (1, 1))
        assert_syntax_error("\uD800\uDC00", "Unexpected character: U+10000.", (1, 1))
        assert_syntax_error("\uDBFF\uDFFF", "Unexpected character: U+10FFFF.", (1, 1))
        assert_syntax_error("\uDEAD", "Invalid character: U+DEAD.", (1, 1))

    # noinspection PyArgumentEqualDefault
    def lex_reports_useful_information_for_dashes_in_names():
        source = Source("a-b")
        lexer = Lexer(source)
        first_token = lexer.advance()
        assert first_token == Token(TokenKind.NAME, 0, 1, 1, 1, "a")
        with raises(GraphQLSyntaxError) as exc_info:
            lexer.advance()
        error = exc_info.value
        assert error.message == (
            "Syntax Error: Invalid number, expected digit but got: 'b'."
        )
        assert error.locations == [(1, 3)]

    def produces_double_linked_list_of_tokens_including_comments():
        source = Source(
            """
            {
              #comment
              field
            }
            """
        )
        lexer = Lexer(source)
        start_token = lexer.token
        while True:
            end_token = lexer.advance()
            if end_token.kind == TokenKind.EOF:
                break
            assert end_token.kind != TokenKind.COMMENT
        assert start_token.prev is None
        assert end_token.next is None
        tokens: List[Token] = []
        tok: Optional[Token] = start_token
        while tok:
            assert not tokens or tok.prev == tokens[-1]
            tokens.append(tok)
            tok = tok.next
        assert [tok.kind for tok in tokens] == [
            TokenKind.SOF,
            TokenKind.BRACE_L,
            TokenKind.COMMENT,
            TokenKind.NAME,
            TokenKind.BRACE_R,
            TokenKind.EOF,
        ]

    def lexes_comments():
        assert lex_one("# Comment").prev == Token(
            TokenKind.COMMENT, 0, 9, 1, 1, " Comment"
        )
        assert lex_one("# Comment\nAnother line").prev == Token(
            TokenKind.COMMENT, 0, 9, 1, 1, " Comment"
        )
        assert lex_one("# Comment\r\nAnother line").prev == Token(
            TokenKind.COMMENT, 0, 9, 1, 1, " Comment"
        )
        assert lex_one("# Comment \U0001f600").prev == Token(
            TokenKind.COMMENT, 0, 11, 1, 1, " Comment \U0001f600"
        )
        assert lex_one("# Comment \uD83D\uDE00").prev == Token(
            TokenKind.COMMENT, 0, 12, 1, 1, " Comment \uD83D\uDE00"
        )
        assert_syntax_error(
            "# Invalid surrogate \uDEAD", "Invalid character: U+DEAD.", (1, 21)
        )


def describe_is_punctuator_token_kind():
    def _is_punctuator_token(text: str) -> bool:
        return is_punctuator_token_kind(lex_one(text).kind)

    def returns_true_for_punctuator_tokens():
        assert _is_punctuator_token("!") is True
        assert _is_punctuator_token("$") is True
        assert _is_punctuator_token("&") is True
        assert _is_punctuator_token("(") is True
        assert _is_punctuator_token(")") is True
        assert _is_punctuator_token("...") is True
        assert _is_punctuator_token(":") is True
        assert _is_punctuator_token("=") is True
        assert _is_punctuator_token("@") is True
        assert _is_punctuator_token("[") is True
        assert _is_punctuator_token("]") is True
        assert _is_punctuator_token("{") is True
        assert _is_punctuator_token("|") is True
        assert _is_punctuator_token("}") is True

    def returns_false_for_non_punctuator_tokens():
        assert _is_punctuator_token("") is False
        assert _is_punctuator_token("name") is False
        assert _is_punctuator_token("1") is False
        assert _is_punctuator_token("3.14") is False
        assert _is_punctuator_token('"str"') is False
        assert _is_punctuator_token('"""str"""') is False
