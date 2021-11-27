from graphql.language import (
    FieldNode,
    NameNode,
    Node,
    OperationDefinitionNode,
    SelectionSetNode,
    parse,
    parse_value,
    print_ast,
    visit,
    Visitor,
)
from graphql.type import GraphQLSchema, get_named_type, is_composite_type
from graphql.utilities import TypeInfo, TypeInfoVisitor, build_schema

from ..fixtures import kitchen_sink_query  # noqa: F401


test_schema = build_schema(
    """
    interface Pet {
      name: String
    }

    type Dog implements Pet {
      name: String
    }

    type Cat implements Pet {
      name: String
    }

    type Human {
      name: String
      pets: [Pet]
    }

    type Alien {
      name(surname: Boolean): String
    }

    type QueryRoot {
      human(id: ID): Human
      alien: Alien
    }

    schema {
      query: QueryRoot
    }
    """
)


def describe_type_info():
    schema = GraphQLSchema()

    def allow_all_methods_to_be_called_before_entering_any_mode():
        type_info = TypeInfo(schema)

        assert type_info.get_type() is None
        assert type_info.get_parent_type() is None
        assert type_info.get_input_type() is None
        assert type_info.get_parent_input_type() is None
        assert type_info.get_field_def() is None
        assert type_info.get_default_value() is None
        assert type_info.get_directive() is None
        assert type_info.get_argument() is None
        assert type_info.get_enum_value() is None


def describe_visit_with_type_info():
    def supports_different_operation_types():
        schema = build_schema(
            """
            schema {
              query: QueryRoot
              mutation: MutationRoot
              subscription: SubscriptionRoot
            }

            type QueryRoot {
              foo: String
            }

            type MutationRoot {
              bar: String
            }

            type SubscriptionRoot {
              baz: String
            }
            """
        )
        ast = parse(
            """
            query { foo }
            mutation { bar }
            subscription { baz }
            """
        )

        class TestVisitor(Visitor):
            def __init__(self):
                super().__init__()
                self.root_types = {}

            def enter_operation_definition(self, node: OperationDefinitionNode, *_args):
                self.root_types[node.operation.value] = str(type_info.get_type())

        type_info = TypeInfo(schema)
        test_visitor = TestVisitor()
        assert visit(ast, TypeInfoVisitor(type_info, test_visitor))

        assert test_visitor.root_types == {
            "query": "QueryRoot",
            "mutation": "MutationRoot",
            "subscription": "SubscriptionRoot",
        }

    def provide_exact_same_arguments_to_wrapped_visitor():
        ast = parse("{ human(id: 4) { name, pets { ... { name } }, unknown } }")

        class TestVisitor(Visitor):
            def __init__(self):
                super().__init__()
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

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
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

            @staticmethod
            def leave(*args):
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

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
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

            @staticmethod
            def leave(*args):
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

    def supports_traversal_of_input_values():
        visited = []

        schema = build_schema(
            """
            input ComplexInput {
              stringListField: [String]
            }
            """
        )
        complex_input_type = schema.get_type("ComplexInput")
        assert complex_input_type is not None
        type_info = TypeInfo(schema, complex_input_type)

        ast = parse_value('{ stringListField: ["foo"] }')

        class TestVisitor(Visitor):
            @staticmethod
            def enter(node: Node, *_args):
                type_ = type_info.get_input_type()
                visited.append(
                    (
                        "enter",
                        node.kind,
                        node.value if isinstance(node, NameNode) else None,
                        str(type_),
                    )
                )

            @staticmethod
            def leave(node: Node, *_args):
                type_ = type_info.get_input_type()
                visited.append(
                    (
                        "leave",
                        node.kind,
                        node.value if isinstance(node, NameNode) else None,
                        str(type_),
                    )
                )

        visit(ast, TypeInfoVisitor(type_info, TestVisitor()))

        assert visited == [
            ("enter", "object_value", None, "ComplexInput"),
            ("enter", "object_field", None, "[String]"),
            ("enter", "name", "stringListField", "[String]"),
            ("leave", "name", "stringListField", "[String]"),
            ("enter", "list_value", None, "String"),
            ("enter", "string_value", None, "String"),
            ("leave", "string_value", None, "String"),
            ("leave", "list_value", None, "String"),
            ("leave", "object_field", None, "[String]"),
            ("leave", "object_value", None, "ComplexInput"),
        ]

    def supports_traversal_of_selection_sets():
        visited = []

        human_type = test_schema.get_type("Human")
        assert human_type is not None
        type_info = TypeInfo(test_schema, human_type)

        ast = parse("{ name, pets { name } }")
        operation_node = ast.definitions[0]
        assert isinstance(operation_node, OperationDefinitionNode)

        class TestVisitor(Visitor):
            @staticmethod
            def enter(node: Node, *_args):
                parent_type = type_info.get_parent_type()
                type_ = type_info.get_type()
                visited.append(
                    (
                        "enter",
                        node.kind,
                        node.value if isinstance(node, NameNode) else None,
                        str(parent_type),
                        str(type_),
                    )
                )

            @staticmethod
            def leave(node: Node, *_args):
                parent_type = type_info.get_parent_type()
                type_ = type_info.get_type()
                visited.append(
                    (
                        "leave",
                        node.kind,
                        node.value if isinstance(node, NameNode) else None,
                        str(parent_type),
                        str(type_),
                    )
                )

        visit(operation_node.selection_set, TypeInfoVisitor(type_info, TestVisitor()))

        assert visited == [
            ("enter", "selection_set", None, "Human", "Human"),
            ("enter", "field", None, "Human", "String"),
            ("enter", "name", "name", "Human", "String"),
            ("leave", "name", "name", "Human", "String"),
            ("leave", "field", None, "Human", "String"),
            ("enter", "field", None, "Human", "[Pet]"),
            ("enter", "name", "pets", "Human", "[Pet]"),
            ("leave", "name", "pets", "Human", "[Pet]"),
            ("enter", "selection_set", None, "Pet", "[Pet]"),
            ("enter", "field", None, "Pet", "String"),
            ("enter", "name", "name", "Pet", "String"),
            ("leave", "name", "name", "Pet", "String"),
            ("leave", "field", None, "Pet", "String"),
            ("leave", "selection_set", None, "Pet", "[Pet]"),
            ("leave", "field", None, "Human", "[Pet]"),
            ("leave", "selection_set", None, "Human", "Human"),
        ]
