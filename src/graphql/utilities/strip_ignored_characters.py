from typing import Union, cast

from ..language import Lexer, TokenKind
from ..language.source import Source, is_source
from ..language.block_string import (
    dedent_block_string_value,
    get_block_string_indentation,
)
from ..language.lexer import is_punctuator_token_kind


def strip_ignored_characters(source: Union[str, Source]) -> str:
    """Strip characters that are ignored anyway.

    Strips characters that are not significant to the validity or execution
    of a GraphQL document:

        - UnicodeBOM
        - WhiteSpace
        - LineTerminator
        - Comment
        - Comma
        - BlockString indentation

    Note: It is required to have a delimiter character between neighboring
    non-punctuator tokes and this function always uses single space as delimiter.

    It is guaranteed that both input and output documents if parsed would result
    in the exact same AST except for nodes location.

    Warning: It is guaranteed that this function will always produce stable results.
    However, it's not guaranteed that it will stay the same between different
    releases due to bugfixes or changes in the GraphQL specification.
    """ '''

    Query example::

        query SomeQuery($foo: String!, $bar: String) {
          someField(foo: $foo, bar: $bar) {
            a
            b {
              c
              d
            }
          }
        }

    Becomes::

        query SomeQuery($foo:String!$bar:String){someField(foo:$foo bar:$bar){a b{c d}}}

    SDL example::

        """
        Type description
        """
        type Foo {
          """
          Field description
          """
          bar: String
        }

    Becomes::

        """Type description""" type Foo{"""Field description""" bar:String}
    '''
    source = cast(Source, source) if is_source(source) else Source(cast(str, source))

    body = source.body
    lexer = Lexer(source)
    stripped_body = ""
    was_last_added_token_non_punctuator = False
    while lexer.advance().kind != TokenKind.EOF:
        current_token = lexer.token
        token_kind = current_token.kind

        # Every two non-punctuator tokens should have space between them.
        # Also prevent case of non-punctuator token following by spread resulting
        # in invalid token (e.g.`1...` is invalid Float token).
        is_non_punctuator = not is_punctuator_token_kind(current_token.kind)
        if was_last_added_token_non_punctuator:
            if is_non_punctuator or current_token.kind == TokenKind.SPREAD:
                stripped_body += " "

        token_body = body[current_token.start : current_token.end]
        if token_kind == TokenKind.BLOCK_STRING:
            stripped_body += dedent_block_string(token_body)
        else:
            stripped_body += token_body

        was_last_added_token_non_punctuator = is_non_punctuator

    return stripped_body


def dedent_block_string(block_str: str) -> str:
    """Skip leading and trailing triple quotations"""
    raw_str = block_str[3:-3]
    body = dedent_block_string_value(raw_str)

    if get_block_string_indentation(body) > 0:
        body = "\n" + body

    last_char = body[-1:]
    has_trailing_quote = last_char == '"' and body[-4:] != '\\"""'
    if has_trailing_quote or last_char == "\\":
        body += "\n"

    return '"""' + body + '"""'
