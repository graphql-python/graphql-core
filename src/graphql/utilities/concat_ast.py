"""AST concatenation"""

from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING

from ..language.ast import DocumentNode

if TYPE_CHECKING:
    from collections.abc import Collection

__all__ = ["concat_ast"]


def concat_ast(asts: Collection[DocumentNode]) -> DocumentNode:
    """Concat ASTs.

    Provided a collection of ASTs, presumably each from different files, concatenate
    the ASTs together into batched AST, useful for validating many GraphQL source files
    which together represent one conceptual application.

    :param asts: Document ASTs to concatenate.
    :returns: A document AST containing all definitions from the provided documents.

    >>> from graphql import concat_ast, parse
    >>> document = concat_ast(
    ...     [parse('type Query { a: String }'), parse('type User { id: ID }')])
    >>> len(document.definitions)
    2
    """
    all_definitions = chain.from_iterable(doc.definitions for doc in asts)
    return DocumentNode(definitions=tuple(all_definitions))
