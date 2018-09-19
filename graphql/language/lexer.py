from copy import copy
from enum import Enum
from typing import List, Optional

from ..error import GraphQLSyntaxError
from .source import Source
from .block_string_value import block_string_value

__all__ = ["Lexer", "TokenKind", "Token"]


class TokenKind(Enum):
    """Each kind of token"""

    SOF = "<SOF>"
    EOF = "<EOF>"
    BANG = "!"
    DOLLAR = "$"
    AMP = "&"
    PAREN_L = "("
    PAREN_R = ")"
    SPREAD = "..."
    COLON = ":"
    EQUALS = "="
    AT = "@"
    BRACKET_L = "["
    BRACKET_R = "]"
    BRACE_L = "{"
    PIPE = "|"
    BRACE_R = "}"
    NAME = "Name"
    INT = "Int"
    FLOAT = "Float"
    STRING = "String"
    BLOCK_STRING = "BlockString"
    COMMENT = "Comment"


class Token:
    __slots__ = ("kind", "start", "end", "line", "column", "prev", "next", "value")

    def __init__(
        self,
        kind: TokenKind,
        start: int,
        end: int,
        line: int,
        column: int,
        prev: "Token" = None,
        value: str = None,
    ) -> None:
        self.kind = kind
        self.start, self.end = start, end
        self.line, self.column = line, column
        self.prev: Optional[Token] = prev or None
        self.next: Optional[Token] = None
        self.value: Optional[str] = value or None

    def __repr__(self):
        return "<Token {} at {}-{} ({}/{})>".format(
            self.desc, self.start, self.end, self.line, self.column
        )

    def __eq__(self, other):
        if isinstance(other, Token):
            return (
                self.kind == other.kind
                and self.start == other.start
                and self.end == other.end
                and self.line == other.line
                and self.column == other.column
                and self.value == other.value
            )
        elif isinstance(other, str):
            return other == self.desc
        return False

    def __copy__(self):
        """Create a shallow copy of the token"""
        return self.__class__(
            self.kind,
            self.start,
            self.end,
            self.line,
            self.column,
            self.prev,
            self.value,
        )

    def __deepcopy__(self, memo):
        """Allow only shallow copies to avoid recursion."""
        return copy(self)

    @property
    def desc(self) -> str:
        """A helper property to describe a token as a string for debugging"""
        kind, value = self.kind.value, self.value
        return f"{kind} {value!r}" if value else kind


def char_at(s, pos):
    try:
        return s[pos]
    except IndexError:
        return None


def print_char(char):
    return TokenKind.EOF.value if char is None else repr(char)


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

    A Lexer is a stateful stream generator in that every time
    it is advanced, it returns the next token in the Source. Assuming the
    source lexes, the final Token emitted by the lexer will be of kind
    EOF, after which the lexer will repeatedly return the same EOF token
    whenever called.

    """

    def __init__(
        self,
        source: Source,
        no_location=False,
        experimental_fragment_variables=False,
        experimental_variable_definition_directives=False,
    ) -> None:
        """Given a Source object, this returns a Lexer for that source."""
        self.source = source
        self.token = self.last_token = Token(TokenKind.SOF, 0, 0, 0, 0)
        self.line, self.line_start = 1, 0
        self.no_location = no_location
        self.experimental_fragment_variables = experimental_fragment_variables
        self.experimental_variable_definition_directives = (
            experimental_variable_definition_directives
        )

    def advance(self):
        self.last_token = self.token
        token = self.token = self.lookahead()
        return token

    def lookahead(self):
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

        This skips over whitespace and comments until it finds the next
        lexable token, then lexes punctuators immediately or calls the
        appropriate helper function for more complicated tokens.

        """
        source = self.source
        body = source.body
        body_length = len(body)

        pos = self.position_after_whitespace(body, prev.end)
        line = self.line
        col = 1 + pos - self.line_start

        if pos >= body_length:
            return Token(TokenKind.EOF, body_length, body_length, line, col, prev)

        char = char_at(body, pos)
        if char is not None:
            kind = _KIND_FOR_PUNCT.get(char)
            if kind:
                return Token(kind, pos, pos + 1, line, col, prev)
            if char == "#":
                return read_comment(source, pos, line, col, prev)
            elif char == ".":
                if char == char_at(body, pos + 1) == char_at(body, pos + 2):
                    return Token(TokenKind.SPREAD, pos, pos + 3, line, col, prev)
            elif "A" <= char <= "Z" or "a" <= char <= "z" or char == "_":
                return read_name(source, pos, line, col, prev)
            elif "0" <= char <= "9" or char == "-":
                return read_number(source, pos, char, line, col, prev)
            elif char == '"':
                if char == char_at(body, pos + 1) == char_at(body, pos + 2):
                    return read_block_string(source, pos, line, col, prev)
                return read_string(source, pos, line, col, prev)

        raise GraphQLSyntaxError(source, pos, unexpected_character_message(char))

    def position_after_whitespace(self, body, start_position: int) -> int:
        """Go to next position after a whitespace.

        Reads from body starting at startPosition until it finds a
        non-whitespace or commented character, then returns the position
        of that character for lexing.

        """
        body_length = len(body)
        position = start_position
        while position < body_length:
            char = char_at(body, position)
            if char is not None and char in " \t,\ufeff":
                position += 1
            elif char == "\n":
                position += 1
                self.line += 1
                self.line_start = position
            elif char == "\r":
                if char_at(body, position + 1) == "\n":
                    position += 2
                else:
                    position += 1
                self.line += 1
                self.line_start = position
            else:
                break
        return position


def unexpected_character_message(char):
    if char < " " and char not in "\t\n\r":
        return f"Cannot contain the invalid character {print_char(char)}."
    if char == "'":
        return (
            "Unexpected single quote character ('),"
            ' did you mean to use a double quote (")?'
        )
    return f"Cannot parse the unexpected character {print_char(char)}."


def read_comment(source: Source, start, line, col, prev) -> Token:
    """Read a comment token from the source file."""
    body = source.body
    position = start
    while True:
        position += 1
        char = char_at(body, position)
        if char is None or (char < " " and char != "\t"):
            break
    return Token(
        TokenKind.COMMENT, start, position, line, col, prev, body[start + 1 : position]
    )


def read_number(source: Source, start, char, line, col, prev) -> Token:
    """Reads a number token from the source file.

    Either a float or an int depending on whether a decimal point appears.

    """
    body = source.body
    position = start
    is_float = False
    if char == "-":
        position += 1
        char = char_at(body, position)
    if char == "0":
        position += 1
        char = char_at(body, position)
        if char is not None and "0" <= char <= "9":
            raise GraphQLSyntaxError(
                source,
                position,
                "Invalid number," f" unexpected digit after 0: {print_char(char)}.",
            )
    else:
        position = read_digits(source, position, char)
        char = char_at(body, position)
    if char == ".":
        is_float = True
        position += 1
        char = char_at(body, position)
        position = read_digits(source, position, char)
        char = char_at(body, position)
    if char is not None and char in "Ee":
        is_float = True
        position += 1
        char = char_at(body, position)
        if char is not None and char in "+-":
            position += 1
            char = char_at(body, position)
        position = read_digits(source, position, char)
    return Token(
        TokenKind.FLOAT if is_float else TokenKind.INT,
        start,
        position,
        line,
        col,
        prev,
        body[start:position],
    )


def read_digits(source: Source, start, char) -> int:
    """Return the new position in the source after reading digits."""
    body = source.body
    position = start
    while char is not None and "0" <= char <= "9":
        position += 1
        char = char_at(body, position)
    if position == start:
        raise GraphQLSyntaxError(
            source,
            position,
            f"Invalid number, expected digit but got: {print_char(char)}.",
        )
    return position


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


def read_string(source: Source, start, line, col, prev) -> Token:
    """Read a string token from the source file."""
    body = source.body
    position = start + 1
    chunk_start = position
    value: List[str] = []
    append = value.append

    while position < len(body):
        char = char_at(body, position)
        if char is None or char in "\n\r":
            break
        if char == '"':
            append(body[chunk_start:position])
            return Token(
                TokenKind.STRING, start, position + 1, line, col, prev, "".join(value)
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
            char = char_at(body, position)
            escaped = _ESCAPED_CHARS.get(char)
            if escaped:
                value.append(escaped)
            elif char == "u":
                code = uni_char_code(
                    char_at(body, position + 1),
                    char_at(body, position + 2),
                    char_at(body, position + 3),
                    char_at(body, position + 4),
                )
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
                    source, position, f"Invalid character escape sequence: {escape}."
                )
            position += 1
            chunk_start = position

    raise GraphQLSyntaxError(source, position, "Unterminated string.")


def read_block_string(source: Source, start, line, col, prev) -> Token:
    body = source.body
    position = start + 3
    chunk_start = position
    raw_value = ""

    while position < len(body):
        char = char_at(body, position)
        if char is None:
            break
        if (
            char == '"'
            and char_at(body, position + 1) == '"'
            and char_at(body, position + 2) == '"'
        ):
            raw_value += body[chunk_start:position]
            return Token(
                TokenKind.BLOCK_STRING,
                start,
                position + 3,
                line,
                col,
                prev,
                block_string_value(raw_value),
            )
        if char < " " and char not in "\t\n\r":
            raise GraphQLSyntaxError(
                source,
                position,
                f"Invalid character within String: {print_char(char)}.",
            )
        if (
            char == "\\"
            and char_at(body, position + 1) == '"'
            and char_at(body, position + 2) == '"'
            and char_at(body, position + 3) == '"'
        ):
            raw_value += body[chunk_start:position] + '"""'
            position += 4
            chunk_start = position
        else:
            position += 1

    raise GraphQLSyntaxError(source, position, "Unterminated string.")


def uni_char_code(a, b, c, d):
    """Convert unicode characters to integers.

    Converts four hexadecimal chars to the integer that the
    string represents. For example, uni_char_code('0','0','0','f')
    will return 15, and uni_char_code('0','0','f','f') returns 255.

    Returns a negative number on error, if a char was invalid.

    This is implemented by noting that char2hex() returns -1 on error,
    which means the result of ORing the char2hex() will also be negative.
    """
    return char2hex(a) << 12 | char2hex(b) << 8 | char2hex(c) << 4 | char2hex(d)


def char2hex(a):
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


def read_name(source: Source, start, line, col, prev) -> Token:
    """Read an alphanumeric + underscore name from the source."""
    body = source.body
    body_length = len(body)
    position = start + 1
    while position < body_length:
        char = char_at(body, position)
        if char is None or not (
            char == "_"
            or "0" <= char <= "9"
            or "A" <= char <= "Z"
            or "a" <= char <= "z"
        ):
            break
        position += 1
    return Token(TokenKind.NAME, start, position, line, col, prev, body[start:position])
