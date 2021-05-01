from pytest import raises

from graphql.language import DirectiveLocation, DirectiveDefinitionNode, Node
from graphql.type import GraphQLArgument, GraphQLDirective, GraphQLInt, GraphQLString


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
            is_repeatable=True,
            ast_node=node,
        )
        assert directive.name == "test"
        assert directive.locations == locations
        assert directive.args == {"arg": arg}
        assert directive.is_repeatable is True
        assert directive.description == "test description"
        assert directive.extensions is None
        assert directive.ast_node is node

    def defines_a_directive_with_no_args():
        locations = [DirectiveLocation.QUERY]
        directive = GraphQLDirective("Foo", locations=locations)

        assert directive.name == "Foo"
        assert directive.args == {}
        assert directive.is_repeatable is False
        assert directive.extensions is None
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
        assert directive.is_repeatable is False
        assert directive.locations == locations

    def defines_a_repeatable_directive():
        locations = [DirectiveLocation.QUERY]
        directive = GraphQLDirective("Foo", is_repeatable=True, locations=locations)

        assert directive.name == "Foo"
        assert directive.args == {}
        assert directive.is_repeatable is True
        assert directive.locations == locations

    def directive_accepts_input_types_as_arguments():
        # noinspection PyTypeChecker
        directive = GraphQLDirective(
            name="Foo", locations=[], args={"arg": GraphQLString}  # type: ignore
        )
        arg = directive.args["arg"]
        assert isinstance(arg, GraphQLArgument)
        assert arg.type is GraphQLString

    def directive_accepts_strings_as_locations():
        # noinspection PyTypeChecker
        directive = GraphQLDirective(
            name="Foo", locations=["SCHEMA", "OBJECT"]  # type: ignore
        )
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

    def can_compare_with_other_source_directive():
        locations = [DirectiveLocation.QUERY]
        directive = GraphQLDirective("Foo", locations)
        assert directive == directive
        assert not directive != directive
        assert not directive == {}
        assert directive != {}
        same_directive = GraphQLDirective("Foo", locations)
        assert directive == same_directive
        assert not directive != same_directive
        other_directive = GraphQLDirective("Bar", locations)
        assert not directive == other_directive
        assert directive != other_directive
        other_locations = [DirectiveLocation.MUTATION]
        other_directive = GraphQLDirective("Foo", other_locations)
        assert not directive == other_directive
        assert directive != other_directive
        other_directive = GraphQLDirective("Foo", locations, is_repeatable=True)
        assert not directive == other_directive
        assert directive != other_directive
        other_directive = GraphQLDirective("Foo", locations, description="other")
        assert not directive == other_directive
        assert directive != other_directive

    def rejects_an_unnamed_directive():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(None, locations=[])  # type: ignore
        assert str(exc_info.value) == "Directive must be named."

    def rejects_a_directive_with_incorrectly_typed_name():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective({"bad": True}, locations=[])  # type: ignore
        assert str(exc_info.value) == "The directive name must be a string."

    def rejects_a_directive_with_incorrectly_typed_args():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=[], args=["arg"])  # type: ignore
        assert str(exc_info.value) == (
            "Foo args must be a dict with argument names as keys."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "Foo",
                locations=[],
                args={1: GraphQLArgument(GraphQLString)},  # type: ignore
            )
        assert str(exc_info.value) == (
            "Foo args must be a dict with argument names as keys."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "Foo",
                locations=[],
                args={"arg": GraphQLDirective("Bar", [])},  # type: ignore
            )
        assert str(exc_info.value) == (
            "Foo args must be GraphQLArgument or input type objects."
        )

    def rejects_a_directive_with_incorrectly_typed_repeatable_flag():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=[], is_repeatable=None)  # type: ignore
        assert str(exc_info.value) == "Foo is_repeatable flag must be True or False."

    def rejects_a_directive_with_undefined_locations():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=None)  # type: ignore
        assert str(exc_info.value) == (
            "Foo locations must be specified"
            " as a collection of DirectiveLocation enum values."
        )

    def rejects_a_directive_with_incorrectly_typed_locations():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations="bad")  # type: ignore
        assert (
            str(exc_info.value) == "Foo locations must be specified"
            " as a collection of DirectiveLocation enum values."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=["bad"])  # type: ignore
        assert str(exc_info.value) == (
            "Foo locations must be specified"
            " as a collection of DirectiveLocation enum values."
        )

    def rejects_a_directive_with_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective(
                "Foo", locations=[], description={"bad": True}  # type: ignore
            )
        assert str(exc_info.value) == "Foo description must be a string."

    def rejects_a_directive_with_incorrectly_typed_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLDirective("Foo", locations=[], ast_node=Node())  # type: ignore
        assert str(exc_info.value) == (
            "Foo AST node must be a DirectiveDefinitionNode."
        )
