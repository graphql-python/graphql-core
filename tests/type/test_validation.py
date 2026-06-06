from __future__ import annotations

from operator import attrgetter

import pytest

from graphql.language import DirectiveLocation, parse
from graphql.pyutils import inspect
from graphql.type import (
    GraphQLArgument,
    GraphQLDefaultValueUsage,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
    assert_directive,
    assert_enum_type,
    assert_input_object_type,
    assert_interface_type,
    assert_object_type,
    assert_scalar_type,
    assert_union_type,
    assert_valid_schema,
    validate_schema,
)
from graphql.utilities import build_schema, extend_schema

from ..utils import dedent

SomeSchema = build_schema(
    """
    scalar SomeScalar

    interface SomeInterface { f: SomeObject }

    type SomeObject implements SomeInterface { f: SomeObject }

    union SomeUnion = SomeObject

    enum SomeEnum { ONLY }

    input SomeInputObject { val: String = "hello" }

    directive @SomeDirective on QUERY
    """
)

get_type = SomeSchema.get_type
SomeScalarType = assert_scalar_type(get_type("SomeScalar"))
SomeInterfaceType = assert_interface_type(get_type("SomeInterface"))
SomeObjectType = assert_object_type(get_type("SomeObject"))
SomeUnionType = assert_union_type(get_type("SomeUnion"))
SomeEnumType = assert_enum_type(get_type("SomeEnum"))
SomeInputObjectType = assert_input_object_type(get_type("SomeInputObject"))
SomeDirective = assert_directive(SomeSchema.get_directive("SomeDirective"))


def with_modifiers(
    type_: GraphQLNamedType,
) -> list[GraphQLNamedType | GraphQLNonNull | GraphQLList]:
    return [
        type_,
        GraphQLList(type_),
        GraphQLNonNull(type_),
        GraphQLNonNull(GraphQLList(type_)),
    ]


output_types = [
    *with_modifiers(GraphQLString),
    *with_modifiers(SomeScalarType),
    *with_modifiers(SomeEnumType),
    *with_modifiers(SomeObjectType),
    *with_modifiers(SomeUnionType),
    *with_modifiers(SomeInterfaceType),
]

not_output_types = with_modifiers(SomeInputObjectType)

input_types = [
    *with_modifiers(GraphQLString),
    *with_modifiers(SomeScalarType),
    *with_modifiers(SomeEnumType),
    *with_modifiers(SomeInputObjectType),
]

not_input_types = [
    *with_modifiers(SomeObjectType),
    *with_modifiers(SomeUnionType),
    *with_modifiers(SomeInterfaceType),
]

not_graphql_types = [
    type("IntType", (int,), {"name": "IntType"}),
    type("FloatType", (float,), {"name": "FloatType"}),
    type("StringType", (str,), {"name": "StringType"}),
]


get_name = attrgetter("__class__.__name__")


def schema_with_field_type(type_):
    return GraphQLSchema(
        query=GraphQLObjectType(name="Query", fields={"f": GraphQLField(type_)})
    )


def describe_type_system_a_schema_must_have_object_root_types():
    def accepts_a_schema_whose_query_type_is_an_object_type():
        schema = build_schema(
            """
            type Query {
              test: String
            }
            """
        )
        assert validate_schema(schema) == []

        schema_with_def = build_schema(
            """
            schema {
              query: QueryRoot
            }

            type QueryRoot {
              test: String
            }
            """
        )

        assert validate_schema(schema_with_def) == []

    def accepts_a_schema_whose_query_and_mutation_types_are_object_types():
        schema = build_schema(
            """
            type Query {
              test: String
            }

            type Mutation {
              test: String
            }
            """
        )
        assert validate_schema(schema) == []

        schema_with_def = build_schema(
            """
            schema {
              query: QueryRoot
              mutation: MutationRoot
            }

            type QueryRoot {
              test: String
            }

            type MutationRoot {
              test: String
            }
            """
        )
        assert validate_schema(schema_with_def) == []

    def accepts_a_schema_whose_query_and_subscription_types_are_object_types():
        schema = build_schema(
            """
            type Query {
              test: String
            }

            type Subscription {
              test: String
            }
            """
        )
        assert validate_schema(schema) == []

        schema_with_def = build_schema(
            """
            schema {
              query: QueryRoot
              subscription: SubscriptionRoot
            }

            type QueryRoot {
              test: String
            }

            type SubscriptionRoot {
              test: String
            }
            """
        )
        assert validate_schema(schema_with_def) == []

    def rejects_a_schema_without_a_query_type():
        schema = build_schema(
            """
            type Mutation {
              test: String
            }
            """
        )
        assert validate_schema(schema) == [
            {"message": "Query root type must be provided.", "locations": None}
        ]

        schema_with_def = build_schema(
            """
            schema {
              mutation: MutationRoot
            }

            type MutationRoot {
              test: String
            }
            """
        )
        assert validate_schema(schema_with_def) == [
            {"message": "Query root type must be provided.", "locations": [(2, 13)]}
        ]

    def rejects_a_schema_whose_query_root_type_is_not_an_object_type():
        schema = build_schema(
            """
            input Query {
              test: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Query root type must be Object type, it cannot be Query.",
                "locations": [(2, 13)],
            }
        ]

        schema_with_def = build_schema(
            """
            schema {
              query: SomeInputObject
            }

            input SomeInputObject {
              test: String
            }
            """
        )
        assert validate_schema(schema_with_def) == [
            {
                "message": "Query root type must be Object type,"
                " it cannot be SomeInputObject.",
                "locations": [(3, 22)],
            }
        ]

    def rejects_a_schema_whose_mutation_type_is_an_input_type():
        schema = build_schema(
            """
            type Query {
              field: String
            }

            input Mutation {
              test: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Mutation root type must be Object type if provided,"
                " it cannot be Mutation.",
                "locations": [(6, 13)],
            }
        ]

        schema_with_def = build_schema(
            """
            schema {
              query: Query
              mutation: SomeInputObject
            }

            type Query {
              field: String
            }

            input SomeInputObject {
              test: String
            }
            """
        )
        assert validate_schema(schema_with_def) == [
            {
                "message": "Mutation root type must be Object type if provided,"
                " it cannot be SomeInputObject.",
                "locations": [(4, 25)],
            }
        ]

    def rejects_a_schema_whose_subscription_type_is_an_input_type():
        schema = build_schema(
            """
            type Query {
              field: String
            }

            input Subscription {
              test: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Subscription root type must be Object type if"
                " provided, it cannot be Subscription.",
                "locations": [(6, 13)],
            }
        ]

        schema_with_def = build_schema(
            """
            schema {
              query: Query
              subscription: SomeInputObject
            }

            type Query {
              field: String
            }

            input SomeInputObject {
              test: String
            }
            """
        )
        assert validate_schema(schema_with_def) == [
            {
                "message": "Subscription root type must be Object type if"
                " provided, it cannot be SomeInputObject.",
                "locations": [(4, 29)],
            }
        ]

    def rejects_a_schema_extended_with_invalid_root_types():
        schema = build_schema(
            """
            input SomeInputObject {
              test: String
            }

            scalar SomeScalar

            enum SomeEnum {
              ENUM_VALUE
            }
            """
        )
        schema = extend_schema(
            schema,
            parse(
                """
                extend schema {
                  query: SomeInputObject
                }
                """
            ),
        )
        schema = extend_schema(
            schema,
            parse(
                """
                extend schema {
                  mutation: SomeScalar
                }
                """
            ),
        )
        schema = extend_schema(
            schema,
            parse(
                """
                extend schema {
                  subscription: SomeEnum
                }
                """
            ),
        )
        assert validate_schema(schema) == [
            {
                "message": "Query root type must be Object type,"
                " it cannot be SomeInputObject.",
                "locations": [(3, 26)],
            },
            {
                "message": "Mutation root type must be Object type"
                " if provided, it cannot be SomeScalar.",
                "locations": [(3, 29)],
            },
            {
                "message": "Subscription root type must be Object type"
                " if provided, it cannot be SomeEnum.",
                "locations": [(3, 33)],
            },
        ]

    def rejects_a_schema_whose_types_are_incorrectly_type():
        # invalid schema cannot be built with Python
        # construct invalid schema manually
        schema = GraphQLSchema(SomeObjectType)
        schema.type_map = {
            "SomeType": {"name": "SomeType"},  # type: ignore
            "SomeDirective": SomeDirective,  # type: ignore
        }
        assert validate_schema(schema) == [
            {"message": "Expected GraphQL named type but got: {'name': 'SomeType'}."},
            {"message": "Expected GraphQL named type but got: @SomeDirective."},
        ]

    def rejects_a_schema_whose_directives_are_incorrectly_typed():
        schema = GraphQLSchema(
            SomeObjectType,
            directives=[None, "SomeDirective", SomeScalarType],  # type: ignore
        )
        assert validate_schema(schema) == [
            {"message": "Expected directive but got: None."},
            {"message": "Expected directive but got: 'SomeDirective'."},
            {"message": "Expected directive but got: SomeScalar."},
        ]

    def rejects_a_schema_whose_directives_have_empty_locations():
        bad_directive = GraphQLDirective(
            name="BadDirective1",
            locations=[],
        )
        schema = GraphQLSchema(
            SomeObjectType,
            directives=[bad_directive],
        )
        assert validate_schema(schema) == [
            {
                "message": "Directive @BadDirective1 must include 1 or more locations.",
            },
        ]


def describe_type_system_root_types_must_all_be_different_if_provided():
    def accepts_a_schema_with_different_root_types():
        schema = build_schema(
            """
            type SomeObject1 {
              field: String
            }

            type SomeObject2 {
              field: String
            }

            type SomeObject3 {
              field: String
            }

            schema {
              query: SomeObject1
              mutation: SomeObject2
              subscription: SomeObject3
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_a_schema_where_the_same_type_is_used_for_multiple_root_types():
        schema = build_schema(
            """
            type SomeObject {
              field: String
            }

            type UniqueObject {
              field: String
            }

            schema {
              query: SomeObject
              mutation: UniqueObject
              subscription: SomeObject
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "All root types must be different, 'SomeObject' type"
                " is used as query and subscription root types.",
                "locations": [(11, 22), (13, 29)],
            }
        ]

    def rejects_a_schema_where_the_same_type_is_used_for_all_root_types():
        schema = build_schema(
            """
            type SomeObject {
              field: String
            }

            schema {
              query: SomeObject
              mutation: SomeObject
              subscription: SomeObject
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "All root types must be different, 'SomeObject' type"
                " is used as query, mutation, and subscription root types.",
                "locations": [(7, 22), (8, 25), (9, 29)],
            }
        ]


def describe_type_system_objects_must_have_fields():
    def accepts_an_object_type_with_fields_object():
        schema = build_schema(
            """
            type Query {
              field: SomeObject
            }

            type SomeObject {
              field: String
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_object_type_with_missing_fields():
        schema = build_schema(
            """
            type Query {
              test: IncompleteObject
            }

            type IncompleteObject
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type IncompleteObject must define one or more fields.",
                "locations": [(6, 13)],
            }
        ]

        manual_schema = schema_with_field_type(
            GraphQLObjectType("IncompleteObject", {})
        )
        msg = validate_schema(manual_schema)[0].message
        assert msg == "Type IncompleteObject must define one or more fields."

        manual_schema_2 = schema_with_field_type(
            GraphQLObjectType("IncompleteObject", dict)
        )
        msg = validate_schema(manual_schema_2)[0].message
        assert msg == "Type IncompleteObject must define one or more fields."

    def rejects_an_object_type_with_incorrectly_named_fields():
        schema = schema_with_field_type(
            GraphQLObjectType("SomeObject", {"__badName": GraphQLField(GraphQLString)})
        )
        msg = validate_schema(schema)[0].message
        assert msg == (
            "Name '__badName' must not begin with '__',"
            " which is reserved by GraphQL introspection."
        )


def describe_type_system_field_args_must_be_properly_named():
    def accepts_field_args_with_valid_names():
        schema = schema_with_field_type(
            GraphQLObjectType(
                "SomeObject",
                {
                    "goodField": GraphQLField(
                        GraphQLString, args={"goodArg": GraphQLArgument(GraphQLString)}
                    )
                },
            )
        )
        assert validate_schema(schema) == []

    def rejects_field_args_with_invalid_names():
        schema = schema_with_field_type(
            GraphQLObjectType(
                "SomeObject",
                {
                    "badField": GraphQLField(
                        GraphQLString,
                        args={"__badName": GraphQLArgument(GraphQLString)},
                    )
                },
            )
        )

        msg = validate_schema(schema)[0].message
        assert msg == (
            "Name '__badName' must not begin with '__',"
            " which is reserved by GraphQL introspection."
        )


def describe_type_system_union_types_must_be_valid():
    def accepts_a_union_type_with_member_types():
        schema = build_schema(
            """
            type Query {
              test: GoodUnion
            }

            type TypeA {
              field: String
            }

            type TypeB {
              field: String
            }

            union GoodUnion =
              | TypeA
              | TypeB
            """
        )
        assert validate_schema(schema) == []

    def rejects_a_union_type_with_empty_types():
        schema = build_schema(
            """
            type Query {
              test: BadUnion
            }

            union BadUnion
            """
        )

        schema = extend_schema(
            schema,
            parse(
                """
                directive @test on UNION

                extend union BadUnion @test
                """
            ),
        )

        assert validate_schema(schema) == [
            {
                "message": "Union type BadUnion must define one or more member types.",
                "locations": [(6, 13), (4, 17)],
            }
        ]

    def rejects_a_union_type_with_duplicated_member_type():
        schema = build_schema(
            """
            type Query {
              test: BadUnion
            }

            type TypeA {
              field: String
            }

            type TypeB {
              field: String
            }

            union BadUnion =
              | TypeA
              | TypeB
              | TypeA
            """
        )

        assert validate_schema(schema) == [
            {
                "message": "Union type BadUnion can only include type TypeA once.",
                "locations": [(15, 17), (17, 17)],
            }
        ]

        schema = extend_schema(schema, parse("extend union BadUnion = TypeB"))

        assert validate_schema(schema) == [
            {
                "message": "Union type BadUnion can only include type TypeA once.",
                "locations": [(15, 17), (17, 17)],
            },
            {
                "message": "Union type BadUnion can only include type TypeB once.",
                "locations": [(16, 17), (1, 25)],
            },
        ]

    def rejects_a_union_type_with_non_object_member_types():
        # invalid schema cannot be built with Python
        schema = build_schema(
            """
            type Query {
              test: BadUnion
            }

            type TypeA {
              field: String
            }

            type TypeB {
              field: String
            }

            union BadUnion =
              | TypeA
              | String
              | TypeB
            """
        )

        schema = extend_schema(schema, parse("extend union BadUnion = Int"))

        assert validate_schema(schema) == [
            {
                "message": "Union type BadUnion can only include Object types,"
                " it cannot include String.",
                "locations": [(16, 17)],
            },
            {
                "message": "Union type BadUnion can only include Object types,"
                " it cannot include Int.",
                "locations": [(1, 25)],
            },
        ]

        bad_union_member_types = [
            GraphQLString,
            GraphQLNonNull(SomeObjectType),
            GraphQLList(SomeObjectType),
            SomeInterfaceType,
            SomeUnionType,
            SomeEnumType,
            SomeInputObjectType,
        ]
        for member_type in bad_union_member_types:
            # invalid union type cannot be built with Python
            bad_union = GraphQLUnionType(
                "BadUnion",
                types=[member_type],  # type: ignore
            )
            bad_schema = schema_with_field_type(bad_union)
            assert validate_schema(bad_schema) == [
                {
                    "message": "Union type BadUnion can only include Object types,"
                    f" it cannot include {inspect(member_type)}."
                }
            ]

    def rejects_a_union_type_with_non_object_members_types_with_malformed_ast():
        schema = build_schema(
            """
            type Query {
              test: BadUnion
            }

            type TypeA {
              field: String
            }

            type TypeB {
              field: String
            }

            union BadUnion =
              | TypeA
              | String
              | TypeB
            """
        )

        bad_union = schema.get_type("BadUnion")
        assert bad_union is not None
        bad_union_node = bad_union.ast_node
        assert bad_union_node is not None
        object.__setattr__(bad_union_node, "types", None)

        assert validate_schema(schema) == [
            {
                "message": "Union type BadUnion can only include Object types,"
                " it cannot include String.",
            }
        ]


def describe_type_system_input_objects_must_have_fields():
    def accepts_an_input_object_type_with_fields():
        schema = build_schema(
            """
            type Query {
               field(arg: SomeInputObject): String
            }

            input SomeInputObject {
              field: String
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_input_object_type_with_missing_fields():
        schema = build_schema(
            """
            type Query {
              field(arg: SomeInputObject): String
            }

            input SomeInputObject
            """
        )
        schema = extend_schema(
            schema,
            parse(
                """
                directive @test on INPUT_OBJECT

                extend input SomeInputObject @test
                """
            ),
        )
        assert validate_schema(schema) == [
            {
                "message": "Input Object type SomeInputObject"
                " must define one or more fields.",
                "locations": [(6, 13), (4, 17)],
            }
        ]

    def accepts_an_input_object_with_breakable_circular_reference():
        schema = build_schema(
            """
            type Query {
              field(arg: SomeInputObject): String
            }

            input SomeInputObject {
              self: SomeInputObject
              arrayOfSelf: [SomeInputObject]
              nonNullArrayOfSelf: [SomeInputObject]!
              nonNullArrayOfNonNullSelf: [SomeInputObject!]!
              intermediateSelf: AnotherInputObject
            }

            input AnotherInputObject {
              parent: SomeInputObject
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_input_object_with_non_breakable_circular_reference():
        schema = build_schema(
            """
            type Query {
              field(arg: SomeInputObject): String
            }

            input SomeInputObject {
              startLoop: AnotherInputObject!
            }

            input AnotherInputObject {
              nextInLoop: YetAnotherInputObject!
            }

            input YetAnotherInputObject {
              closeLoop: SomeInputObject!
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Invalid circular reference."
                " The Input Object SomeInputObject references itself"
                " via the non-null fields: SomeInputObject.startLoop,"
                " AnotherInputObject.nextInLoop,"
                " YetAnotherInputObject.closeLoop.",
                "locations": [(7, 15), (11, 15), (15, 15)],
            }
        ]

    def rejects_an_input_object_with_multiple_non_breakable_circular_reference():
        schema = build_schema(
            """
            type Query {
              field(arg: SomeInputObject): String
            }

            input SomeInputObject {
              startLoop: AnotherInputObject!
            }

            input AnotherInputObject {
              closeLoop: SomeInputObject!
              startSecondLoop: YetAnotherInputObject!
            }

            input YetAnotherInputObject {
              closeSecondLoop: AnotherInputObject!
              nonNullSelf: YetAnotherInputObject!
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Invalid circular reference."
                " The Input Object SomeInputObject references itself"
                " via the non-null fields: SomeInputObject.startLoop,"
                " AnotherInputObject.closeLoop.",
                "locations": [(7, 15), (11, 15)],
            },
            {
                "message": "Invalid circular reference."
                " The Input Object AnotherInputObject references itself"
                " via the non-null fields: AnotherInputObject.startSecondLoop,"
                " YetAnotherInputObject.closeSecondLoop.",
                "locations": [(12, 15), (16, 15)],
            },
            {
                "message": "Invalid circular reference."
                " The Input Object YetAnotherInputObject references itself"
                " in the non-null field YetAnotherInputObject.nonNullSelf.",
                "locations": [(17, 15)],
            },
        ]

    def accepts_input_objects_with_default_values_without_circular_refs_sdl():
        valid_schema = build_schema(
            """
            type Query {
              field(arg1: A, arg2: B): String
            }

            input A {
              x: A = null
              y: A = { x: null, y: null }
              z: [A] = []
            }

            input B {
              x: B2! = {}
              y: String = "abc"
              z: Custom = {}
            }

            input B2 {
              x: B3 = {}
            }

            input B3 {
              x: B = { x: { x: null } }
            }

            scalar Custom
            """
        )
        assert validate_schema(valid_schema) == []

    def accepts_input_objects_with_default_values_without_circular_refs():
        a_type = GraphQLInputObjectType(
            "A",
            lambda: {
                "x": GraphQLInputField(a_type, default_value=None),
                "y": GraphQLInputField(a_type, default_value={"x": None, "y": None}),
                "z": GraphQLInputField(GraphQLList(a_type), default_value=[]),
            },
        )

        b_type = GraphQLInputObjectType(
            "B",
            lambda: {
                "x": GraphQLInputField(GraphQLNonNull(b2_type), default_value={}),
                "y": GraphQLInputField(GraphQLString, default_value="abc"),
                "z": GraphQLInputField(custom_type, default_value={}),
            },
        )

        b2_type = GraphQLInputObjectType(
            "B2",
            lambda: {
                "x": GraphQLInputField(b3_type, default_value={}),
            },
        )

        b3_type = GraphQLInputObjectType(
            "B3",
            lambda: {
                "x": GraphQLInputField(b_type, default_value={"x": {"x": None}}),
            },
        )

        custom_type = GraphQLScalarType("Custom")

        valid_schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "field": GraphQLField(
                        GraphQLString,
                        args={
                            "arg1": GraphQLArgument(a_type),
                            "arg2": GraphQLArgument(b_type),
                        },
                    )
                },
            )
        )

        assert validate_schema(valid_schema) == []

    def rejects_input_objects_with_default_value_circular_reference_sdl():
        invalid_schema = build_schema(
            """
            type Query {
              field(arg1: A, arg2: B, arg3: C, arg4: D, arg5: E): String
            }

            input A {
              x: A = {}
            }

            input B {
              x: B2 = {}
            }

            input B2 {
              x: B3 = {}
            }

            input B3 {
              x: B = {}
            }

            input C {
              x: [C] = [{}]
            }

            input D {
              x: D = { x: { x: {} } }
            }

            input E {
              x: E = { x: null }
              y: E = { y: null }
            }

            input F {
              x: F2! = {}
            }

            input F2 {
              x: F = { x: {} }
            }
            """
        )

        assert validate_schema(invalid_schema) == [
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field A.x references itself.",
                "locations": [(7, 22)],
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field B.x references itself via the default values of:"
                " B2.x, B3.x.",
                "locations": [(11, 23), (15, 23), (19, 22)],
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field C.x references itself.",
                "locations": [(23, 24)],
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field D.x references itself.",
                "locations": [(27, 22)],
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field E.x references itself via the default values of:"
                " E.y.",
                "locations": [(31, 22), (32, 22)],
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field F2.x references itself.",
                "locations": [(40, 22)],
            },
        ]

    def rejects_input_objects_with_default_value_circular_reference():
        a_type = GraphQLInputObjectType(
            "A",
            lambda: {
                "x": GraphQLInputField(a_type, default_value={}),
            },
        )

        b_type = GraphQLInputObjectType(
            "B",
            lambda: {
                "x": GraphQLInputField(b2_type, default_value={}),
            },
        )

        b2_type = GraphQLInputObjectType(
            "B2",
            lambda: {
                "x": GraphQLInputField(b3_type, default_value={}),
            },
        )

        b3_type = GraphQLInputObjectType(
            "B3",
            lambda: {
                "x": GraphQLInputField(b_type, default_value={}),
            },
        )

        c_type = GraphQLInputObjectType(
            "C",
            lambda: {
                "x": GraphQLInputField(GraphQLList(c_type), default_value=[{}]),
            },
        )

        d_type = GraphQLInputObjectType(
            "D",
            lambda: {
                "x": GraphQLInputField(d_type, default_value={"x": {"x": {}}}),
            },
        )

        e_type = GraphQLInputObjectType(
            "E",
            lambda: {
                "x": GraphQLInputField(e_type, default_value={"x": None}),
                "y": GraphQLInputField(e_type, default_value={"y": None}),
            },
        )

        f_type = GraphQLInputObjectType(
            "F",
            lambda: {
                "x": GraphQLInputField(GraphQLNonNull(f2_type), default_value={}),
            },
        )

        f2_type = GraphQLInputObjectType(
            "F2",
            lambda: {
                "x": GraphQLInputField(f_type, default_value={"x": {}}),
            },
        )

        invalid_schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "field": GraphQLField(
                        GraphQLString,
                        args={
                            "arg1": GraphQLArgument(a_type),
                            "arg2": GraphQLArgument(b_type),
                            "arg3": GraphQLArgument(c_type),
                            "arg4": GraphQLArgument(d_type),
                            "arg5": GraphQLArgument(e_type),
                            "arg6": GraphQLArgument(f_type),
                        },
                    )
                },
            )
        )

        assert validate_schema(invalid_schema) == [
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field A.x references itself.",
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field B.x references itself via the default values of:"
                " B2.x, B3.x.",
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field C.x references itself.",
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field D.x references itself.",
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field E.x references itself via the default values of:"
                " E.y.",
            },
            {
                "message": "Invalid circular reference. The default value of Input"
                " Object field F2.x references itself.",
            },
        ]

    def rejects_an_input_object_type_with_incorrectly_typed_fields():
        schema = build_schema(
            """
            type Query {
              field(arg: SomeInputObject): String
            }

            type SomeObject {
              field: String
            }

            union SomeUnion = SomeObject

            input SomeInputObject {
              badObject: SomeObject
              badUnion: SomeUnion
              goodInputObject: SomeInputObject
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "The type of SomeInputObject.badObject must be Input Type"
                " but got: SomeObject.",
                "locations": [(13, 26)],
            },
            {
                "message": "The type of SomeInputObject.badUnion must be Input Type"
                " but got: SomeUnion.",
                "locations": [(14, 25)],
            },
        ]

    def rejects_an_input_object_type_with_required_field_that_is_deprecated():
        schema = build_schema(
            """
            type Query {
              field(arg: SomeInputObject): String
            }

            input SomeInputObject {
              badField: String! @deprecated
              optionalField: String @deprecated
              anotherOptionalField: String! = "" @deprecated
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Required input field SomeInputObject.badField"
                " cannot be deprecated.",
                "locations": [(7, 33), (7, 25)],
            }
        ]


def describe_type_system_enum_types_must_be_well_defined():
    def rejects_an_enum_type_without_values():
        schema = build_schema(
            """
            type Query {
              field: SomeEnum
            }

            enum SomeEnum
            """
        )

        schema = extend_schema(
            schema,
            parse(
                """
                directive @test on ENUM

                extend enum SomeEnum @test
                """
            ),
        )

        assert validate_schema(schema) == [
            {
                "message": "Enum type SomeEnum must define one or more values.",
                "locations": [(6, 13), (4, 17)],
            }
        ]

    def rejects_an_enum_type_with_incorrectly_named_values():
        schema = schema_with_field_type(
            GraphQLEnumType("SomeEnum", values={"__badName": {}})
        )

        assert validate_schema(schema) == [
            {
                "message": "Name '__badName' must not begin with '__',"
                " which is reserved by GraphQL introspection."
            }
        ]


def describe_type_system_object_fields_must_have_output_types():
    def _schema_with_object_field(type_: GraphQLOutputType) -> GraphQLSchema:
        bad_object_type = GraphQLObjectType(
            "BadObject", {"badField": GraphQLField(type_)}
        )
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(bad_object_type)}),
            types=[SomeObjectType],
        )

    @pytest.mark.parametrize("type_", output_types, ids=get_name)
    def accepts_an_output_type_as_an_object_field_type(type_):
        schema = _schema_with_object_field(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_object_field_type():
        schema = _schema_with_object_field(None)  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of BadObject.badField must be Output Type"
                " but got: None."
            }
        ]

    @pytest.mark.parametrize("type_", not_output_types, ids=get_name)
    def rejects_a_non_output_type_as_an_object_field_type(type_):
        schema = _schema_with_object_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadObject.badField must be Output Type"
                f" but got: {type_}."
            }
        ]

    @pytest.mark.parametrize("type_", not_graphql_types, ids=get_name)
    def rejects_a_non_type_value_as_an_object_field_type(type_):
        schema = _schema_with_object_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadObject.badField must be Output Type"
                f" but got: {inspect(type_)}.",
            },
            {"message": f"Expected GraphQL named type but got: {inspect(type_)}."},
        ]

    def rejects_with_relevant_locations_for_a_non_output_type():
        schema = build_schema(
            """
            type Query {
              field: [SomeInputObject]
            }

            input SomeInputObject {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "The type of Query.field must be Output Type"
                " but got: [SomeInputObject].",
                "locations": [(3, 22)],
            }
        ]


def describe_type_system_objects_can_only_implement_unique_interfaces():
    def rejects_an_object_implementing_a_non_type_value():
        query_type = GraphQLObjectType(
            "BadObject",
            {"f": GraphQLField(GraphQLString)},
        )
        query_type.interfaces = (None,)
        schema = GraphQLSchema(query_type)

        assert validate_schema(schema) == [
            {
                "message": "Type BadObject must only implement Interface types,"
                " it cannot implement None."
            }
        ]

    def rejects_an_object_implementing_a_non_interface_type():
        schema = build_schema(
            """
            type Query {
              test: BadObject
            }

            input SomeInputObject {
              field: String
            }

            type BadObject implements SomeInputObject {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type BadObject must only implement Interface types,"
                " it cannot implement SomeInputObject."
            }
        ]

    def rejects_an_object_implementing_a_non_interface_type_with_malformed_ast():
        schema = build_schema(
            """
            type Query {
              test: BadObject
            }

            input SomeInputObject {
              field: String
            }

            type BadObject implements SomeInputObject {
              field: String
            }
            """
        )

        bad_object = schema.get_type("BadObject")
        assert bad_object is not None
        bad_object_node = bad_object.ast_node
        assert bad_object_node is not None
        object.__setattr__(bad_object_node, "interfaces", None)

        assert validate_schema(schema) == [
            {
                "message": "Type BadObject must only implement Interface types,"
                " it cannot implement SomeInputObject."
            }
        ]

    def rejects_an_object_implementing_the_same_interface_twice():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String
            }

            type AnotherObject implements AnotherInterface & AnotherInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type AnotherObject can only implement"
                " AnotherInterface once.",
                "locations": [(10, 43), (10, 62)],
            }
        ]

    def rejects_an_object_implementing_same_interface_twice_due_to_extension():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String
            }

            type AnotherObject implements AnotherInterface {
              field: String
            }
            """
        )
        extended_schema = extend_schema(
            schema, parse("extend type AnotherObject implements AnotherInterface")
        )
        assert validate_schema(extended_schema) == [
            {
                "message": "Type AnotherObject can only implement"
                " AnotherInterface once.",
                "locations": [(10, 43), (1, 38)],
            }
        ]


def describe_type_system_interface_extensions_should_be_valid():
    def rejects_object_implementing_extended_interface_due_to_missing_field():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String
            }

            type AnotherObject implements AnotherInterface {
              field: String
            }
            """
        )
        extended_schema = extend_schema(
            schema,
            parse(
                """
                extend interface AnotherInterface {
                  newField: String
                }

                extend type AnotherObject {
                  differentNewField: String
                }
                """
            ),
        )
        assert validate_schema(extended_schema) == [
            {
                "message": "Interface field AnotherInterface.newField expected"
                " but AnotherObject does not provide it.",
                "locations": [(3, 19), (10, 13), (6, 17)],
            }
        ]

    def rejects_object_implementing_extended_interface_due_to_missing_args():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String
            }

            type AnotherObject implements AnotherInterface {
              field: String
            }
            """
        )
        extended_schema = extend_schema(
            schema,
            parse(
                """
                extend interface AnotherInterface {
                  newField(test: Boolean): String
                }

                extend type AnotherObject {
                  newField: String
                }
                """
            ),
        )
        assert validate_schema(extended_schema) == [
            {
                "message": "Interface field argument"
                " AnotherInterface.newField(test:) expected"
                " but AnotherObject.newField does not provide it.",
                "locations": [(3, 28), (7, 19)],
            }
        ]

    def rejects_object_implementing_extended_interface_due_to_type_mismatch():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String
            }

            type AnotherObject implements AnotherInterface {
              field: String
            }
            """
        )
        extended_schema = extend_schema(
            schema,
            parse(
                """
                extend interface AnotherInterface {
                  newInterfaceField: NewInterface
                }

                interface NewInterface {
                  newField: String
                }

                interface MismatchingInterface {
                  newField: String
                }

                extend type AnotherObject {
                  newInterfaceField: MismatchingInterface
                }

                # Required to prevent unused interface errors
                type DummyObject implements NewInterface & MismatchingInterface {
                  newField: String
                }
                """
            ),
        )
        assert validate_schema(extended_schema) == [
            {
                "message": "Interface field AnotherInterface.newInterfaceField"
                " expects type NewInterface"
                " but AnotherObject.newInterfaceField"
                " is type MismatchingInterface.",
                "locations": [(3, 38), (15, 38)],
            }
        ]


def describe_type_system_interface_fields_must_have_output_types():
    def _schema_with_interface_field(type_: GraphQLOutputType) -> GraphQLSchema:
        fields = {"badField": GraphQLField(type_)}
        bad_interface_type = GraphQLInterfaceType("BadInterface", fields)
        bad_implementing_type = GraphQLObjectType(
            "BadImplementing",
            fields,
            interfaces=[bad_interface_type],
        )
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(bad_interface_type)}),
            types=[bad_implementing_type, SomeObjectType],
        )

    @pytest.mark.parametrize("type_", output_types, ids=get_name)
    def accepts_an_output_type_as_an_interface_field_type(type_):
        schema = _schema_with_interface_field(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_interface_field_type():
        schema = _schema_with_interface_field(None)  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of BadImplementing.badField must be Output Type"
                " but got: None.",
            },
            {
                "message": "The type of BadInterface.badField must be Output Type"
                " but got: None.",
            },
        ]

    @pytest.mark.parametrize("type_", not_output_types, ids=get_name)
    def rejects_a_non_output_type_as_an_interface_field_type(type_):
        schema = _schema_with_interface_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadImplementing.badField must be Output Type"
                f" but got: {type_}.",
            },
            {
                "message": "The type of BadInterface.badField must be Output Type"
                f" but got: {type_}.",
            },
        ]

    @pytest.mark.parametrize("type_", not_graphql_types, ids=get_name)
    def rejects_a_non_type_value_as_an_interface_field_type(type_):
        schema = _schema_with_interface_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadImplementing.badField must be Output Type"
                f" but got: {inspect(type_)}.",
            },
            {
                "message": "The type of BadInterface.badField must be Output Type"
                f" but got: {inspect(type_)}.",
            },
            {"message": f"Expected GraphQL named type but got: {inspect(type_)}."},
        ]

    def rejects_a_non_output_type_as_an_interface_field_with_locations():
        schema = build_schema(
            """
            type Query {
              test: SomeInterface
            }

            interface SomeInterface {
              field: SomeInputObject
            }

            input SomeInputObject {
              foo: String
            }

            type SomeObject implements SomeInterface {
              field: SomeInputObject
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "The type of SomeInterface.field must be Output Type"
                " but got: SomeInputObject.",
                "locations": [(7, 22)],
            },
            {
                "message": "The type of SomeObject.field must be Output Type"
                " but got: SomeInputObject.",
                "locations": [(15, 22)],
            },
        ]

    def accepts_an_interface_not_implemented_by_at_least_one_object():
        schema = build_schema(
            """
            type Query {
              test: SomeInterface
            }

            interface SomeInterface {
              foo: String
            }
            """
        )
        assert validate_schema(schema) == []


def describe_type_system_arguments_must_have_input_types():
    def _schema_with_arg(type_: GraphQLInputType) -> GraphQLSchema:
        args = {"badArg": GraphQLArgument(type_)}
        bad_object_type = GraphQLObjectType(
            "BadObject",
            {"badField": GraphQLField(GraphQLString, args)},
        )
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(bad_object_type)}),
            directives=[
                GraphQLDirective(
                    "BadDirective",
                    [DirectiveLocation.QUERY],
                    args,
                )
            ],
        )

    @pytest.mark.parametrize("type_", input_types, ids=get_name)
    def accepts_an_input_type_as_a_field_arg_type(type_):
        schema = _schema_with_arg(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_field_arg_type():
        schema = _schema_with_arg(None)  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of @BadDirective(badArg:) must be Input Type"
                " but got: None."
            },
            {
                "message": "The type of BadObject.badField(badArg:) must be Input Type"
                " but got: None."
            },
        ]

    @pytest.mark.parametrize("type_", not_input_types, ids=get_name)
    def rejects_a_non_input_type_as_a_field_arg_type(type_):
        schema = _schema_with_arg(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of @BadDirective(badArg:) must be Input Type"
                f" but got: {type_}."
            },
            {
                "message": "The type of BadObject.badField(badArg:) must be Input Type"
                f" but got: {type_}."
            },
        ]

    @pytest.mark.parametrize("type_", not_graphql_types, ids=get_name)
    def rejects_a_non_type_value_as_a_field_arg_type(type_):
        schema = _schema_with_arg(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of @BadDirective(badArg:) must be Input Type"
                f" but got: {inspect(type_)}."
            },
            {
                "message": "The type of BadObject.badField(badArg:) must be Input Type"
                f" but got: {inspect(type_)}."
            },
            {"message": f"Expected GraphQL named type but got: {inspect(type_)}."},
        ]

    def rejects_a_required_argument_that_is_deprecated():
        schema = build_schema(
            """
            directive @BadDirective(
              badArg: String! @deprecated
              optionalArg: String @deprecated
              anotherOptionalArg: String! = "" @deprecated
            ) on FIELD

            type Query {
              test(
                badArg: String! @deprecated
                optionalArg: String @deprecated
                anotherOptionalArg: String! = "" @deprecated
              ): String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Required argument @BadDirective(badArg:)"
                " cannot be deprecated.",
                "locations": [(3, 31), (3, 23)],
            },
            {
                "message": "Required argument Query.test(badArg:)"
                " cannot be deprecated.",
                "locations": [(10, 33), (10, 25)],
            },
        ]

    def rejects_a_non_input_type_as_a_field_arg_with_locations():
        schema = build_schema(
            """
            type Query {
              test(arg: SomeObject): String
            }

            type SomeObject {
              foo: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "The type of Query.test(arg:) must be Input Type"
                " but got: SomeObject.",
                "locations": [(3, 25)],
            },
        ]


def describe_type_system_argument_default_values_must_be_valid():
    def rejects_an_argument_with_invalid_default_values_sdl():
        schema = build_schema(
            """
            type Query {
              field(arg: Int = 3.14): Int
            }

            directive @bad(arg: Int = 2.718) on FIELD
            """
        )

        assert validate_schema(schema) == [
            {
                "message": "@bad(arg:) has invalid default value:"
                " Int cannot represent non-integer value: 2.718",
                "locations": [(6, 39)],
            },
            {
                "message": "Query.field(arg:) has invalid default value:"
                " Int cannot represent non-integer value: 3.14",
                "locations": [(3, 32)],
            },
        ]

    def rejects_an_argument_with_invalid_default_values_programmatic():
        schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {
                    "field": GraphQLField(
                        GraphQLInt,
                        args={
                            "arg": GraphQLArgument(GraphQLInt, default_value=3.14),
                        },
                    )
                },
            ),
            directives=[
                GraphQLDirective(
                    "bad",
                    args={
                        "arg": GraphQLArgument(GraphQLInt, default_value=2.718),
                    },
                    locations=[DirectiveLocation.FIELD],
                ),
            ],
        )

        assert validate_schema(schema) == [
            {
                "message": "@bad(arg:) has invalid default value:"
                " Int cannot represent non-integer value: 2.718",
            },
            {
                "message": "Query.field(arg:) has invalid default value:"
                " Int cannot represent non-integer value: 3.14",
            },
        ]

    def attempts_to_offer_a_suggested_fix_if_possible_programmatic():
        exotic = object()

        test_enum = GraphQLEnumType(
            "TestEnum",
            {
                "ONE": 1,
                "TWO": exotic,
            },
        )

        test_input = GraphQLInputObjectType(
            "TestInput",
            lambda: {
                "self": GraphQLInputField(test_input),
                "string": GraphQLInputField(GraphQLNonNull(GraphQLList(GraphQLString))),
                "enum": GraphQLInputField(GraphQLList(test_enum)),
            },
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "field": GraphQLField(
                        GraphQLInt,
                        args={
                            "argWithPossibleFix": GraphQLArgument(
                                test_input,
                                default_value={
                                    "self": None,
                                    "string": [1],
                                    "enum": exotic,
                                },
                            ),
                            "argWithInvalidPossibleFix": GraphQLArgument(
                                test_input, default_value={"string": None}
                            ),
                            "argWithoutPossibleFix": GraphQLArgument(
                                test_input, default_value={"enum": "Exotic"}
                            ),
                        },
                    )
                },
            )
        )

        assert validate_schema(schema) == [
            {
                "message": "Query.field(argWithPossibleFix:) has invalid default"
                " value: {'self': None, 'string': [1], 'enum': "
                + inspect(exotic)
                + "}. Did you mean: {'self': None, 'string': ['1'],"
                " 'enum': ['TWO']}?",
            },
            {
                "message": "Query.field(argWithInvalidPossibleFix:) has invalid"
                " default value at .string: Expected value of non-null type"
                " '[String]!' not to be None.",
            },
            {
                "message": "Query.field(argWithoutPossibleFix:) has invalid default"
                " value: Expected value of type 'TestInput' to include required"
                " field 'string', found: {'enum': 'Exotic'}.",
            },
            {
                "message": "Query.field(argWithoutPossibleFix:) has invalid default"
                " value at .enum: Value 'Exotic' does not exist in 'TestEnum' enum.",
            },
        ]

    def attempts_to_offer_a_suggested_fix_if_possible_sdl():
        original_schema = build_schema(
            """
            enum TestEnum {
              ONE
              TWO
            }

            input TestInput {
              self: TestInput
              string: [String]!
              enum: [TestEnum]
            }

            type Query {
              field(
                argWithPossibleFix: TestInput
                argWithInvalidPossibleFix: TestInput
                argWithoutPossibleFix: TestInput
              ): Int
            }
            """
        )

        exotic = object()

        # workaround as we cannot inject custom internal values into enums
        # defined in SDL
        test_enum = GraphQLEnumType(
            "TestEnum",
            {
                "ONE": 1,
                "TWO": exotic,
            },
        )

        test_input = assert_input_object_type(original_schema.get_type("TestInput"))
        test_input.fields["enum"].type = GraphQLList(test_enum)

        # workaround as we cannot inject exotic default values into arguments
        # defined in SDL
        default_values = {
            "argWithPossibleFix": {"self": None, "string": [1], "enum": exotic},
            "argWithInvalidPossibleFix": {"string": None},
            "argWithoutPossibleFix": {"enum": "Exotic"},
        }
        query_type = assert_object_type(original_schema.get_type("Query"))
        for arg_name, arg in query_type.fields["field"].args.items():
            arg.type = test_input
            arg.default_value = GraphQLDefaultValueUsage(value=default_values[arg_name])

        assert validate_schema(original_schema) == [
            {
                "message": "Query.field(argWithPossibleFix:) has invalid default"
                " value: {'self': None, 'string': [1], 'enum': "
                + inspect(exotic)
                + "}. Did you mean: {'self': None, 'string': ['1'],"
                " 'enum': ['TWO']}?",
            },
            {
                "message": "Query.field(argWithInvalidPossibleFix:) has invalid"
                " default value at .string: Expected value of non-null type"
                " '[String]!' not to be None.",
            },
            {
                "message": "Query.field(argWithoutPossibleFix:) has invalid default"
                " value: Expected value of type 'TestInput' to include required"
                " field 'string', found: {'enum': 'Exotic'}.",
            },
            {
                "message": "Query.field(argWithoutPossibleFix:) has invalid default"
                " value at .enum: Value 'Exotic' does not exist in 'TestEnum' enum.",
            },
        ]


def describe_type_system_input_object_fields_must_have_input_types():
    def _schema_with_input_field(type_: GraphQLInputType) -> GraphQLSchema:
        bad_input_object_type = GraphQLInputObjectType(
            "BadInputObject", {"badField": GraphQLInputField(type_)}
        )
        return GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "f": GraphQLField(
                        GraphQLString,
                        args={"badArg": GraphQLArgument(bad_input_object_type)},
                    )
                },
            )
        )

    @pytest.mark.parametrize("type_", input_types, ids=get_name)
    def accepts_an_input_type_as_an_input_field_type(type_):
        schema = _schema_with_input_field(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_input_field_type():
        schema = _schema_with_input_field(None)  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of BadInputObject.badField must be Input Type"
                " but got: None."
            }
        ]

    @pytest.mark.parametrize("type_", not_input_types, ids=get_name)
    def rejects_a_non_input_type_as_an_input_field_type(type_):
        schema = _schema_with_input_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadInputObject.badField must be Input Type"
                f" but got: {type_}."
            }
        ]

    @pytest.mark.parametrize("type_", not_graphql_types, ids=get_name)
    def rejects_a_non_type_value_as_an_input_field_type(type_):
        schema = _schema_with_input_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadInputObject.badField must be Input Type"
                f" but got: {inspect(type_)}."
            },
            {"message": f"Expected GraphQL named type but got: {inspect(type_)}."},
        ]

    def rejects_with_relevant_locations_for_a_non_input_type():
        schema = build_schema(
            """
            type Query {
              test(arg: SomeInputObject): String
            }

            input SomeInputObject {
              foo: SomeObject
            }

            type SomeObject {
              bar: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "The type of SomeInputObject.foo must be Input Type"
                " but got: SomeObject.",
                "locations": [(7, 20)],
            }
        ]


def describe_type_system_input_object_field_default_values_must_be_valid():
    def rejects_an_input_object_field_with_invalid_default_values_sdl():
        schema = build_schema(
            """
            type Query {
              field(arg: SomeInputObject): Int
            }

            input SomeInputObject {
              field: Int = 3.14
            }
            """
        )

        assert validate_schema(schema) == [
            {
                "message": "SomeInputObject.field has invalid default value:"
                " Int cannot represent non-integer value: 3.14",
                "locations": [(7, 28)],
            }
        ]

    def rejects_an_input_object_field_with_invalid_default_values_programmatic():
        some_input_object = GraphQLInputObjectType(
            "SomeInputObject",
            {
                "field": GraphQLInputField(GraphQLInt, default_value=3.14),
            },
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "field": GraphQLField(
                        GraphQLInt,
                        args={"arg": GraphQLArgument(some_input_object)},
                    )
                },
            )
        )

        assert validate_schema(schema) == [
            {
                "message": "SomeInputObject.field has invalid default value:"
                " Int cannot represent non-integer value: 3.14",
            }
        ]


def describe_type_system_one_of_input_object_fields_must_be_nullable():
    def rejects_non_nullable_fields():
        schema = build_schema(
            """
            type Query {
              test(arg: SomeInputObject): String
            }

            input SomeInputObject @oneOf {
              a: String
              b: String!
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "OneOf input field SomeInputObject.b must be nullable.",
                "locations": [(8, 18)],
            }
        ]

    def rejects_fields_with_default_values():
        schema = build_schema(
            """
            type Query {
              test(arg: SomeInputObject): String
            }

            input SomeInputObject @oneOf {
              a: String
              b: String = "foo"
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "OneOf input field SomeInputObject.b"
                " cannot have a default value.",
                "locations": [(8, 15)],
            }
        ]


def describe_objects_must_adhere_to_interfaces_they_implement():
    def accepts_an_object_which_implements_an_interface():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              field(input: String): String
            }
            """
        )
        assert validate_schema(schema) == []

    def accepts_an_object_which_implements_an_interface_and_with_more_fields():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              field(input: String): String
              anotherField: String
            }
            """
        )
        assert validate_schema(schema) == []

    def accepts_an_object_which_implements_an_interface_field_with_more_args():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              field(input: String, anotherInput: String): String
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_object_missing_an_interface_field():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              anotherField: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field AnotherInterface.field expected but"
                " AnotherObject does not provide it.",
                "locations": [(7, 15), (10, 13)],
            }
        ]

    def rejects_an_object_with_an_incorrectly_typed_interface_field():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              field(input: String): Int
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field AnotherInterface.field"
                " expects type String but"
                " AnotherObject.field is type Int.",
                "locations": [(7, 37), (11, 37)],
            }
        ]

    def rejects_an_object_with_a_differently_typed_interface_field():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            type A { foo: String }
            type B { foo: String }

            interface AnotherInterface {
              field: A
            }

            type AnotherObject implements AnotherInterface {
              field: B
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field AnotherInterface.field"
                " expects type A but AnotherObject.field is type B.",
                "locations": [(10, 22), (14, 22)],
            }
        ]

    def accepts_an_object_with_a_subtyped_interface_field_interface():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: AnotherInterface
            }

            type AnotherObject implements AnotherInterface {
              field: AnotherObject
            }
            """
        )
        assert validate_schema(schema) == []

    def accepts_an_object_with_a_subtyped_interface_field_union():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            type SomeObject {
              field: String
            }

            union SomeUnionType = SomeObject

            interface AnotherInterface {
              field: SomeUnionType
            }

            type AnotherObject implements AnotherInterface {
              field: SomeObject
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_object_missing_an_interface_argument():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field argument"
                " AnotherInterface.field(input:) expected"
                " but AnotherObject.field does not provide it.",
                "locations": [(7, 21), (11, 15)],
            }
        ]

    def rejects_an_object_with_an_incorrectly_typed_interface_argument():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              field(input: Int): String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field argument"
                " AnotherInterface.field(input:) expects type String"
                " but AnotherObject.field(input:) is type Int.",
                "locations": [(7, 28), (11, 28)],
            }
        ]

    def rejects_an_object_with_an_incorrectly_typed_field_and_argument():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(input: String): String
            }

            type AnotherObject implements AnotherInterface {
              field(input: Int): Int
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field AnotherInterface.field expects"
                " type String but AnotherObject.field is type Int.",
                "locations": [(7, 37), (11, 34)],
            },
            {
                "message": "Interface field argument"
                " AnotherInterface.field(input:) expects type String"
                " but AnotherObject.field(input:) is type Int.",
                "locations": [(7, 28), (11, 28)],
            },
        ]

    def rejects_object_implementing_an_interface_field_with_additional_args():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field(baseArg: String): String
            }

            type AnotherObject implements AnotherInterface {
              field(
                baseArg: String,
                requiredArg: String!
                optionalArg1: String,
                optionalArg2: String = "",
              ): String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Argument 'AnotherObject.field(requiredArg:)'"
                " must not be required type 'String!' if not provided by the"
                " Interface field 'AnotherInterface.field'.",
                "locations": [(13, 17), (7, 15)],
            }
        ]

    def accepts_an_object_with_an_equivalently_wrapped_interface_field_type():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: [String]!
            }

            type AnotherObject implements AnotherInterface {
              field: [String]!
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_object_with_a_non_list_interface_field_list_type():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: [String]
            }

            type AnotherObject implements AnotherInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field AnotherInterface.field expects type"
                " [String] but AnotherObject.field is type String.",
                "locations": [(7, 22), (11, 22)],
            }
        ]

    def rejects_an_object_with_a_list_interface_field_non_list_type():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String
            }

            type AnotherObject implements AnotherInterface {
              field: [String]
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field AnotherInterface.field expects type"
                " String but AnotherObject.field is type [String].",
                "locations": [(7, 22), (11, 22)],
            }
        ]

    def accepts_an_object_with_a_subset_non_null_interface_field_type():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String
            }

            type AnotherObject implements AnotherInterface {
              field: String!
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_object_with_a_superset_nullable_interface_field_type():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface AnotherInterface {
              field: String!
            }

            type AnotherObject implements AnotherInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field AnotherInterface.field expects type"
                " String! but AnotherObject.field is type String.",
                "locations": [(7, 22), (11, 22)],
            }
        ]

    def rejects_an_object_missing_a_transitive_interface():
        schema = build_schema(
            """
            type Query {
              test: AnotherObject
            }

            interface SuperInterface {
              field: String!
            }

            interface AnotherInterface implements SuperInterface {
              field: String!
            }

            type AnotherObject implements AnotherInterface {
              field: String!
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type AnotherObject must implement SuperInterface"
                " because it is implemented by AnotherInterface.",
                "locations": [(10, 51), (14, 43)],
            }
        ]


def describe_interfaces_must_adhere_to_interface_they_implement():
    def accepts_an_interface_which_implements_an_interface():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              field(input: String): String
            }
            """
        )
        assert validate_schema(schema) == []

    def accepts_an_interface_which_implements_an_interface_along_with_more_fields():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              field(input: String): String
              anotherField: String
            }
            """
        )
        assert validate_schema(schema) == []

    def accepts_an_interface_which_implements_an_interface_with_additional_args():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              field(input: String, anotherInput: String): String
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_interface_missing_an_interface_field():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              anotherField: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field ParentInterface.field expected"
                " but ChildInterface does not provide it.",
                "locations": [(7, 15), (10, 13)],
            }
        ]

    def rejects_an_interface_with_an_incorrectly_typed_interface_field():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              field(input: String): Int
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field ParentInterface.field expects type String"
                " but ChildInterface.field is type Int.",
                "locations": [(7, 37), (11, 37)],
            }
        ]

    def rejects_an_interface_with_a_differently_typed_interface_field():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            type A { foo: String }
            type B { foo: String }

            interface ParentInterface {
              field: A
            }

            interface ChildInterface implements ParentInterface {
              field: B
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field ParentInterface.field expects type A"
                " but ChildInterface.field is type B.",
                "locations": [(10, 22), (14, 22)],
            }
        ]

    def accepts_an_interface_with_a_subtyped_interface_field_interface():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field: ParentInterface
            }

            interface ChildInterface implements ParentInterface {
              field: ChildInterface
            }
            """
        )
        assert validate_schema(schema) == []

    def accepts_an_interface_with_a_subtyped_interface_field_union():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            type SomeObject {
              field: String
            }

            union SomeUnionType = SomeObject

            interface ParentInterface {
              field: SomeUnionType
            }

            interface ChildInterface implements ParentInterface {
              field: SomeObject
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_interface_implementing_a_non_interface_type():
        schema = build_schema(
            """
            type Query {
              field: String
            }

            input SomeInputObject {
              field: String
            }

            interface BadInterface implements SomeInputObject {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type BadInterface must only implement Interface types,"
                " it cannot implement SomeInputObject.",
            }
        ]

    def rejects_an_interface_missing_an_interface_argument():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field argument ParentInterface.field(input:)"
                " expected but ChildInterface.field does not provide it.",
                "locations": [(7, 21), (11, 15)],
            }
        ]

    def rejects_an_interface_with_an_incorrectly_typed_interface_argument():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              field(input: Int): String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field argument ParentInterface.field(input:)"
                " expects type String but ChildInterface.field(input:) is type Int.",
                "locations": [(7, 28), (11, 28)],
            }
        ]

    def rejects_an_interface_with_both_an_incorrectly_typed_field_and_argument():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(input: String): String
            }

            interface ChildInterface implements ParentInterface {
              field(input: Int): Int
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field ParentInterface.field expects type String"
                " but ChildInterface.field is type Int.",
                "locations": [(7, 37), (11, 34)],
            },
            {
                "message": "Interface field argument ParentInterface.field(input:)"
                " expects type String but ChildInterface.field(input:) is type Int.",
                "locations": [(7, 28), (11, 28)],
            },
        ]

    def rejects_an_interface_implementing_an_interface_field_with_additional_args():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field(baseArg: String): String
            }

            interface ChildInterface implements ParentInterface {
              field(
                baseArg: String,
                requiredArg: String!
                optionalArg1: String,
                optionalArg2: String = "",
              ): String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Argument 'ChildInterface.field(requiredArg:)'"
                " must not be required type 'String!' if not provided by the"
                " Interface field 'ParentInterface.field'.",
                "locations": [(13, 17), (7, 15)],
            }
        ]

    def accepts_an_interface_with_an_equivalently_wrapped_interface_field_type():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field: [String]!
            }

            interface ChildInterface implements ParentInterface {
              field: [String]!
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_interface_with_a_non_list_interface_field_list_type():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field: [String]
            }

            interface ChildInterface implements ParentInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field ParentInterface.field"
                " expects type [String] but ChildInterface.field is type String.",
                "locations": [(7, 22), (11, 22)],
            }
        ]

    def rejects_an_interface_with_a_list_interface_field_non_list_type():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field: String
            }

            interface ChildInterface implements ParentInterface {
              field: [String]
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field ParentInterface.field expects type String"
                " but ChildInterface.field is type [String].",
                "locations": [(7, 22), (11, 22)],
            }
        ]

    def accepts_an_interface_with_a_subset_non_null_interface_field_type():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field: String
            }

            interface ChildInterface implements ParentInterface {
              field: String!
            }
            """
        )
        assert validate_schema(schema) == []

    def rejects_an_interface_with_a_superset_nullable_interface_field_type():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface ParentInterface {
              field: String!
            }

            interface ChildInterface implements ParentInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Interface field ParentInterface.field expects type String!"
                " but ChildInterface.field is type String.",
                "locations": [(7, 22), (11, 22)],
            }
        ]

    def rejects_an_object_missing_a_transitive_interface():
        schema = build_schema(
            """
            type Query {
              test: ChildInterface
            }

            interface SuperInterface {
              field: String!
            }

            interface ParentInterface implements SuperInterface {
              field: String!
            }

            interface ChildInterface implements ParentInterface {
              field: String!
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type ChildInterface must implement SuperInterface"
                " because it is implemented by ParentInterface.",
                "locations": [(10, 50), (14, 49)],
            }
        ]

    def rejects_a_self_reference_interface():
        schema = build_schema(
            """
            type Query {
            test: FooInterface
            }

            interface FooInterface implements FooInterface {
            field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type FooInterface cannot implement itself"
                " because it would create a circular reference.",
                "locations": [(6, 47)],
            }
        ]

    def rejects_a_circular_interface_implementation():
        schema = build_schema(
            """
            type Query {
              test: FooInterface
            }

            interface FooInterface implements BarInterface {
              field: String
            }

            interface BarInterface implements FooInterface {
              field: String
            }
            """
        )
        assert validate_schema(schema) == [
            {
                "message": "Type FooInterface cannot implement BarInterface"
                " because it would create a circular reference.",
                "locations": [(10, 47), (6, 47)],
            },
            {
                "message": "Type BarInterface cannot implement FooInterface"
                " because it would create a circular reference.",
                "locations": [(6, 47), (10, 47)],
            },
        ]


def describe_assert_valid_schema():
    def does_not_throw_on_valid_schemas():
        schema = build_schema(
            """
             type Query {
               foo: String
             }
            """
        )
        assert_valid_schema(schema)

    def combines_multiple_errors():
        schema = build_schema("type SomeType")
        with pytest.raises(TypeError) as exc_info:
            assert_valid_schema(schema)
        assert (
            str(exc_info.value)
            == dedent(
                """
            Query root type must be provided.

            Type SomeType must define one or more fields.
            """
            ).rstrip()
        )
