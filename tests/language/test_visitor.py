from copy import copy
from functools import partial
from typing import cast, List, Optional

from pytest import mark, raises

from graphql.language import (
    Node,
    FieldNode,
    NameNode,
    SelectionNode,
    SelectionSetNode,
    parse,
    visit,
    BREAK,
    REMOVE,
    SKIP,
    ParallelVisitor,
    Visitor,
    VisitorKeyMap,
)
from graphql.pyutils import FrozenList

from ..fixtures import kitchen_sink_query  # noqa: F401


def check_visitor_fn_args(ast, node, key, parent, path, ancestors, is_edited=False):
    assert isinstance(node, Node)

    is_root = key is None
    if is_root:
        if not is_edited:
            assert node is ast
        assert parent is None
        assert path == []
        assert ancestors == []
        return

    assert isinstance(key, (int, str))

    if isinstance(key, int):
        assert isinstance(parent, list)
        assert 0 <= key <= len(parent)
    else:
        assert isinstance(parent, Node)
        assert hasattr(parent, key)

    assert isinstance(path, list)
    assert path[-1] == key

    assert isinstance(ancestors, list)
    assert len(ancestors) == len(path) - 1

    if not is_edited:
        current_node = ast

        for i, ancestor in enumerate(ancestors):
            assert ancestor is current_node
            k = path[i]
            assert isinstance(k, (int, str))
            if isinstance(k, int):
                assert isinstance(current_node, list)
                assert 0 <= k <= len(current_node)
                current_node = current_node[k]
            else:
                assert isinstance(current_node, Node)
                assert hasattr(current_node, k)
                current_node = getattr(current_node, k)
            assert current_node is not None

        assert parent is current_node
        if isinstance(key, int):
            assert parent[key] is node
        else:
            assert getattr(parent, key) is node


check_visitor_fn_args_edited = partial(check_visitor_fn_args, is_edited=True)


def get_value(node):
    return getattr(node, "value", None)


def describe_visitor():
    def visit_with_invalid_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            visit("invalid", Visitor())  # type: ignore
        assert str(exc_info.value) == "Not an AST Node: 'invalid'."

    def visit_with_invalid_visitor():
        ast = parse("{ a }", no_location=True)

        class TestVisitor:
            def enter(self, *_args):
                pass

        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            visit(ast, TestVisitor())  # type: ignore
        assert str(exc_info.value) == "Not an AST Visitor: <TestVisitor instance>."

    def visitors_support_all_method_variants():
        class TestVisitorWithInstanceMethods(Visitor):
            def enter(self, node, *args):
                assert isinstance(self, TestVisitorWithInstanceMethods)
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"enter:{node.kind}")
                pass

            def leave(self, node, *args):
                assert isinstance(self, TestVisitorWithInstanceMethods)
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"leave:{node.kind}")
                pass

            def enter_field(self, node, *args):
                assert isinstance(self, TestVisitorWithInstanceMethods)
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"enter_field:{node.kind}")
                pass

            def leave_field(self, node, *args):
                assert isinstance(self, TestVisitorWithInstanceMethods)
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"leave_field:{node.kind}")
                pass

        class TestVisitorWithClassMethods(Visitor):
            @classmethod
            def enter(cls, node, *args):
                assert cls is TestVisitorWithClassMethods
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"enter:{node.kind}")
                pass

            @classmethod
            def leave(cls, node, *args):
                assert cls is TestVisitorWithClassMethods
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"leave:{node.kind}")
                pass

            @classmethod
            def enter_field(cls, node, *args):
                assert cls is TestVisitorWithClassMethods
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"enter_field:{node.kind}")
                pass

            @classmethod
            def leave_field(cls, node, *args):
                assert cls is TestVisitorWithClassMethods
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"leave_field:{node.kind}")
                pass

        class TestVisitorWithStaticMethods(Visitor):
            @staticmethod
            def enter(node, *args):
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"enter:{node.kind}")
                pass

            @staticmethod
            def leave(node, *args):
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"leave:{node.kind}")
                pass

            @staticmethod
            def enter_field(node, *args):
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"enter_field:{node.kind}")
                pass

            @staticmethod
            def leave_field(node, *args):
                assert isinstance(node, Node)
                assert len(args) == 4
                visited.append(f"leave_field:{node.kind}")
                pass

        for visitor_class in (
            TestVisitorWithInstanceMethods,
            TestVisitorWithClassMethods,
            TestVisitorWithStaticMethods,
        ):
            ast = parse("{ a }")
            visited: List[str] = []
            visit(ast, visitor_class())
            assert visited == [
                "enter:document",
                "enter:operation_definition",
                "enter:selection_set",
                "enter_field:field",
                "enter:name",
                "leave:name",
                "leave_field:field",
                "leave:selection_set",
                "leave:operation_definition",
                "leave:document",
            ]

    def validates_path_argument():
        ast = parse("{ a }", no_location=True)
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                visited.append(["enter", *args[3]])

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                visited.append(["leave", *args[3]])

        visit(ast, TestVisitor())
        assert visited == [
            ["enter"],
            ["enter", "definitions", 0],
            ["enter", "definitions", 0, "selection_set"],
            ["enter", "definitions", 0, "selection_set", "selections", 0],
            ["enter", "definitions", 0, "selection_set", "selections", 0, "name"],
            ["leave", "definitions", 0, "selection_set", "selections", 0, "name"],
            ["leave", "definitions", 0, "selection_set", "selections", 0],
            ["leave", "definitions", 0, "selection_set"],
            ["leave", "definitions", 0],
            ["leave"],
        ]

    def validates_ancestors_argument():
        ast = parse("{ a }", no_location=True)
        visited_nodes = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(node, key, parent, _path, ancestors):
                in_array = isinstance(key, int)
                if in_array:
                    visited_nodes.append(parent)
                visited_nodes.append(node)
                expected_ancestors = visited_nodes[0:-2]
                assert ancestors == expected_ancestors

            @staticmethod
            def leave(_node, key, _parent, _path, ancestors):
                expected_ancestors = visited_nodes[0:-2]
                assert ancestors == expected_ancestors
                in_array = isinstance(key, int)
                if in_array:
                    visited_nodes.pop()
                visited_nodes.pop()

        visit(ast, TestVisitor())

    def allows_visiting_only_specified_nodes():
        ast = parse("{ a }", no_location=True)
        visited = []

        class TestVisitor(Visitor):
            selection_set = None

            @staticmethod
            def enter_field(node, *_args):
                visited.append(["enter", node.kind])

            @staticmethod
            def leave_field(node, *_args):
                visited.append(["leave", node.kind])

        visit(ast, TestVisitor())
        assert visited == [["enter", "field"], ["leave", "field"]]

    def allows_editing_a_node_both_on_enter_and_on_leave():
        ast = parse("{ a, b, c { a, b, c } }", no_location=True)
        visited = []

        class TestVisitor(Visitor):
            selection_set = None

            def enter_operation_definition(self, *args):
                check_visitor_fn_args(ast, *args)
                node = copy(args[0])
                assert len(node.selection_set.selections) == 3
                self.selection_set = node.selection_set
                node.selection_set = SelectionSetNode(selections=[])
                visited.append("enter")
                return node

            def leave_operation_definition(self, *args):
                check_visitor_fn_args_edited(ast, *args)
                node = copy(args[0])
                assert not node.selection_set.selections
                node.selection_set = self.selection_set
                visited.append("leave")
                return node

        edited_ast = visit(ast, TestVisitor())
        assert edited_ast == ast
        assert visited == ["enter", "leave"]

    @mark.parametrize("remove_action", (REMOVE, Ellipsis), ids=("REMOVE", "Ellipsis"))
    def allows_for_editing_on_enter(remove_action):
        ast = parse("{ a, b, c { a, b, c } }", no_location=True)

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                if isinstance(node, FieldNode) and node.name.value == "b":
                    return remove_action

        edited_ast = visit(ast, TestVisitor())
        assert ast == parse("{ a, b, c { a, b, c } }", no_location=True)
        assert edited_ast == parse("{ a,    c { a,    c } }", no_location=True)

    @mark.parametrize("remove_action", (REMOVE, Ellipsis), ids=("REMOVE", "Ellipsis"))
    def allows_for_editing_on_leave(remove_action):
        ast = parse("{ a, b, c { a, b, c } }", no_location=True)

        class TestVisitor(Visitor):
            @staticmethod
            def leave(*args):
                check_visitor_fn_args_edited(ast, *args)
                node = args[0]
                if isinstance(node, FieldNode) and node.name.value == "b":
                    return remove_action

        edited_ast = visit(ast, TestVisitor())
        assert ast == parse("{ a, b, c { a, b, c } }", no_location=True)
        assert edited_ast == parse("{ a,    c { a,    c } }", no_location=True)

    @mark.parametrize("skip_action", (SKIP, False), ids=("SKIP", "False"))
    def ignores_false_returned_on_leave(skip_action):
        ast = parse("{ a, b, c { a, b, c } }", no_location=True)

        class TestVisitor(Visitor):
            @staticmethod
            def leave(*args):
                return skip_action

        returned_ast = visit(ast, TestVisitor())
        assert returned_ast == parse("{ a, b, c { a, b, c } }", no_location=True)

    def visits_edited_node():
        ast = parse("{ a { x } }", no_location=True)
        added_field = FieldNode(name=NameNode(value="__typename"))

        class TestVisitor(Visitor):
            did_visit_added_field = False

            def enter(self, *args):
                check_visitor_fn_args_edited(ast, *args)
                node = args[0]
                if isinstance(node, FieldNode) and node.name.value == "a":
                    node = copy(node)
                    assert node.selection_set
                    node.selection_set.selections = (
                        FrozenList([added_field]) + node.selection_set.selections
                    )
                    return node
                if node == added_field:
                    self.did_visit_added_field = True

        visitor = TestVisitor()
        visit(ast, visitor)
        assert visitor.did_visit_added_field

    @mark.parametrize("skip_action", (SKIP, False), ids=("SKIP", "False"))
    def allows_skipping_a_sub_tree(skip_action):
        ast = parse("{ a, b { x }, c }", no_location=True)
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])
                if kind == "field" and node.name.value == "b":
                    return skip_action

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        visit(ast, TestVisitor())
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "field", None],
            ["enter", "name", "c"],
            ["leave", "name", "c"],
            ["leave", "field", None],
            ["leave", "selection_set", None],
            ["leave", "operation_definition", None],
            ["leave", "document", None],
        ]

    @mark.parametrize("break_action", (BREAK, True), ids=("BREAK", "True"))
    def allows_early_exit_while_visiting(break_action):
        ast = parse("{ a, b { x }, c }", no_location=True)
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])
                if kind == "name" and node.value == "x":
                    return break_action

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        visit(ast, TestVisitor())
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "b"],
            ["leave", "name", "b"],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "x"],
        ]

    @mark.parametrize("break_action", (BREAK, True), ids=("BREAK", "True"))
    def allows_early_exit_while_leaving(break_action):
        ast = parse("{ a, b { x }, c }", no_location=True)
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])
                if kind == "name" and node.value == "x":
                    return break_action

        visit(ast, TestVisitor())
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "b"],
            ["leave", "name", "b"],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "x"],
            ["leave", "name", "x"],
        ]

    def allows_a_named_functions_visitor_api():
        ast = parse("{ a, b { x }, c }", no_location=True)
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter_name(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])

            @staticmethod
            def enter_selection_set(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])

            @staticmethod
            def leave_selection_set(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        visit(ast, TestVisitor())
        assert visited == [
            ["enter", "selection_set", None],
            ["enter", "name", "a"],
            ["enter", "name", "b"],
            ["enter", "selection_set", None],
            ["enter", "name", "x"],
            ["leave", "selection_set", None],
            ["enter", "name", "c"],
            ["leave", "selection_set", None],
        ]

    def experimental_visits_variables_defined_in_fragments():
        ast = parse(
            "fragment a($v: Boolean = false) on t { f }",
            no_location=True,
            experimental_fragment_variables=True,
        )
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        visit(ast, TestVisitor())
        assert visited == [
            ["enter", "document", None],
            ["enter", "fragment_definition", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["enter", "variable_definition", None],
            ["enter", "variable", None],
            ["enter", "name", "v"],
            ["leave", "name", "v"],
            ["leave", "variable", None],
            ["enter", "named_type", None],
            ["enter", "name", "Boolean"],
            ["leave", "name", "Boolean"],
            ["leave", "named_type", None],
            ["enter", "boolean_value", False],
            ["leave", "boolean_value", False],
            ["leave", "variable_definition", None],
            ["enter", "named_type", None],
            ["enter", "name", "t"],
            ["leave", "name", "t"],
            ["leave", "named_type", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "f"],
            ["leave", "name", "f"],
            ["leave", "field", None],
            ["leave", "selection_set", None],
            ["leave", "fragment_definition", None],
            ["leave", "document", None],
        ]

    # noinspection PyShadowingNames
    def visits_kitchen_sink(kitchen_sink_query):  # noqa: F811
        ast = parse(kitchen_sink_query)
        visited: List = []
        record = visited.append
        arg_stack: List = []
        push = arg_stack.append
        pop = arg_stack.pop

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                node, key, parent = args[:3]
                parent_kind = parent.kind if isinstance(parent, Node) else None
                record(["enter", node.kind, key, parent_kind])

                check_visitor_fn_args(ast, *args)
                push(args[:])

            @staticmethod
            def leave(*args):
                node, key, parent = args[:3]
                parent_kind = parent.kind if isinstance(parent, Node) else None
                record(["leave", node.kind, key, parent_kind])

                assert pop() == args

        visit(ast, TestVisitor())

        assert arg_stack == []
        assert visited == [
            ["enter", "document", None, None],
            ["enter", "operation_definition", 0, None],
            ["enter", "name", "name", "operation_definition"],
            ["leave", "name", "name", "operation_definition"],
            ["enter", "variable_definition", 0, None],
            ["enter", "variable", "variable", "variable_definition"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "variable", "variable_definition"],
            ["enter", "named_type", "type", "variable_definition"],
            ["enter", "name", "name", "named_type"],
            ["leave", "name", "name", "named_type"],
            ["leave", "named_type", "type", "variable_definition"],
            ["leave", "variable_definition", 0, None],
            ["enter", "variable_definition", 1, None],
            ["enter", "variable", "variable", "variable_definition"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "variable", "variable_definition"],
            ["enter", "named_type", "type", "variable_definition"],
            ["enter", "name", "name", "named_type"],
            ["leave", "name", "name", "named_type"],
            ["leave", "named_type", "type", "variable_definition"],
            ["enter", "enum_value", "default_value", "variable_definition"],
            ["leave", "enum_value", "default_value", "variable_definition"],
            ["leave", "variable_definition", 1, None],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "operation_definition"],
            ["enter", "field", 0, None],
            ["enter", "name", "alias", "field"],
            ["leave", "name", "alias", "field"],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "list_value", "value", "argument"],
            ["enter", "int_value", 0, None],
            ["leave", "int_value", 0, None],
            ["enter", "int_value", 1, None],
            ["leave", "int_value", 1, None],
            ["leave", "list_value", "value", "argument"],
            ["leave", "argument", 0, None],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["enter", "inline_fragment", 1, None],
            ["enter", "named_type", "type_condition", "inline_fragment"],
            ["enter", "name", "name", "named_type"],
            ["leave", "name", "name", "named_type"],
            ["leave", "named_type", "type_condition", "inline_fragment"],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "inline_fragment"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["enter", "field", 1, None],
            ["enter", "name", "alias", "field"],
            ["leave", "name", "alias", "field"],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "int_value", "value", "argument"],
            ["leave", "int_value", "value", "argument"],
            ["leave", "argument", 0, None],
            ["enter", "argument", 1, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "variable", "value", "argument"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "value", "argument"],
            ["leave", "argument", 1, None],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "variable", "value", "argument"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "value", "argument"],
            ["leave", "argument", 0, None],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["enter", "fragment_spread", 1, None],
            ["enter", "name", "name", "fragment_spread"],
            ["leave", "name", "name", "fragment_spread"],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["leave", "fragment_spread", 1, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 1, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "inline_fragment"],
            ["leave", "inline_fragment", 1, None],
            ["enter", "inline_fragment", 2, None],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "variable", "value", "argument"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "value", "argument"],
            ["leave", "argument", 0, None],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "inline_fragment"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "inline_fragment"],
            ["leave", "inline_fragment", 2, None],
            ["enter", "inline_fragment", 3, None],
            ["enter", "selection_set", "selection_set", "inline_fragment"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "inline_fragment"],
            ["leave", "inline_fragment", 3, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "operation_definition"],
            ["leave", "operation_definition", 0, None],
            ["enter", "operation_definition", 1, None],
            ["enter", "name", "name", "operation_definition"],
            ["leave", "name", "name", "operation_definition"],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "operation_definition"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "int_value", "value", "argument"],
            ["leave", "int_value", "value", "argument"],
            ["leave", "argument", 0, None],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "operation_definition"],
            ["leave", "operation_definition", 1, None],
            ["enter", "operation_definition", 2, None],
            ["enter", "name", "name", "operation_definition"],
            ["leave", "name", "name", "operation_definition"],
            ["enter", "variable_definition", 0, None],
            ["enter", "variable", "variable", "variable_definition"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "variable", "variable_definition"],
            ["enter", "named_type", "type", "variable_definition"],
            ["enter", "name", "name", "named_type"],
            ["leave", "name", "name", "named_type"],
            ["leave", "named_type", "type", "variable_definition"],
            ["leave", "variable_definition", 0, None],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "operation_definition"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "variable", "value", "argument"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "value", "argument"],
            ["leave", "argument", 0, None],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 0, None],
            ["enter", "field", 1, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "selection_set", "selection_set", "field"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 1, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "operation_definition"],
            ["leave", "operation_definition", 2, None],
            ["enter", "fragment_definition", 3, None],
            ["enter", "name", "name", "fragment_definition"],
            ["leave", "name", "name", "fragment_definition"],
            ["enter", "named_type", "type_condition", "fragment_definition"],
            ["enter", "name", "name", "named_type"],
            ["leave", "name", "name", "named_type"],
            ["leave", "named_type", "type_condition", "fragment_definition"],
            ["enter", "directive", 0, None],
            ["enter", "name", "name", "directive"],
            ["leave", "name", "name", "directive"],
            ["leave", "directive", 0, None],
            ["enter", "selection_set", "selection_set", "fragment_definition"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "variable", "value", "argument"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "value", "argument"],
            ["leave", "argument", 0, None],
            ["enter", "argument", 1, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "variable", "value", "argument"],
            ["enter", "name", "name", "variable"],
            ["leave", "name", "name", "variable"],
            ["leave", "variable", "value", "argument"],
            ["leave", "argument", 1, None],
            ["enter", "argument", 2, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "object_value", "value", "argument"],
            ["enter", "object_field", 0, None],
            ["enter", "name", "name", "object_field"],
            ["leave", "name", "name", "object_field"],
            ["enter", "string_value", "value", "object_field"],
            ["leave", "string_value", "value", "object_field"],
            ["leave", "object_field", 0, None],
            ["enter", "object_field", 1, None],
            ["enter", "name", "name", "object_field"],
            ["leave", "name", "name", "object_field"],
            ["enter", "string_value", "value", "object_field"],
            ["leave", "string_value", "value", "object_field"],
            ["leave", "object_field", 1, None],
            ["leave", "object_value", "value", "argument"],
            ["leave", "argument", 2, None],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "fragment_definition"],
            ["leave", "fragment_definition", 3, None],
            ["enter", "operation_definition", 4, None],
            ["enter", "selection_set", "selection_set", "operation_definition"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["enter", "argument", 0, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "boolean_value", "value", "argument"],
            ["leave", "boolean_value", "value", "argument"],
            ["leave", "argument", 0, None],
            ["enter", "argument", 1, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "boolean_value", "value", "argument"],
            ["leave", "boolean_value", "value", "argument"],
            ["leave", "argument", 1, None],
            ["enter", "argument", 2, None],
            ["enter", "name", "name", "argument"],
            ["leave", "name", "name", "argument"],
            ["enter", "null_value", "value", "argument"],
            ["leave", "null_value", "value", "argument"],
            ["leave", "argument", 2, None],
            ["leave", "field", 0, None],
            ["enter", "field", 1, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 1, None],
            ["leave", "selection_set", "selection_set", "operation_definition"],
            ["leave", "operation_definition", 4, None],
            ["enter", "operation_definition", 5, None],
            ["enter", "selection_set", "selection_set", "operation_definition"],
            ["enter", "field", 0, None],
            ["enter", "name", "name", "field"],
            ["leave", "name", "name", "field"],
            ["leave", "field", 0, None],
            ["leave", "selection_set", "selection_set", "operation_definition"],
            ["leave", "operation_definition", 5, None],
            ["leave", "document", None, None],
        ]


def describe_support_for_custom_ast_nodes():
    custom_ast = parse("{ a }")

    class CustomFieldNode(SelectionNode):
        __slots__ = "name", "selection_set"

        name: NameNode
        selection_set: Optional[SelectionSetNode]

    custom_selection_set = cast(FieldNode, custom_ast.definitions[0]).selection_set
    assert custom_selection_set is not None
    custom_selection_set.selections = custom_selection_set.selections + [
        CustomFieldNode(
            name=NameNode(value="b"),
            selection_set=SelectionSetNode(
                selections=CustomFieldNode(name=NameNode(value="c"))
            ),
        )
    ]

    def does_not_traverse_unknown_node_kinds():
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(node, *_args):
                visited.append(["enter", node.kind, get_value(node)])

            @staticmethod
            def leave(node, *_args):
                visited.append(["leave", node.kind, get_value(node)])

        visit(custom_ast, TestVisitor())
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "custom_field", None],
            ["leave", "custom_field", None],
            ["leave", "selection_set", None],
            ["leave", "operation_definition", None],
            ["leave", "document", None],
        ]

    def visits_only_the_specified_kind_in_visitor_key_map():
        visited = []

        visitor_key_map: VisitorKeyMap = {
            "document": ("definitions",),
            "operation_definition": ("name",),
        }

        class TestVisitor(Visitor):
            @staticmethod
            def enter(node, *_args):
                visited.append(["enter", node.kind, get_value(node)])

            @staticmethod
            def leave(node, *_args):
                visited.append(["leave", node.kind, get_value(node)])

        example_document_ast = parse(
            """
            query ExampleOperation {
              someField
            }
            """
        )

        visit(example_document_ast, TestVisitor(), visitor_key_map)
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "name", "ExampleOperation"],
            ["leave", "name", "ExampleOperation"],
            ["leave", "operation_definition", None],
            ["leave", "document", None],
        ]

    def cannot_define_visitor_with_unknown_ast_nodes():
        with raises(TypeError) as exc_info:

            class VisitorWithNonExistingNode(Visitor):
                def enter_field(self, *_args):
                    pass

                def leave_garfield(self, *_args):
                    pass

        assert str(exc_info.value) == "Invalid AST node kind: garfield."

        with raises(TypeError) as exc_info:

            class VisitorWithUnspecificNode(Visitor):
                def enter_type_system_extension(self, *_args):
                    pass

        assert str(exc_info.value) == "Invalid AST node kind: type_system_extension."


def describe_visit_in_parallel():
    @mark.parametrize("skip_action", (SKIP, False), ids=("SKIP", "False"))
    def allows_skipping_a_sub_tree(skip_action):
        # Note: nearly identical to the above test but using ParallelVisitor
        ast = parse("{ a, b { x }, c }")
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])
                if kind == "field" and node.name.value == "b":
                    return skip_action

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        visit(ast, ParallelVisitor([TestVisitor()]))
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "field", None],
            ["enter", "name", "c"],
            ["leave", "name", "c"],
            ["leave", "field", None],
            ["leave", "selection_set", None],
            ["leave", "operation_definition", None],
            ["leave", "document", None],
        ]

    @mark.parametrize("skip_action", (SKIP, False), ids=("SKIP", "False"))
    def allows_skipping_different_sub_trees(skip_action):
        ast = parse("{ a { x }, b { y} }")
        visited = []

        class TestVisitor(Visitor):
            def __init__(self, name):
                self.name = name

            def enter(self, *args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                name = self.name
                visited.append([f"no-{name}", "enter", kind, value])
                if kind == "field" and node.name.value == name:
                    return skip_action

            def leave(self, *args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                name = self.name
                visited.append([f"no-{name}", "leave", kind, value])

        visit(ast, ParallelVisitor([TestVisitor("a"), TestVisitor("b")]))
        assert visited == [
            ["no-a", "enter", "document", None],
            ["no-b", "enter", "document", None],
            ["no-a", "enter", "operation_definition", None],
            ["no-b", "enter", "operation_definition", None],
            ["no-a", "enter", "selection_set", None],
            ["no-b", "enter", "selection_set", None],
            ["no-a", "enter", "field", None],
            ["no-b", "enter", "field", None],
            ["no-b", "enter", "name", "a"],
            ["no-b", "leave", "name", "a"],
            ["no-b", "enter", "selection_set", None],
            ["no-b", "enter", "field", None],
            ["no-b", "enter", "name", "x"],
            ["no-b", "leave", "name", "x"],
            ["no-b", "leave", "field", None],
            ["no-b", "leave", "selection_set", None],
            ["no-b", "leave", "field", None],
            ["no-a", "enter", "field", None],
            ["no-b", "enter", "field", None],
            ["no-a", "enter", "name", "b"],
            ["no-a", "leave", "name", "b"],
            ["no-a", "enter", "selection_set", None],
            ["no-a", "enter", "field", None],
            ["no-a", "enter", "name", "y"],
            ["no-a", "leave", "name", "y"],
            ["no-a", "leave", "field", None],
            ["no-a", "leave", "selection_set", None],
            ["no-a", "leave", "field", None],
            ["no-a", "leave", "selection_set", None],
            ["no-b", "leave", "selection_set", None],
            ["no-a", "leave", "operation_definition", None],
            ["no-b", "leave", "operation_definition", None],
            ["no-a", "leave", "document", None],
            ["no-b", "leave", "document", None],
        ]

    @mark.parametrize("break_action", (BREAK, True), ids=("BREAK", "True"))
    def allows_early_exit_while_visiting(break_action):
        # Note: nearly identical to the above test but using ParallelVisitor.
        ast = parse("{ a, b { x }, c }")
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])
                if kind == "name" and node.value == "x":
                    return break_action

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        visit(ast, ParallelVisitor([TestVisitor()]))
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "b"],
            ["leave", "name", "b"],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "x"],
        ]

    @mark.parametrize("break_action", (BREAK, True), ids=("BREAK", "True"))
    def allows_early_exit_from_different_points(break_action):
        ast = parse("{ a { y }, b { x } }")
        visited = []

        class TestVisitor(Visitor):
            def __init__(self, name):
                self.name = name

            def enter(self, *args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                name = self.name
                visited.append([f"break-{name}", "enter", kind, value])
                if kind == "name" and node.value == name:
                    return break_action

            def leave(self, *args):
                assert self.name == "b"
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                name = self.name
                visited.append([f"break-{name}", "leave", kind, value])

        visit(ast, ParallelVisitor([TestVisitor("a"), TestVisitor("b")]))
        assert visited == [
            ["break-a", "enter", "document", None],
            ["break-b", "enter", "document", None],
            ["break-a", "enter", "operation_definition", None],
            ["break-b", "enter", "operation_definition", None],
            ["break-a", "enter", "selection_set", None],
            ["break-b", "enter", "selection_set", None],
            ["break-a", "enter", "field", None],
            ["break-b", "enter", "field", None],
            ["break-a", "enter", "name", "a"],
            ["break-b", "enter", "name", "a"],
            ["break-b", "leave", "name", "a"],
            ["break-b", "enter", "selection_set", None],
            ["break-b", "enter", "field", None],
            ["break-b", "enter", "name", "y"],
            ["break-b", "leave", "name", "y"],
            ["break-b", "leave", "field", None],
            ["break-b", "leave", "selection_set", None],
            ["break-b", "leave", "field", None],
            ["break-b", "enter", "field", None],
            ["break-b", "enter", "name", "b"],
        ]

    @mark.parametrize("break_action", (BREAK, True), ids=("BREAK", "True"))
    def allows_early_exit_while_leaving(break_action):
        # Note: nearly identical to the above test but using ParallelVisitor.
        ast = parse("{ a, b { x }, c }")
        visited = []

        class TestVisitor(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])

            @staticmethod
            def leave(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])
                if kind == "name" and node.value == "x":
                    return break_action

        visit(ast, ParallelVisitor([TestVisitor()]))
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "b"],
            ["leave", "name", "b"],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "x"],
            ["leave", "name", "x"],
        ]

    @mark.parametrize("break_action", (BREAK, True), ids=("BREAK", "True"))
    def allows_early_exit_from_leaving_different_points(break_action):
        ast = parse("{ a { y }, b { x } }")
        visited = []

        class TestVisitor(Visitor):
            def __init__(self, name):
                self.name = name

            def enter(self, *args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                name = self.name
                visited.append([f"break-{name}", "enter", kind, value])

            def leave(self, *args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                name = self.name
                visited.append([f"break-{name}", "leave", kind, value])
                if kind == "field" and node.name.value == name:
                    return break_action

        visit(ast, ParallelVisitor([TestVisitor("a"), TestVisitor("b")]))
        assert visited == [
            ["break-a", "enter", "document", None],
            ["break-b", "enter", "document", None],
            ["break-a", "enter", "operation_definition", None],
            ["break-b", "enter", "operation_definition", None],
            ["break-a", "enter", "selection_set", None],
            ["break-b", "enter", "selection_set", None],
            ["break-a", "enter", "field", None],
            ["break-b", "enter", "field", None],
            ["break-a", "enter", "name", "a"],
            ["break-b", "enter", "name", "a"],
            ["break-a", "leave", "name", "a"],
            ["break-b", "leave", "name", "a"],
            ["break-a", "enter", "selection_set", None],
            ["break-b", "enter", "selection_set", None],
            ["break-a", "enter", "field", None],
            ["break-b", "enter", "field", None],
            ["break-a", "enter", "name", "y"],
            ["break-b", "enter", "name", "y"],
            ["break-a", "leave", "name", "y"],
            ["break-b", "leave", "name", "y"],
            ["break-a", "leave", "field", None],
            ["break-b", "leave", "field", None],
            ["break-a", "leave", "selection_set", None],
            ["break-b", "leave", "selection_set", None],
            ["break-a", "leave", "field", None],
            ["break-b", "leave", "field", None],
            ["break-b", "enter", "field", None],
            ["break-b", "enter", "name", "b"],
            ["break-b", "leave", "name", "b"],
            ["break-b", "enter", "selection_set", None],
            ["break-b", "enter", "field", None],
            ["break-b", "enter", "name", "x"],
            ["break-b", "leave", "name", "x"],
            ["break-b", "leave", "field", None],
            ["break-b", "leave", "selection_set", None],
            ["break-b", "leave", "field", None],
        ]

    @mark.parametrize("remove_action", (REMOVE, Ellipsis), ids=("REMOVE", "Ellipsis"))
    def allows_for_editing_on_enter(remove_action):
        ast = parse("{ a, b, c { a, b, c } }", no_location=True)
        visited = []

        class TestVisitor1(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                if node.kind == "field" and node.name.value == "b":
                    return remove_action

        class TestVisitor2(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])

            @staticmethod
            def leave(*args):
                check_visitor_fn_args_edited(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        edited_ast = visit(ast, ParallelVisitor([TestVisitor1(), TestVisitor2()]))
        assert ast == parse("{ a, b, c { a, b, c } }", no_location=True)
        assert edited_ast == parse("{ a,    c { a,    c } }", no_location=True)
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "c"],
            ["leave", "name", "c"],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "c"],
            ["leave", "name", "c"],
            ["leave", "field", None],
            ["leave", "selection_set", None],
            ["leave", "field", None],
            ["leave", "selection_set", None],
            ["leave", "operation_definition", None],
            ["leave", "document", None],
        ]

    @mark.parametrize("remove_action", (REMOVE, Ellipsis), ids=("REMOVE", "Ellipsis"))
    def allows_for_editing_on_leave(remove_action):
        ast = parse("{ a, b, c { a, b, c } }", no_location=True)
        visited = []

        class TestVisitor1(Visitor):
            @staticmethod
            def leave(*args):
                check_visitor_fn_args_edited(ast, *args)
                node = args[0]
                if node.kind == "field" and node.name.value == "b":
                    return remove_action

        class TestVisitor2(Visitor):
            @staticmethod
            def enter(*args):
                check_visitor_fn_args(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["enter", kind, value])

            @staticmethod
            def leave(*args):
                check_visitor_fn_args_edited(ast, *args)
                node = args[0]
                kind, value = node.kind, get_value(node)
                visited.append(["leave", kind, value])

        edited_ast = visit(ast, ParallelVisitor([TestVisitor1(), TestVisitor2()]))
        assert ast == parse("{ a, b, c { a, b, c } }", no_location=True)
        assert edited_ast == parse("{ a,    c { a,    c } }", no_location=True)
        assert visited == [
            ["enter", "document", None],
            ["enter", "operation_definition", None],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "b"],
            ["leave", "name", "b"],
            ["enter", "field", None],
            ["enter", "name", "c"],
            ["leave", "name", "c"],
            ["enter", "selection_set", None],
            ["enter", "field", None],
            ["enter", "name", "a"],
            ["leave", "name", "a"],
            ["leave", "field", None],
            ["enter", "field", None],
            ["enter", "name", "b"],
            ["leave", "name", "b"],
            ["enter", "field", None],
            ["enter", "name", "c"],
            ["leave", "name", "c"],
            ["leave", "field", None],
            ["leave", "selection_set", None],
            ["leave", "field", None],
            ["leave", "selection_set", None],
            ["leave", "operation_definition", None],
            ["leave", "document", None],
        ]
