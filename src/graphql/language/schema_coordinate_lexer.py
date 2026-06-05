from ..error import GraphQLSyntaxError
from .ast import Token
from .character_classes import is_name_start
from .lexer import Lexer
from .token_kind import TokenKind

__all__ = ["SchemaCoordinateLexer"]


_KIND_FOR_PUNCT = {
    ".": TokenKind.DOT,
    "(": TokenKind.PAREN_L,
    ")": TokenKind.PAREN_R,
    ":": TokenKind.COLON,
    "@": TokenKind.AT,
}


class SchemaCoordinateLexer(Lexer):
    """GraphQL Schema Coordinate Lexer

    A SchemaCoordinateLexer is a stateful stream generator in that every time it is
    advanced, it returns the next token in the Source. Assuming the source lexes, the
    final Token emitted by the lexer will be of kind EOF, after which the lexer will
    repeatedly return the same EOF token whenever called.

    Unlike the regular Lexer, this lexer uses a restricted syntax that does not allow
    any ignored tokens (such as whitespace or comments). Since a schema coordinate may
    not contain a newline, the line is always 1 and the line start is always 0.
    """

    def read_next_token(self, start: int) -> Token:
        """Get the next token from the source starting at the given position.

        This lexes punctuators and names only, raising a syntax error on any other
        character (including ignored tokens such as whitespace and comments).
        """
        body = self.source.body
        body_length = len(body)
        position = start

        if position < body_length:
            char = body[position]

            kind = _KIND_FOR_PUNCT.get(char)
            if kind:
                return self.create_token(kind, position, position + 1)

            if is_name_start(char):
                return self.read_name(position)

            raise GraphQLSyntaxError(
                self.source,
                position,
                f"Invalid character: {self.print_code_point_at(position)}.",
            )

        return self.create_token(TokenKind.EOF, body_length, body_length)
