from typing import List

from ..error import GraphQLSyntaxError
from .ast import Token
from .block_string import dedent_block_string_value
from .source import Source
from .token_kind import TokenKind

__all__ = ["Lexer", "is_punctuator_token_kind"]


_punctuator_token_kinds = frozenset(
    [
        TokenKind.BANG,
        TokenKind.DOLLAR,
        TokenKind.AMP,
        TokenKind.PAREN_L,
        TokenKind.PAREN_R,
        TokenKind.SPREAD,
        TokenKind.COLON,
        TokenKind.EQUALS,
        TokenKind.AT,
        TokenKind.BRACKET_L,
        TokenKind.BRACKET_R,
        TokenKind.BRACE_L,
        TokenKind.PIPE,
        TokenKind.BRACE_R,
    ]
)


def is_punctuator_token_kind(kind: TokenKind) -> bool:
    """Check whether the given token kind corresponds to a punctuator.

    For internal use only.
    """
    return kind in _punctuator_token_kinds


def print_char(char):
    return repr(char) if char else TokenKind.EOF.value


_KIND_FOR_PUNCT = {
    "!": TokenKind.BANG,
    "$": TokenKind.DOLLAR,
    "&": TokenKind.AMP,
    "(": TokenKind.PAREN_L,
    ")": TokenKind.PAREN_R,
    ":": TokenKind.COLON,
    "=": TokenKind.EQUALS,
    "@": TokenKind.AT,
    "[": TokenKind.BRACKET_L,
    "]": TokenKind.BRACKET_R,
    "{": TokenKind.BRACE_L,
    "}": TokenKind.BRACE_R,
    "|": TokenKind.PIPE,
}


class Lexer:
    """GraphQL Lexer

    A Lexer is a stateful stream generator in that every time it is advanced, it returns
    the next token in the Source. Assuming the source lexes, the final Token emitted by
    the lexer will be of kind EOF, after which the lexer will repeatedly return the same
    EOF token whenever called.
    """

    def __init__(self, source: Source):
        """Given a Source object, initialize a Lexer for that source."""
        self.source = source
        self.token = self.last_token = Token(TokenKind.SOF, 0, 0, 0, 0)
        self.line, self.line_start = 1, 0

    def advance(self) -> Token:
        """Advance the token stream to the next non-ignored token."""
        self.last_token = self.token
        token = self.token = self.lookahead()
        return token

    def lookahead(self) -> Token:
        """Look ahead and return the next non-ignored token, but do not change state."""
        token = self.token
        if token.kind != TokenKind.EOF:
            while True:
                if not token.next:
                    token.next = self.read_token(token)
                token = token.next
                if token.kind != TokenKind.COMMENT:
                    break
        return token

    def read_token(self, prev: Token) -> Token:
        """Get the next token from the source starting at the given position.

        This skips over whitespace until it finds the next lexable token, then lexes
        punctuators immediately or calls the appropriate helper function for more
        complicated tokens.
        """
        source = self.source
        body = source.body
        body_length = len(body)

        pos = self.position_after_whitespace(body, prev.end)
        line = self.line
        col = 1 + pos - self.line_start

        if pos >= body_length:
            return Token(TokenKind.EOF, body_length, body_length, line, col, prev)

        char = body[pos]
        kind = _KIND_FOR_PUNCT.get(char)
        if kind:
            return Token(kind, pos, pos + 1, line, col, prev)
        if char == "#":
            return self.read_comment(pos, line, col, prev)
        elif char == ".":
            if body[pos + 1 : pos + 3] == "..":
                return Token(TokenKind.SPREAD, pos, pos + 3, line, col, prev)
        elif "A" <= char <= "Z" or "a" <= char <= "z" or char == "_":
            return self.read_name(pos, line, col, prev)
        elif "0" <= char <= "9" or char == "-":
            return self.read_number(pos, char, line, col, prev)
        elif char == '"':
            if body[pos + 1 : pos + 3] == '""':
                return self.read_block_string(pos, line, col, prev)
            return self.read_string(pos, line, col, prev)

        raise GraphQLSyntaxError(source, pos, unexpected_character_message(char))

    def position_after_whitespace(self, body: str, start_position: int) -> int:
        """Go to next position after a whitespace.

        Reads from body starting at start_position until it finds a non-whitespace
        character, then returns the position of that character for lexing.
        """
        body_length = len(body)
        position = start_position
        while position < body_length:
            char = body[position]
            if char in " \t,\ufeff":
                position += 1
            elif char == "\n":
                position += 1
                self.line += 1
                self.line_start = position
            elif char == "\r":  # pragma: no cover
                if body[position + 1 : position + 2] == "\n":
                    position += 2
                else:
                    position += 1
                self.line += 1
                self.line_start = position
            else:  # pragma: no cover
                break
        return position

    def read_comment(self, start: int, line: int, col: int, prev: Token) -> Token:
        """Read a comment token from the source file."""
        body = self.source.body
        body_length = len(body)

        position = start
        while True:
            position += 1
            if position >= body_length:
                break
            char = body[position]
            if char < " " and char != "\t":
                break
        return Token(
            TokenKind.COMMENT,
            start,
            position,
            line,
            col,
            prev,
            body[start + 1 : position],
        )

    def read_number(
        self, start: int, char: str, line: int, col: int, prev: Token
    ) -> Token:
        """Reads a number token from the source file.

        Either a float or an int depending on whether a decimal point appears.
        """
        source = self.source
        body = source.body
        position = start
        is_float = False
        if char == "-":
            position += 1
            char = body[position : position + 1]
        if char == "0":
            position += 1
            char = body[position : position + 1]
            if "0" <= char <= "9":
                raise GraphQLSyntaxError(
                    source,
                    position,
                    f"Invalid number, unexpected digit after 0: {print_char(char)}.",
                )
        else:
            position = self.read_digits(position, char)
            char = body[position : position + 1]
        if char == ".":
            is_float = True
            position += 1
            char = body[position : position + 1]
            position = self.read_digits(position, char)
            char = body[position : position + 1]
        if char and char in "Ee":
            is_float = True
            position += 1
            char = body[position : position + 1]
            if char and char in "+-":
                position += 1
                char = body[position : position + 1]
            position = self.read_digits(position, char)
            char = body[position : position + 1]

        # Numbers cannot be followed by . or NameStart
        if char and (char == "." or is_name_start(char)):
            raise GraphQLSyntaxError(
                source,
                position,
                f"Invalid number, expected digit but got: {print_char(char)}.",
            )

        return Token(
            TokenKind.FLOAT if is_float else TokenKind.INT,
            start,
            position,
            line,
            col,
            prev,
            body[start:position],
        )

    def read_digits(self, start: int, char: str) -> int:
        """Return the new position in the source after reading digits."""
        source = self.source
        body = source.body
        position = start
        while "0" <= char <= "9":
            position += 1
            char = body[position : position + 1]
        if position == start:
            raise GraphQLSyntaxError(
                source,
                position,
                f"Invalid number, expected digit but got: {print_char(char)}.",
            )
        return position

    def read_string(self, start: int, line: int, col: int, prev: Token) -> Token:
        """Read a string token from the source file."""
        source = self.source
        body = source.body
        body_length = len(body)
        position = start + 1
        chunk_start = position
        value: List[str] = []
        append = value.append

        while position < body_length:
            char = body[position]
            if char in "\n\r":
                break
            if char == '"':
                append(body[chunk_start:position])
                return Token(
                    TokenKind.STRING,
                    start,
                    position + 1,
                    line,
                    col,
                    prev,
                    "".join(value),
                )
            if char < " " and char != "\t":
                raise GraphQLSyntaxError(
                    source,
                    position,
                    f"Invalid character within String: {print_char(char)}.",
                )
            position += 1
            if char == "\\":
                append(body[chunk_start : position - 1])
                char = body[position : position + 1]
                escaped = _ESCAPED_CHARS.get(char)
                if escaped:
                    value.append(escaped)
                elif char == "u" and position + 4 < body_length:
                    code = uni_char_code(*body[position + 1 : position + 5])
                    if code < 0:
                        escape = repr(body[position : position + 5])
                        escape = escape[:1] + "\\" + escape[1:]
                        raise GraphQLSyntaxError(
                            source,
                            position,
                            f"Invalid character escape sequence: {escape}.",
                        )
                    append(chr(code))
                    position += 4
                else:
                    escape = repr(char)
                    escape = escape[:1] + "\\" + escape[1:]
                    raise GraphQLSyntaxError(
                        source,
                        position,
                        f"Invalid character escape sequence: {escape}.",
                    )
                position += 1
                chunk_start = position

        raise GraphQLSyntaxError(source, position, "Unterminated string.")

    def read_block_string(self, start: int, line: int, col: int, prev: Token) -> Token:
        source = self.source
        body = source.body
        body_length = len(body)
        position = start + 3
        chunk_start = position
        raw_value = ""

        while position < body_length:
            char = body[position]
            if char == '"' and body[position + 1 : position + 3] == '""':
                raw_value += body[chunk_start:position]
                return Token(
                    TokenKind.BLOCK_STRING,
                    start,
                    position + 3,
                    line,
                    col,
                    prev,
                    dedent_block_string_value(raw_value),
                )
            if char < " " and char not in "\t\n\r":
                raise GraphQLSyntaxError(
                    source,
                    position,
                    f"Invalid character within String: {print_char(char)}.",
                )

            if char == "\n":
                position += 1
                self.line += 1
                self.line_start = position
            elif char == "\r":
                if body[position + 1 : position + 2] == "\n":
                    position += 2
                else:
                    position += 1
                self.line += 1
                self.line_start = position
            elif char == "\\" and body[position + 1 : position + 4] == '"""':
                raw_value += body[chunk_start:position] + '"""'
                position += 4
                chunk_start = position
            else:
                position += 1

        raise GraphQLSyntaxError(source, position, "Unterminated string.")

    def read_name(self, start: int, line: int, col: int, prev: Token) -> Token:
        """Read an alphanumeric + underscore name from the source."""
        body = self.source.body
        body_length = len(body)
        position = start + 1
        while position < body_length:
            char = body[position]
            if not (
                char == "_"
                or "0" <= char <= "9"
                or "A" <= char <= "Z"
                or "a" <= char <= "z"
            ):
                break
            position += 1
        return Token(
            TokenKind.NAME, start, position, line, col, prev, body[start:position]
        )


_ESCAPED_CHARS = {
    '"': '"',
    "/": "/",
    "\\": "\\",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def unexpected_character_message(char: str):
    """Report a message that an unexpected character was encountered."""
    if char < " " and char not in "\t\n\r":
        return f"Cannot contain the invalid character {print_char(char)}."
    if char == "'":
        return (
            "Unexpected single quote character ('),"
            ' did you mean to use a double quote (")?'
        )
    return f"Cannot parse the unexpected character {print_char(char)}."


def uni_char_code(a: str, b: str, c: str, d: str):
    """Convert unicode characters to integers.

    Converts four hexadecimal chars to the integer that the string represents.
    For example, uni_char_code('0','0','0','f') will return 15,
    and uni_char_code('0','0','f','f') returns 255.

    Returns a negative number on error, if a char was invalid.

    This is implemented by noting that char2hex() returns -1 on error,
    which means the result of ORing the char2hex() will also be negative.
    """
    return char2hex(a) << 12 | char2hex(b) << 8 | char2hex(c) << 4 | char2hex(d)


def char2hex(a: str):
    """Convert a hex character to its integer value.

    '0' becomes 0, '9' becomes 9
    'A' becomes 10, 'F' becomes 15
    'a' becomes 10, 'f' becomes 15

    Returns -1 on error.

    """
    if "0" <= a <= "9":
        return ord(a) - 48
    elif "A" <= a <= "F":
        return ord(a) - 55
    elif "a" <= a <= "f":  # a-f
        return ord(a) - 87
    return -1


def is_name_start(char: str) -> bool:
    """Check whether char is an underscore or a plain ASCII letter"""
    return char == "_" or "A" <= char <= "Z" or "a" <= char <= "z"
