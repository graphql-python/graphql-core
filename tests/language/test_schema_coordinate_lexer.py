from typing import Optional, Tuple

from pytest import raises

from graphql.error import GraphQLSyntaxError
from graphql.language import Source, Token, TokenKind
from graphql.language.schema_coordinate_lexer import SchemaCoordinateLexer

Location = Optional[Tuple[int, int]]


def lex_second(s: str) -> Token:
    lexer = SchemaCoordinateLexer(Source(s))
    lexer.advance()
    return lexer.advance()


def assert_syntax_error(text: str, message: str, location: Location) -> None:
    with raises(GraphQLSyntaxError) as exc_info:
        lex_second(text)
    error = exc_info.value
    assert error.message == f"Syntax Error: {message}"
    assert error.description == message
    assert error.locations == [location]


def describe_schema_coordinate_lexer():
    def tracks_a_schema_coordinate():
        lexer = SchemaCoordinateLexer(Source("Name.field"))
        assert lexer.advance() == Token(TokenKind.NAME, 0, 4, 1, 1, "Name")

    def forbids_ignored_tokens():
        lexer = SchemaCoordinateLexer(Source("\nName.field"))
        with raises(GraphQLSyntaxError) as exc_info:
            lexer.advance()
        error = exc_info.value
        assert error.message == "Syntax Error: Invalid character: U+000A."
        assert error.locations == [(1, 1)]

    def lex_reports_a_useful_syntax_error():
        assert_syntax_error("Foo .bar", "Invalid character: ' '.", (1, 4))
