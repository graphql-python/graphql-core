from graphql.language import DirectiveLocation
from graphql.pyutils import dedent
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
    GraphQLType,
    GraphQLNullableType,
    GraphQLInputField,
    GraphQLDirective,
    assert_object_type,
)
from graphql.utilities import build_schema, print_schema, print_introspection_schema


def print_for_test(schema: GraphQLSchema) -> str:
    schema_text = print_schema(schema)
    # keep print_schema and build_schema in sync
    assert print_schema(build_schema(schema_text)) == schema_text
    return schema_text


def print_single_field_schema(field: GraphQLField):
    query = GraphQLObjectType(name="Query", fields={"singleField": field})
    return print_for_test(GraphQLSchema(query=query))


def list_of(type_: GraphQLType):
    return GraphQLList(type_)


def non_null(type_: GraphQLNullableType):
    return GraphQLNonNull(type_)


def describe_type_system_printer():
    def prints_string_field():
        output = print_single_field_schema(GraphQLField(GraphQLString))
        assert output == dedent(
            """
            type Query {
              singleField: String
            }
            """
        )

    def prints_list_of_string_field():
        output = print_single_field_schema(GraphQLField(list_of(GraphQLString)))
        assert output == dedent(
            """
            type Query {
              singleField: [String]
            }
            """
        )

    def prints_non_null_string_field():
        output = print_single_field_schema(GraphQLField(non_null(GraphQLString)))
        assert output == dedent(
            """
            type Query {
              singleField: String!
            }
            """
        )

    def prints_non_null_list_of_string_field():
        output = print_single_field_schema(
            GraphQLField(non_null(list_of(GraphQLString)))
        )
        assert output == dedent(
            """
            type Query {
              singleField: [String]!
            }
            """
        )

    def prints_list_of_non_null_string_field():
        output = print_single_field_schema(
            GraphQLField((list_of(non_null(GraphQLString))))
        )
        assert output == dedent(
            """
            type Query {
              singleField: [String!]
            }
            """
        )

    def prints_non_null_list_of_non_null_string_field():
        output = print_single_field_schema(
            GraphQLField(non_null(list_of(non_null(GraphQLString))))
        )
        assert output == dedent(
            """
            type Query {
              singleField: [String!]!
            }
            """
        )

    def prints_object_field():
        foo_type = GraphQLObjectType(
            name="Foo", fields={"str": GraphQLField(GraphQLString)}
        )

        schema = GraphQLSchema(types=[foo_type])
        output = print_for_test(schema)
        assert output == dedent(
            """
            type Foo {
              str: String
            }
            """
        )

    def prints_string_field_with_int_arg():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString, args={"argOne": GraphQLArgument(GraphQLInt)}
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int): String
            }
            """
        )

    def prints_string_field_with_int_arg_with_default():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={"argOne": GraphQLArgument(GraphQLInt, default_value=2)},
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int = 2): String
            }
            """
        )

    def prints_string_field_with_string_arg_with_default():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={
                    "argOne": GraphQLArgument(
                        GraphQLString, default_value="tes\t de\fault"
                    )
                },
            )
        )
        assert output == dedent(
            r"""
            type Query {
              singleField(argOne: String = "tes\t de\fault"): String
            }
            """
        )

    def prints_string_field_with_int_arg_with_default_null():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={"argOne": GraphQLArgument(GraphQLInt, default_value=None)},
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int = null): String
            }
            """
        )

    def prints_string_field_with_non_null_int_arg():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={"argOne": GraphQLArgument(non_null(GraphQLInt))},
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int!): String
            }
            """
        )

    def prints_string_field_with_multiple_args():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={
                    "argOne": GraphQLArgument(GraphQLInt),
                    "argTwo": GraphQLArgument(GraphQLString),
                },
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int, argTwo: String): String
            }
            """
        )

    def prints_string_field_with_multiple_args_first_is_default():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={
                    "argOne": GraphQLArgument(GraphQLInt, default_value=1),
                    "argTwo": GraphQLArgument(GraphQLString),
                    "argThree": GraphQLArgument(GraphQLBoolean),
                },
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int = 1, argTwo: String, argThree: Boolean): String
            }
            """
        )

    def prints_string_field_with_multiple_args_second_is_default():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={
                    "argOne": GraphQLArgument(GraphQLInt),
                    "argTwo": GraphQLArgument(GraphQLString, default_value="foo"),
                    "argThree": GraphQLArgument(GraphQLBoolean),
                },
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int, argTwo: String = "foo", argThree: Boolean): String
            }
            """  # noqa: E501
        )

    def prints_string_field_with_multiple_args_last_is_default():
        output = print_single_field_schema(
            GraphQLField(
                type_=GraphQLString,
                args={
                    "argOne": GraphQLArgument(GraphQLInt),
                    "argTwo": GraphQLArgument(GraphQLString),
                    "argThree": GraphQLArgument(GraphQLBoolean, default_value=False),
                },
            )
        )
        assert output == dedent(
            """
            type Query {
              singleField(argOne: Int, argTwo: String, argThree: Boolean = false): String
            }
            """  # noqa: E501
        )

    def prints_custom_query_root_type():
        custom_query_type = GraphQLObjectType(
            "CustomQueryType", {"bar": GraphQLField(GraphQLString)}
        )

        schema = GraphQLSchema(custom_query_type)

        output = print_for_test(schema)
        assert output == dedent(
            """
            schema {
              query: CustomQueryType
            }

            type CustomQueryType {
              bar: String
            }
            """
        )

    def prints_interface():
        foo_type = GraphQLInterfaceType(
            name="Foo", fields={"str": GraphQLField(GraphQLString)}
        )

        bar_type = GraphQLObjectType(
            name="Bar",
            fields={"str": GraphQLField(GraphQLString)},
            interfaces=[foo_type],
        )

        schema = GraphQLSchema(types=[bar_type])
        output = print_for_test(schema)
        assert output == dedent(
            """
            type Bar implements Foo {
              str: String
            }

            interface Foo {
              str: String
            }
            """
        )

    def prints_multiple_interfaces():
        foo_type = GraphQLInterfaceType(
            name="Foo", fields={"str": GraphQLField(GraphQLString)}
        )

        baaz_type = GraphQLInterfaceType(
            name="Baaz", fields={"int": GraphQLField(GraphQLInt)}
        )

        bar_type = GraphQLObjectType(
            name="Bar",
            fields={
                "str": GraphQLField(GraphQLString),
                "int": GraphQLField(GraphQLInt),
            },
            interfaces=[foo_type, baaz_type],
        )

        schema = GraphQLSchema(types=[bar_type])
        output = print_for_test(schema)
        assert output == dedent(
            """
            interface Baaz {
              int: Int
            }

            type Bar implements Foo & Baaz {
              str: String
              int: Int
            }

            interface Foo {
              str: String
            }
            """
        )

    def prints_unions():
        foo_type = GraphQLObjectType(
            name="Foo", fields={"bool": GraphQLField(GraphQLBoolean)}
        )

        bar_type = GraphQLObjectType(
            name="Bar", fields={"str": GraphQLField(GraphQLString)}
        )

        single_union = GraphQLUnionType(name="SingleUnion", types=[foo_type])

        multiple_union = GraphQLUnionType(
            name="MultipleUnion", types=[foo_type, bar_type]
        )

        schema = GraphQLSchema(types=[single_union, multiple_union])
        output = print_for_test(schema)
        assert output == dedent(
            """
            type Bar {
              str: String
            }

            type Foo {
              bool: Boolean
            }

            union MultipleUnion = Foo | Bar

            union SingleUnion = Foo
            """
        )

    def prints_input_type():
        input_type = GraphQLInputObjectType(
            name="InputType", fields={"int": GraphQLInputField(GraphQLInt)}
        )

        schema = GraphQLSchema(types=[input_type])
        output = print_for_test(schema)
        assert output == dedent(
            """
            input InputType {
              int: Int
            }
            """
        )

    def prints_custom_scalar():
        odd_type = GraphQLScalarType(name="Odd")

        schema = GraphQLSchema(types=[odd_type])
        output = print_for_test(schema)
        assert output == dedent(
            """
            scalar Odd
            """
        )

    def prints_enum():
        rgb_type = GraphQLEnumType(
            name="RGB", values=dict.fromkeys(("RED", "GREEN", "BLUE"))
        )

        schema = GraphQLSchema(types=[rgb_type])
        output = print_for_test(schema)
        assert output == dedent(
            """
            enum RGB {
              RED
              GREEN
              BLUE
            }
            """
        )

    def prints_empty_types():
        schema = GraphQLSchema(
            types=[
                GraphQLEnumType("SomeEnum", {}),
                GraphQLInputObjectType("SomeInputObject", {}),
                GraphQLInterfaceType("SomeInterface", {}),
                GraphQLObjectType("SomeObject", {}),
                GraphQLUnionType("SomeUnion", []),
            ]
        )

        output = print_for_test(schema)
        assert output == dedent(
            """
            enum SomeEnum

            input SomeInputObject

            interface SomeInterface

            type SomeObject

            union SomeUnion
            """
        )

    def prints_custom_directives():
        simple_directive = GraphQLDirective(
            "simpleDirective", [DirectiveLocation.FIELD]
        )
        complex_directive = GraphQLDirective(
            "complexDirective",
            [DirectiveLocation.FIELD, DirectiveLocation.QUERY],
            description="Complex Directive",
            args={
                "stringArg": GraphQLArgument(GraphQLString),
                "intArg": GraphQLArgument(GraphQLInt, default_value=-1),
            },
            is_repeatable=True,
        )

        schema = GraphQLSchema(directives=[simple_directive, complex_directive])
        output = print_for_test(schema)
        assert output == dedent(
            '''
            directive @simpleDirective on FIELD

            """Complex Directive"""
            directive @complexDirective(stringArg: String, intArg: Int = -1) repeatable on FIELD | QUERY
            '''  # noqa: E501
        )

    def one_line_prints_a_short_description():
        description = "This field is awesome"
        output = print_single_field_schema(
            GraphQLField(GraphQLString, description=description)
        )
        assert output == dedent(
            '''
            type Query {
              """This field is awesome"""
              singleField: String
            }
            '''
        )
        schema = build_schema(output)
        recreated_root = assert_object_type(schema.type_map["Query"])
        recreated_field = recreated_root.fields["singleField"]
        assert recreated_field.description == description

    def prints_introspection_schema():
        schema = GraphQLSchema()
        output = print_introspection_schema(schema)
        assert output == dedent(
            '''
            """
            Directs the executor to include this field or fragment only when the `if` argument is true.
            """
            directive @include(
              """Included when true."""
              if: Boolean!
            ) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            """
            Directs the executor to skip this field or fragment when the `if` argument is true.
            """
            directive @skip(
              """Skipped when true."""
              if: Boolean!
            ) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            """Marks an element of a GraphQL schema as no longer supported."""
            directive @deprecated(
              """
              Explains why this element was deprecated, usually also including a suggestion
              for how to access supported similar data. Formatted using the Markdown syntax,
              as specified by [CommonMark](https://commonmark.org/).
              """
              reason: String = "No longer supported"
            ) on FIELD_DEFINITION | ENUM_VALUE

            """
            A Directive provides a way to describe alternate runtime execution and type validation behavior in a GraphQL document.

            In some cases, you need to provide options to alter GraphQL's execution behavior
            in ways field arguments will not suffice, such as conditionally including or
            skipping a field. Directives provide this by describing additional information
            to the executor.
            """
            type __Directive {
              name: String!
              description: String
              locations: [__DirectiveLocation!]!
              args: [__InputValue!]!
            }

            """
            A Directive can be adjacent to many parts of the GraphQL language, a
            __DirectiveLocation describes one such possible adjacencies.
            """
            enum __DirectiveLocation {
              """Location adjacent to a query operation."""
              QUERY

              """Location adjacent to a mutation operation."""
              MUTATION

              """Location adjacent to a subscription operation."""
              SUBSCRIPTION

              """Location adjacent to a field."""
              FIELD

              """Location adjacent to a fragment definition."""
              FRAGMENT_DEFINITION

              """Location adjacent to a fragment spread."""
              FRAGMENT_SPREAD

              """Location adjacent to an inline fragment."""
              INLINE_FRAGMENT

              """Location adjacent to a variable definition."""
              VARIABLE_DEFINITION

              """Location adjacent to a schema definition."""
              SCHEMA

              """Location adjacent to a scalar definition."""
              SCALAR

              """Location adjacent to an object type definition."""
              OBJECT

              """Location adjacent to a field definition."""
              FIELD_DEFINITION

              """Location adjacent to an argument definition."""
              ARGUMENT_DEFINITION

              """Location adjacent to an interface definition."""
              INTERFACE

              """Location adjacent to a union definition."""
              UNION

              """Location adjacent to an enum definition."""
              ENUM

              """Location adjacent to an enum value definition."""
              ENUM_VALUE

              """Location adjacent to an input object type definition."""
              INPUT_OBJECT

              """Location adjacent to an input object field definition."""
              INPUT_FIELD_DEFINITION
            }

            """
            One possible value for a given Enum. Enum values are unique values, not a
            placeholder for a string or numeric value. However an Enum value is returned in
            a JSON response as a string.
            """
            type __EnumValue {
              name: String!
              description: String
              isDeprecated: Boolean!
              deprecationReason: String
            }

            """
            Object and Interface types are described by a list of Fields, each of which has
            a name, potentially a list of arguments, and a return type.
            """
            type __Field {
              name: String!
              description: String
              args: [__InputValue!]!
              type: __Type!
              isDeprecated: Boolean!
              deprecationReason: String
            }

            """
            Arguments provided to Fields or Directives and the input fields of an
            InputObject are represented as Input Values which describe their type and
            optionally a default value.
            """
            type __InputValue {
              name: String!
              description: String
              type: __Type!

              """
              A GraphQL-formatted string representing the default value for this input value.
              """
              defaultValue: String
            }

            """
            A GraphQL Schema defines the capabilities of a GraphQL server. It exposes all
            available types and directives on the server, as well as the entry points for
            query, mutation, and subscription operations.
            """
            type __Schema {
              """A list of all types supported by this server."""
              types: [__Type!]!

              """The type that query operations will be rooted at."""
              queryType: __Type!

              """
              If this server supports mutation, the type that mutation operations will be rooted at.
              """
              mutationType: __Type

              """
              If this server support subscription, the type that subscription operations will be rooted at.
              """
              subscriptionType: __Type

              """A list of all directives supported by this server."""
              directives: [__Directive!]!
            }

            """
            The fundamental unit of any GraphQL Schema is the type. There are many kinds of
            types in GraphQL as represented by the `__TypeKind` enum.

            Depending on the kind of a type, certain fields describe information about that
            type. Scalar types provide no information beyond a name and description, while
            Enum types provide their values. Object and Interface types provide the fields
            they describe. Abstract types, Union and Interface, provide the Object types
            possible at runtime. List and NonNull types compose other types.
            """
            type __Type {
              kind: __TypeKind!
              name: String
              description: String
              fields(includeDeprecated: Boolean = false): [__Field!]
              interfaces: [__Type!]
              possibleTypes: [__Type!]
              enumValues(includeDeprecated: Boolean = false): [__EnumValue!]
              inputFields: [__InputValue!]
              ofType: __Type
            }

            """An enum describing what kind of type a given `__Type` is."""
            enum __TypeKind {
              """Indicates this type is a scalar."""
              SCALAR

              """
              Indicates this type is an object. `fields` and `interfaces` are valid fields.
              """
              OBJECT

              """
              Indicates this type is an interface. `fields` and `possibleTypes` are valid fields.
              """
              INTERFACE

              """Indicates this type is a union. `possibleTypes` is a valid field."""
              UNION

              """Indicates this type is an enum. `enumValues` is a valid field."""
              ENUM

              """
              Indicates this type is an input object. `inputFields` is a valid field.
              """
              INPUT_OBJECT

              """Indicates this type is a list. `ofType` is a valid field."""
              LIST

              """Indicates this type is a non-null. `ofType` is a valid field."""
              NON_NULL
            }
            '''  # noqa: E501
        )
