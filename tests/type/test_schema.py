from pytest import raises

from graphql.language import DirectiveLocation
from graphql.type import (
    GraphQLField,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    GraphQLInputObjectType,
    GraphQLInputField,
    GraphQLDirective,
    GraphQLArgument,
    GraphQLList,
)

InterfaceType = GraphQLInterfaceType(
    "Interface", {"fieldName": GraphQLField(GraphQLString)}
)

DirectiveInputType = GraphQLInputObjectType(
    "DirInput", {"field": GraphQLInputField(GraphQLString)}
)

WrappedDirectiveInputType = GraphQLInputObjectType(
    "WrappedDirInput", {"field": GraphQLInputField(GraphQLString)}
)

Directive = GraphQLDirective(
    name="dir",
    locations=[DirectiveLocation.OBJECT],
    args={
        "arg": GraphQLArgument(DirectiveInputType),
        "argList": GraphQLArgument(GraphQLList(WrappedDirectiveInputType)),
    },
)

Schema = GraphQLSchema(
    query=GraphQLObjectType(
        "Query", {"getObject": GraphQLField(InterfaceType, resolve=lambda: {})}
    ),
    directives=[Directive],
)


def describe_type_system_schema():
    def describe_type_map():
        def includes_input_types_only_used_in_directives():
            assert "DirInput" in Schema.type_map
            assert "WrappedDirInput" in Schema.type_map

    def describe_validity():
        def describe_when_not_assumed_valid():
            def configures_the_schema_to_still_needing_validation():
                # noinspection PyProtectedMember
                assert GraphQLSchema(assume_valid=False)._validation_errors is None

            def checks_the_configuration_for_mistakes():
                with raises(Exception):
                    # noinspection PyTypeChecker
                    GraphQLSchema(lambda: None)
                with raises(Exception):
                    GraphQLSchema(types={})
                with raises(Exception):
                    GraphQLSchema(directives={})

        def describe_when_assumed_valid():
            def configures_the_schema_to_have_no_errors():
                # noinspection PyProtectedMember
                assert GraphQLSchema(assume_valid=True)._validation_errors == []
