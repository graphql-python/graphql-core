"""AST concatenation"""

from __future__ import annotations

from itertools import chain
from typing import Collection

from ..language.ast import DocumentNode

__all__ = ["concat_ast"]


def concat_ast(asts: Collection[DocumentNode]) -> DocumentNode:
    """Concat ASTs.

    Provided a collection of ASTs, presumably each from different files, concatenate
    the ASTs together into batched AST, useful for validating many GraphQL source files
    which together represent one conceptual application.
    """
    all_definitions = chain.from_iterable(doc.definitions for doc in asts)
    return DocumentNode(definitions=tuple(all_definitions))
