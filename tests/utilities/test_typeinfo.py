from graphql.language import (
    FieldNode,
    NameNode,
    SelectionSetNode,
    parse,
    print_ast,
    visit,
    Visitor,
)
from graphql.type import get_named_type, is_composite_type
from graphql.utilities import TypeInfo, TypeInfoVisitor

from ..validation.harness import test_schema

# noinspection PyUnresolvedReferences
from ..fixtures import kitchen_sink_query  # noqa: F401


def describe_visit_with_type_info():
    def provide_exact_same_arguments_to_wrapped_visitor():
        ast = parse("{ human(id: 4) { name, pets { ... { name } }, unknown } }")

        class TestVisitor(Visitor):
            def __init__(self):
                self.args = []

            def enter(self, *args):
                self.args.append(("enter", *args))

            def leave(self, *args):
                self.args.append(("leave", *args))

        test_visitor = TestVisitor()
        visit(ast, test_visitor)

        type_info = TypeInfo(test_schema)
        wrapped_visitor = TestVisitor()
        visit(ast, TypeInfoVisitor(type_info, wrapped_visitor))

        assert test_visitor.args == wrapped_visitor.args

    def maintains_type_info_during_visit():
        visited = []

        type_info = TypeInfo(test_schema)

        ast = parse("{ human(id: 4) { name, pets { ... { name } }, unknown } }")

        # noinspection PyMethodMayBeStatic
        class TestVisitor(Visitor):
            def enter(self, *args):
                parent_type = type_info.get_parent_type()
                type_ = type_info.get_type()
                input_type = type_info.get_input_type()
                node = args[0]
                visited.append(
                    (
                        "enter",
                        node.kind,
                        node.value if node.kind == "name" else None,
                        str(parent_type) if parent_type else None,
                        str(type_) if type_ else None,
                        str(input_type) if input_type else None,
                    )
                )

            def leave(self, *args):
                parent_type = type_info.get_parent_type()
                type_ = type_info.get_type()
                input_type = type_info.get_input_type()
                node = args[0]
                visited.append(
                    (
                        "leave",
                        node.kind,
                        node.value if node.kind == "name" else None,
                        str(parent_type) if parent_type else None,
                        str(type_) if type_ else None,
                        str(input_type) if input_type else None,
                    )
                )

        visit(ast, TypeInfoVisitor(type_info, TestVisitor()))

        assert visited == [
            ("enter", "document", None, None, None, None),
            ("enter", "operation_definition", None, None, "QueryRoot", None),
            ("enter", "selection_set", None, "QueryRoot", "QueryRoot", None),
            ("enter", "field", None, "QueryRoot", "Human", None),
            ("enter", "name", "human", "QueryRoot", "Human", None),
            ("leave", "name", "human", "QueryRoot", "Human", None),
            ("enter", "argument", None, "QueryRoot", "Human", "ID"),
            ("enter", "name", "id", "QueryRoot", "Human", "ID"),
            ("leave", "name", "id", "QueryRoot", "Human", "ID"),
            ("enter", "int_value", None, "QueryRoot", "Human", "ID"),
            ("leave", "int_value", None, "QueryRoot", "Human", "ID"),
            ("leave", "argument", None, "QueryRoot", "Human", "ID"),
            ("enter", "selection_set", None, "Human", "Human", None),
            ("enter", "field", None, "Human", "String", None),
            ("enter", "name", "name", "Human", "String", None),
            ("leave", "name", "name", "Human", "String", None),
            ("leave", "field", None, "Human", "String", None),
            ("enter", "field", None, "Human", "[Pet]", None),
            ("enter", "name", "pets", "Human", "[Pet]", None),
            ("leave", "name", "pets", "Human", "[Pet]", None),
            ("enter", "selection_set", None, "Pet", "[Pet]", None),
            ("enter", "inline_fragment", None, "Pet", "Pet", None),
            ("enter", "selection_set", None, "Pet", "Pet", None),
            ("enter", "field", None, "Pet", "String", None),
            ("enter", "name", "name", "Pet", "String", None),
            ("leave", "name", "name", "Pet", "String", None),
            ("leave", "field", None, "Pet", "String", None),
            ("leave", "selection_set", None, "Pet", "Pet", None),
            ("leave", "inline_fragment", None, "Pet", "Pet", None),
            ("leave", "selection_set", None, "Pet", "[Pet]", None),
            ("leave", "field", None, "Human", "[Pet]", None),
            ("enter", "field", None, "Human", None, None),
            ("enter", "name", "unknown", "Human", None, None),
            ("leave", "name", "unknown", "Human", None, None),
            ("leave", "field", None, "Human", None, None),
            ("leave", "selection_set", None, "Human", "Human", None),
            ("leave", "field", None, "QueryRoot", "Human", None),
            ("leave", "selection_set", None, "QueryRoot", "QueryRoot", None),
            ("leave", "operation_definition", None, None, "QueryRoot", None),
            ("leave", "document", None, None, None, None),
        ]

    def maintains_type_info_during_edit():
        visited = []
        type_info = TypeInfo(test_schema)

        ast = parse("{ human(id: 4) { name, pets }, alien }")

        # noinspection PyMethodMayBeStatic
        class TestVisitor(Visitor):
            def enter(self, *args):
                parent_type = type_info.get_parent_type()
                type_ = type_info.get_type()
                input_type = type_info.get_input_type()
                node = args[0]
                visited.append(
                    (
                        "enter",
                        node.kind,
                        node.value if node.kind == "name" else None,
                        str(parent_type) if parent_type else None,
                        str(type_) if type_ else None,
                        str(input_type) if input_type else None,
                    )
                )

                # Make a query valid by adding missing selection sets.
                if (
                    node.kind == "field"
                    and not node.selection_set
                    and is_composite_type(get_named_type(type_))
                ):
                    return FieldNode(
                        alias=node.alias,
                        name=node.name,
                        arguments=node.arguments,
                        directives=node.directives,
                        selection_set=SelectionSetNode(
                            selections=[FieldNode(name=NameNode(value="__typename"))]
                        ),
                    )

            def leave(self, *args):
                parent_type = type_info.get_parent_type()
                type_ = type_info.get_type()
                input_type = type_info.get_input_type()
                node = args[0]
                visited.append(
                    (
                        "leave",
                        node.kind,
                        node.value if node.kind == "name" else None,
                        str(parent_type) if parent_type else None,
                        str(type_) if type_ else None,
                        str(input_type) if input_type else None,
                    )
                )

        edited_ast = visit(ast, TypeInfoVisitor(type_info, TestVisitor()))

        assert ast == parse("{ human(id: 4) { name, pets }, alien }")

        assert print_ast(edited_ast) == print_ast(
            parse(
                "{ human(id: 4) { name, pets { __typename } },"
                " alien { __typename } }"
            )
        )

        assert visited == [
            ("enter", "document", None, None, None, None),
            ("enter", "operation_definition", None, None, "QueryRoot", None),
            ("enter", "selection_set", None, "QueryRoot", "QueryRoot", None),
            ("enter", "field", None, "QueryRoot", "Human", None),
            ("enter", "name", "human", "QueryRoot", "Human", None),
            ("leave", "name", "human", "QueryRoot", "Human", None),
            ("enter", "argument", None, "QueryRoot", "Human", "ID"),
            ("enter", "name", "id", "QueryRoot", "Human", "ID"),
            ("leave", "name", "id", "QueryRoot", "Human", "ID"),
            ("enter", "int_value", None, "QueryRoot", "Human", "ID"),
            ("leave", "int_value", None, "QueryRoot", "Human", "ID"),
            ("leave", "argument", None, "QueryRoot", "Human", "ID"),
            ("enter", "selection_set", None, "Human", "Human", None),
            ("enter", "field", None, "Human", "String", None),
            ("enter", "name", "name", "Human", "String", None),
            ("leave", "name", "name", "Human", "String", None),
            ("leave", "field", None, "Human", "String", None),
            ("enter", "field", None, "Human", "[Pet]", None),
            ("enter", "name", "pets", "Human", "[Pet]", None),
            ("leave", "name", "pets", "Human", "[Pet]", None),
            ("enter", "selection_set", None, "Pet", "[Pet]", None),
            ("enter", "field", None, "Pet", "String!", None),
            ("enter", "name", "__typename", "Pet", "String!", None),
            ("leave", "name", "__typename", "Pet", "String!", None),
            ("leave", "field", None, "Pet", "String!", None),
            ("leave", "selection_set", None, "Pet", "[Pet]", None),
            ("leave", "field", None, "Human", "[Pet]", None),
            ("leave", "selection_set", None, "Human", "Human", None),
            ("leave", "field", None, "QueryRoot", "Human", None),
            ("enter", "field", None, "QueryRoot", "Alien", None),
            ("enter", "name", "alien", "QueryRoot", "Alien", None),
            ("leave", "name", "alien", "QueryRoot", "Alien", None),
            ("enter", "selection_set", None, "Alien", "Alien", None),
            ("enter", "field", None, "Alien", "String!", None),
            ("enter", "name", "__typename", "Alien", "String!", None),
            ("leave", "name", "__typename", "Alien", "String!", None),
            ("leave", "field", None, "Alien", "String!", None),
            ("leave", "selection_set", None, "Alien", "Alien", None),
            ("leave", "field", None, "QueryRoot", "Alien", None),
            ("leave", "selection_set", None, "QueryRoot", "QueryRoot", None),
            ("leave", "operation_definition", None, None, "QueryRoot", None),
            ("leave", "document", None, None, None, None),
        ]
