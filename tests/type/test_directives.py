from pytest import raises

from graphql.language import DirectiveLocation, DirectiveDefinitionNode, Node
from graphql.type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLInt,
    GraphQLString,
    GraphQLSkipDirective,
    is_directive,
    is_specified_directive,
)


def describe_type_system_directive():
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

    def defines_a_directive_with_no_args():
        locations = [DirectiveLocation.QUERY]
        directive = GraphQLDirective("Foo", locations=locations)

        assert directive.name == "Foo"
        assert directive.args == {}
        assert directive.locations == locations

    def defines_a_directive_with_multiple_args():
        args = {
            "foo": GraphQLArgument(GraphQLString),
            "bar": GraphQLArgument(GraphQLInt),
        }
        locations = [DirectiveLocation.QUERY]
        directive = GraphQLDirective("Foo", locations=locations, args=args)

        assert directive.name == "Foo"
        assert directive.args == args
        assert directive.locations == locations

    def directive_accepts_input_types_as_arguments():
        # noinspection PyTypeChecker
        directive = GraphQLDirective(
            name="Foo", locations=[], args={"arg": GraphQLString}
        )  # type: ignore
        arg = directive.args["arg"]
        assert isinstance(arg, GraphQLArgument)
        assert arg.type is GraphQLString

    def directive_accepts_strings_as_locations():
        # noinspection PyTypeChecker
        directive = GraphQLDirective(
            name="Foo", locations=["SCHEMA", "OBJECT"]
        )  # type: ignore
        assert directive.locations == [
            DirectiveLocation.SCHEMA,
            DirectiveLocation.OBJECT,
        ]

    def directive_has_str():
        directive = GraphQLDirective("foo", [])
        assert str(directive) == "@foo"

    def directive_has_repr():
        directive = GraphQLDirective("foo", [])
        assert repr(directive) == "<GraphQLDirective(@foo)>"

    def reject_an_unnamed_directivce():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(None, locations=[])  # type: ignore
        assert str(exc_info.value) == "Directive must be named."

    def reject_directive_with_incorrectly_typed_name():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective({"bad": True}, locations=[])  # type: ignore
        assert str(exc_info.value) == "The directive name must be a string."

    def reject_directive_with_incorrectly_typed_args():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=[], args=["arg"])  # type: ignore
        assert str(exc_info.value) == (
            "Foo args must be a dict with argument names as keys."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "Foo", locations=[], args={1: GraphQLArgument(GraphQLString)}
            )  # type: ignore
        assert str(exc_info.value) == (
            "Foo args must be a dict with argument names as keys."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "Foo", locations=[], args={"arg": GraphQLDirective("Bar", [])}
            )  # type: ignore
        assert str(exc_info.value) == (
            "Foo args must be GraphQLArgument or input type objects."
        )

    def reject_directive_with_undefined_locations():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=None)  # type: ignore
        assert str(exc_info.value) == "Foo locations must be a list/tuple."

    def recect_directive_with_incorrectly_typed_locations():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations="bad")  # type: ignore
        assert str(exc_info.value) == "Foo locations must be a list/tuple."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=["bad"])  # type: ignore
        assert str(exc_info.value) == (
            "Foo locations must be DirectiveLocation objects."
        )

    def reject_directive_with_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "Foo", locations=[], description={"bad": True}
            )  # type: ignore
        assert str(exc_info.value) == "Foo description must be a string."

    def reject_directive_with_incorrectly_typed_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=[], ast_node=Node())  # type: ignore
        assert str(exc_info.value) == (
            "Foo AST node must be a DirectiveDefinitionNode."
        )


def describe_directive_predicates():
    def describe_is_directive():
        def returns_true_for_directive():
            directive = GraphQLDirective("Foo", [])
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
            directive = GraphQLDirective("Foo", [])
            assert is_specified_directive(directive) is False
