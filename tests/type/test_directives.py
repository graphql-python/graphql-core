from pytest import raises

from graphql.language import DirectiveLocation, DirectiveDefinitionNode, Node
from graphql.type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLString,
    GraphQLSkipDirective,
    is_directive,
    is_specified_directive,
)


def describe_graphql_directive():
    def can_create_instance():
        arg = GraphQLArgument(GraphQLString, description="arg description")
        node = DirectiveDefinitionNode()
        locations = [DirectiveLocation.SCHEMA, DirectiveLocation.OBJECT]
        directive = GraphQLDirective(
            name="test",
            locations=[DirectiveLocation.SCHEMA, DirectiveLocation.OBJECT],
            args={"arg": arg},
            description="test description",
            ast_node=node,
        )
        assert directive.name == "test"
        assert directive.locations == locations
        assert directive.args == {"arg": arg}
        assert directive.description == "test description"
        assert directive.ast_node is node

    def has_str():
        directive = GraphQLDirective("test", [])
        assert str(directive) == "@test"

    def has_repr():
        directive = GraphQLDirective("test", [])
        assert repr(directive) == "<GraphQLDirective(@test)>"

    def accepts_strings_as_locations():
        # noinspection PyTypeChecker
        directive = GraphQLDirective(
            name="test", locations=["SCHEMA", "OBJECT"]
        )  # type: ignore
        assert directive.locations == [
            DirectiveLocation.SCHEMA,
            DirectiveLocation.OBJECT,
        ]

    def accepts_input_types_as_arguments():
        # noinspection PyTypeChecker
        directive = GraphQLDirective(
            name="test", locations=[], args={"arg": GraphQLString}
        )  # type: ignore
        arg = directive.args["arg"]
        assert isinstance(arg, GraphQLArgument)
        assert arg.type is GraphQLString

    def does_not_accept_a_bad_name():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(None, locations=[])  # type: ignore
        assert str(exc_info.value) == "Directive must be named."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective({"bad": True}, locations=[])  # type: ignore
        assert str(exc_info.value) == "The directive name must be a string."

    def does_not_accept_bad_locations():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("test", locations="bad")  # type: ignore
        assert str(exc_info.value) == "test locations must be a list/tuple."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("test", locations=["bad"])  # type: ignore
        assert str(exc_info.value) == (
            "test locations must be DirectiveLocation objects."
        )

    def does_not_accept_bad_args():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("test", locations=[], args=["arg"])  # type: ignore
        assert str(exc_info.value) == (
            "test args must be a dict with argument names as keys."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "test", locations=[], args={1: GraphQLArgument(GraphQLString)}
            )  # type: ignore
        assert str(exc_info.value) == (
            "test args must be a dict with argument names as keys."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "test", locations=[], args={"arg": GraphQLDirective("test", [])}
            )  # type: ignore
        assert str(exc_info.value) == (
            "test args must be GraphQLArgument or input type objects."
        )

    def does_not_accept_a_bad_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "test", locations=[], description={"bad": True}
            )  # type: ignore
        assert str(exc_info.value) == "test description must be a string."

    def does_not_accept_a_bad_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("test", locations=[], ast_node=Node())  # type: ignore
        assert str(exc_info.value) == (
            "test AST node must be a DirectiveDefinitionNode."
        )


def describe_directive_predicates():
    def describe_is_directive():
        def returns_true_for_directive():
            directive = GraphQLDirective("test", [])
            assert is_directive(directive) is True

        def returns_false_for_type_class_rather_than_instance():
            assert is_directive(GraphQLDirective) is False

        def returns_false_for_other_instances():
            assert is_directive(GraphQLString) is False

        def returns_false_for_random_garbage():
            assert is_directive(None) is False
            assert is_directive({"what": "is this"}) is False

    def describe_is_specified_directive():
        def returns_true_for_specified_directive():
            assert is_specified_directive(GraphQLSkipDirective) is True

        def returns_false_for_unspecified_directive():
            directive = GraphQLDirective("test", [])
            assert is_specified_directive(directive) is False
