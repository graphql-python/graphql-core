from graphql import parse
from graphql.language import visit, Visitor, ParallelVisitor

from ..fixtures import big_schema_sdl  # noqa: F401


class TestVisitor(Visitor):
    @staticmethod
    def enter(*args):
        pass

    @staticmethod
    def leave(*args):
        pass


def test_visit_all_ast_nodes(benchmark, big_schema_sdl):  # noqa: F811
    document_ast = parse(big_schema_sdl)
    visitor = TestVisitor()
    benchmark(lambda: visit(document_ast, visitor))


def test_visit_all_ast_nodes_in_parallel(benchmark, big_schema_sdl):  # noqa: F811
    document_ast = parse(big_schema_sdl)
    visitor = TestVisitor()
    parallel_visitor = ParallelVisitor([visitor] * 50)
    benchmark(lambda: visit(document_ast, parallel_visitor))
