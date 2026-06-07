from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from graphql.utilities import (
    ResolvedDirective,
    ResolvedDirectiveArgument,
    ResolvedEnumValue,
    ResolvedField,
    ResolvedFieldArgument,
    ResolvedInputField,
    ResolvedNamedType,
    build_schema,
    resolve_schema_coordinate,
)

if TYPE_CHECKING:
    from graphql.type import (
        GraphQLDirective,
        GraphQLEnumType,
        GraphQLInputObjectType,
        GraphQLNamedType,
        GraphQLObjectType,
    )

schema = build_schema("""
    type Query {
      searchBusiness(criteria: SearchCriteria!): [Business]
    }

    input SearchCriteria {
      name: String
      filter: SearchFilter
    }

    enum SearchFilter {
      OPEN_NOW
      DELIVERS_TAKEOUT
      VEGETARIAN_MENU
    }

    type Business {
      id: ID
      name: String
      email: String @private(scope: "loggedIn")
    }

    directive @private(scope: String!) on FIELD_DEFINITION
    """)


def describe_resolve_schema_coordinate():
    def resolves_a_named_type():
        assert resolve_schema_coordinate(schema, "Business") == ResolvedNamedType(
            cast("GraphQLNamedType", schema.get_type("Business"))
        )

        assert resolve_schema_coordinate(schema, "String") == ResolvedNamedType(
            cast("GraphQLNamedType", schema.get_type("String"))
        )

        assert resolve_schema_coordinate(schema, "private") is None

        assert resolve_schema_coordinate(schema, "Unknown") is None

    def resolves_a_type_field():
        type_ = cast("GraphQLObjectType", schema.get_type("Business"))
        field = type_.fields["name"]
        assert resolve_schema_coordinate(schema, "Business.name") == ResolvedField(
            type_, field
        )

        assert resolve_schema_coordinate(schema, "Business.unknown") is None

        with pytest.raises(TypeError) as exc_info:
            resolve_schema_coordinate(schema, "Unknown.field")
        assert (
            str(exc_info.value)
            == "Expected 'Unknown' to be defined as a type in the schema."
        )

        with pytest.raises(TypeError) as exc_info:
            resolve_schema_coordinate(schema, "String.field")
        assert str(exc_info.value) == (
            "Expected 'String' to be an Enum, Input Object, Object or Interface type."
        )

    def resolves_an_input_field():
        type_ = cast("GraphQLInputObjectType", schema.get_type("SearchCriteria"))
        input_field = type_.fields["filter"]
        assert resolve_schema_coordinate(
            schema, "SearchCriteria.filter"
        ) == ResolvedInputField(type_, input_field)

        assert resolve_schema_coordinate(schema, "SearchCriteria.unknown") is None

    def resolves_an_enum_value():
        type_ = cast("GraphQLEnumType", schema.get_type("SearchFilter"))
        enum_value = type_.values["OPEN_NOW"]
        assert resolve_schema_coordinate(
            schema, "SearchFilter.OPEN_NOW"
        ) == ResolvedEnumValue(type_, enum_value)

        assert resolve_schema_coordinate(schema, "SearchFilter.UNKNOWN") is None

    def resolves_a_field_argument():
        type_ = cast("GraphQLObjectType", schema.get_type("Query"))
        field = type_.fields["searchBusiness"]
        field_argument = field.args["criteria"]
        assert resolve_schema_coordinate(
            schema, "Query.searchBusiness(criteria:)"
        ) == ResolvedFieldArgument(type_, field, field_argument)

        assert resolve_schema_coordinate(schema, "Business.name(unknown:)") is None

        with pytest.raises(TypeError) as exc_info:
            resolve_schema_coordinate(schema, "Unknown.field(arg:)")
        assert (
            str(exc_info.value)
            == "Expected 'Unknown' to be defined as a type in the schema."
        )

        with pytest.raises(TypeError) as exc_info:
            resolve_schema_coordinate(schema, "Business.unknown(arg:)")
        assert str(exc_info.value) == (
            "Expected 'unknown' to exist as a field of type 'Business' in the schema."
        )

        with pytest.raises(TypeError) as exc_info:
            resolve_schema_coordinate(schema, "SearchCriteria.name(arg:)")
        assert (
            str(exc_info.value)
            == "Expected 'SearchCriteria' to be an object type or interface type."
        )

    def resolves_a_directive():
        assert resolve_schema_coordinate(schema, "@private") == ResolvedDirective(
            cast("GraphQLDirective", schema.get_directive("private"))
        )

        assert resolve_schema_coordinate(schema, "@deprecated") == ResolvedDirective(
            cast("GraphQLDirective", schema.get_directive("deprecated"))
        )

        assert resolve_schema_coordinate(schema, "@unknown") is None

        assert resolve_schema_coordinate(schema, "@Business") is None

    def resolves_a_directive_argument():
        directive = cast("GraphQLDirective", schema.get_directive("private"))
        directive_argument = directive.args["scope"]
        assert resolve_schema_coordinate(
            schema, "@private(scope:)"
        ) == ResolvedDirectiveArgument(directive, directive_argument)

        assert resolve_schema_coordinate(schema, "@private(unknown:)") is None

        with pytest.raises(TypeError) as exc_info:
            resolve_schema_coordinate(schema, "@unknown(arg:)")
        assert (
            str(exc_info.value)
            == "Expected 'unknown' to be defined as a directive in the schema."
        )


# NOTE: the following are not required for spec compliance; resolution
# of meta-fields is implementation-defined.
#
# These tests are here to ensure a change of behavior will only be made
# in a semver-major release of GraphQL.js.
def describe_resolve_schema_coordinate_meta_fields_and_introspection_types():
    def resolves_a_meta_field():
        type_ = cast("GraphQLObjectType", schema.get_type("Business"))
        field = schema.get_field(type_, "__typename")
        assert field
        assert resolve_schema_coordinate(
            schema, "Business.__typename"
        ) == ResolvedField(type_, field)

    def resolves_a_meta_field_argument():
        type_ = cast("GraphQLObjectType", schema.get_type("Query"))
        field = schema.get_field(type_, "__type")
        assert field
        field_argument = field.args["name"]
        assert resolve_schema_coordinate(
            schema, "Query.__type(name:)"
        ) == ResolvedFieldArgument(type_, field, field_argument)

    def resolves_an_introspection_type():
        assert resolve_schema_coordinate(schema, "__Type") == ResolvedNamedType(
            cast("GraphQLNamedType", schema.get_type("__Type"))
        )

    def resolves_an_introspection_type_field():
        type_ = cast("GraphQLObjectType", schema.get_type("__Directive"))
        field = type_.fields["name"]
        assert resolve_schema_coordinate(schema, "__Directive.name") == ResolvedField(
            type_, field
        )

    def resolves_an_introspection_type_enum_value():
        type_ = cast("GraphQLEnumType", schema.get_type("__DirectiveLocation"))
        enum_value = type_.values["INLINE_FRAGMENT"]
        assert resolve_schema_coordinate(
            schema, "__DirectiveLocation.INLINE_FRAGMENT"
        ) == ResolvedEnumValue(type_, enum_value)
