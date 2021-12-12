from operator import attrgetter
from typing import Any, List, Union

from pytest import mark, raises

from graphql.language import parse, DirectiveLocation
from graphql.pyutils import inspect
from graphql.type import (
    assert_directive,
    assert_enum_type,
    assert_input_object_type,
    assert_interface_type,
    assert_object_type,
    assert_scalar_type,
    assert_union_type,
    assert_valid_schema,
    is_input_type,
    is_output_type,
    validate_schema,
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputType,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
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
) -> List[Union[GraphQLNamedType, GraphQLNonNull, GraphQLList]]:
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
                "message": "Query root type must be Object type,"
                " it cannot be Query.",
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
                  mutation: SomeInputObject
                }
                """
            ),
        )
        schema = extend_schema(
            schema,
            parse(
                """
                extend schema {
                  subscription: SomeInputObject
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
                " if provided, it cannot be SomeInputObject.",
                "locations": [(3, 29)],
            },
            {
                "message": "Subscription root type must be Object type"
                " if provided, it cannot be SomeInputObject.",
                "locations": [(3, 33)],
            },
        ]

    def rejects_a_schema_whose_types_are_incorrectly_type():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLSchema(
                SomeObjectType,
                types=[{"name": "SomeType"}, SomeDirective],  # type: ignore
            )
        assert str(exc_info.value) == (
            "Schema types must be specified as a collection of GraphQL types."
        )
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
            GraphQLObjectType("IncompleteObject", lambda: {})
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
        with raises(TypeError) as exc_info:
            build_schema(
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
        assert str(exc_info.value) == (
            "BadUnion types must be specified"
            " as a collection of GraphQLObjectType instances."
        )
        # construct invalid schema manually
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
              | TypeA
              | TypeB
            """
        )
        with raises(TypeError) as exc_info:
            extend_schema(schema, parse("extend union BadUnion = Int"))
        assert str(exc_info.value) == (
            "BadUnion types must be specified"
            " as a collection of GraphQLObjectType instances."
        )
        schema = extend_schema(schema, parse("extend union BadUnion = TypeB"))
        bad_union: Any = schema.get_type("BadUnion")
        assert bad_union.types[1].name == "TypeA"
        bad_union.types[1] = GraphQLString
        assert bad_union.types[3].name == "TypeB"
        bad_union.types[3] = GraphQLInt
        bad_union.ast_node.types[1].name.value = "String"
        bad_union.extension_ast_nodes[0].types[0].name.value = "Int"
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
                "BadUnion", types=[member_type]  # type: ignore
            )
            with raises(TypeError) as exc_info:
                schema_with_field_type(bad_union)
            assert str(exc_info.value) == (
                "BadUnion types must be specified"
                " as a collection of GraphQLObjectType instances."
            )
            # noinspection PyPropertyAccess
            bad_union.types = []
            bad_schema = schema_with_field_type(bad_union)
            # noinspection PyPropertyAccess
            bad_union.types = [member_type]
            assert validate_schema(bad_schema) == [
                {
                    "message": "Union type BadUnion can only include Object types,"
                    + f" it cannot include {inspect(member_type)}."
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
                "message": "Cannot reference Input Object 'SomeInputObject'"
                " within itself through a series of non-null fields:"
                " 'startLoop.nextInLoop.closeLoop'.",
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
                "message": "Cannot reference Input Object 'SomeInputObject'"
                " within itself through a series of non-null fields:"
                " 'startLoop.closeLoop'.",
                "locations": [(7, 15), (11, 15)],
            },
            {
                "message": "Cannot reference Input Object 'AnotherInputObject'"
                " within itself through a series of non-null fields:"
                " 'startSecondLoop.closeSecondLoop'.",
                "locations": [(12, 15), (16, 15)],
            },
            {
                "message": "Cannot reference Input Object 'YetAnotherInputObject'"
                " within itself through a series of non-null fields:"
                " 'nonNullSelf'.",
                "locations": [(17, 15)],
            },
        ]

    def rejects_an_input_object_type_with_incorrectly_typed_fields():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
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
        assert str(exc_info.value) == (
            "SomeInputObject fields cannot be resolved."
            " Input field type must be a GraphQL input type."
        )
        # construct invalid schema manually
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
              badObject: SomeInputObject
              badUnion: SomeInputObject
              goodInputObject: SomeInputObject
            }
            """
        )
        some_input_obj: Any = schema.get_type("SomeInputObject")
        some_input_obj.fields["badObject"].type = schema.get_type("SomeObject")
        some_input_obj.fields["badUnion"].type = schema.get_type("SomeUnion")
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

    def rejects_an_input_object_type_with_required_arguments_that_is_deprecated():
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
        if is_output_type(type_):
            field = GraphQLField(type_)
        else:
            # invalid field cannot be built with Python directly
            with raises(TypeError) as exc_info:
                GraphQLField(type_)
            assert str(exc_info.value) == "Field type must be an output type."
            # therefore we need to monkey-patch a valid field
            field = GraphQLField(GraphQLString)
            field.type = type_
        bad_object_type = GraphQLObjectType("BadObject", {"badField": field})
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(bad_object_type)}),
            types=[SomeObjectType],
        )

    @mark.parametrize("type_", output_types, ids=get_name)
    def accepts_an_output_type_as_an_object_field_type(type_):
        schema = _schema_with_object_field(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_object_field_type():
        # noinspection PyTypeChecker
        schema = _schema_with_object_field(None)  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of BadObject.badField must be Output Type"
                " but got: None."
            }
        ]

    @mark.parametrize("type_", not_output_types, ids=get_name)
    def rejects_a_non_output_type_as_an_object_field_type(type_):
        schema = _schema_with_object_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadObject.badField must be Output Type"
                f" but got: {type_}."
            }
        ]

    @mark.parametrize("type_", not_graphql_types, ids=get_name)
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
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
                """
                type Query {
                  field: [SomeInputObject]
                }

                input SomeInputObject {
                  field: String
                }
                """
            )
        assert str(exc_info.value) == (
            "Query fields cannot be resolved. Field type must be an output type."
        )
        # therefore we need to monkey-patch a valid schema
        schema = build_schema(
            """
            type Query {
              field: [String]
            }

            input SomeInputObject {
              field: String
            }
            """
        )
        some_input_obj = schema.get_type("SomeInputObject")
        schema.query_type.fields["field"].type.of_type = some_input_obj  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of Query.field must be Output Type"
                " but got: [SomeInputObject].",
                "locations": [(3, 22)],
            }
        ]


def describe_type_system_objects_can_only_implement_unique_interfaces():
    def rejects_an_object_implementing_a_non_type_values():
        query_type = GraphQLObjectType(
            "BadObject", {"f": GraphQLField(GraphQLString)}, interfaces=[]
        )
        # noinspection PyTypeChecker
        query_type.interfaces.append(None)
        schema = GraphQLSchema(query_type)

        assert validate_schema(schema) == [
            {
                "message": "Type BadObject must only implement Interface types,"
                " it cannot implement None."
            }
        ]

    def rejects_an_object_implementing_a_non_interface_type():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
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
        assert str(exc_info.value) == (
            "BadObject interfaces must be specified"
            " as a collection of GraphQLInterfaceType instances."
        )

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
        if is_output_type(type_):
            field = GraphQLField(type_)
        else:
            # invalid field cannot be built with Python directly
            with raises(TypeError) as exc_info:
                GraphQLField(type_)
            assert str(exc_info.value) == "Field type must be an output type."
            # therefore we need to monkey-patch a valid field
            field = GraphQLField(GraphQLString)
            field.type = type_
        fields = {"badField": field}

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

    @mark.parametrize("type_", output_types, ids=get_name)
    def accepts_an_output_type_as_an_interface_field_type(type_):
        schema = _schema_with_interface_field(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_interface_field_type():
        # noinspection PyTypeChecker
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

    @mark.parametrize("type_", not_output_types, ids=get_name)
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

    @mark.parametrize("type_", not_graphql_types, ids=get_name)
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
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
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
        assert str(exc_info.value) == (
            "SomeInterface fields cannot be resolved."
            " Field type must be an output type."
        )
        # therefore we need to monkey-patch a valid schema
        schema = build_schema(
            """
            type Query {
              test: SomeInterface
            }

            interface SomeInterface {
              field: String
            }

            input SomeInputObject {
              foo: String
            }

            type SomeObject implements SomeInterface {
              field: String
            }
            """
        )
        # therefore we need to monkey-patch a valid schema
        some_input_obj = schema.get_type("SomeInputObject")
        some_interface: Any = schema.get_type("SomeInterface")
        some_interface.fields["field"].type = some_input_obj
        some_object: Any = schema.get_type("SomeObject")
        some_object.fields["field"].type = some_input_obj
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
        if is_input_type(type_):
            argument = GraphQLArgument(type_)
        else:
            # invalid argument cannot be built with Python directly
            with raises(TypeError) as exc_info:
                GraphQLArgument(type_)
            assert str(exc_info.value) == "Argument type must be a GraphQL input type."
            # therefore we need to monkey-patch a valid argument
            argument = GraphQLArgument(GraphQLString)
            argument.type = type_
        args = {"badArg": argument}
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

    @mark.parametrize("type_", input_types, ids=get_name)
    def accepts_an_input_type_as_a_field_arg_type(type_):
        schema = _schema_with_arg(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_field_arg_type():
        # noinspection PyTypeChecker
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

    @mark.parametrize("type_", not_input_types, ids=get_name)
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

    @mark.parametrize("type_", not_graphql_types, ids=get_name)
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
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
                """
                type Query {
                  test(arg: SomeObject): String
                }

                type SomeObject {
                  foo: String
                }
                """
            )
        assert str(exc_info.value) == (
            "Query fields cannot be resolved."
            " Argument type must be a GraphQL input type."
        )
        # therefore we need to monkey-patch a valid schema
        schema = build_schema(
            """
            type Query {
              test(arg: String): String
            }

            type SomeObject {
              foo: String
            }
            """
        )
        some_object = schema.get_type("SomeObject")
        schema.query_type.fields["test"].args["arg"].type = some_object  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of Query.test(arg:) must be Input Type"
                " but got: SomeObject.",
                "locations": [(3, 25)],
            },
        ]


def describe_type_system_input_object_fields_must_have_input_types():
    def _schema_with_input_field(type_: GraphQLInputType) -> GraphQLSchema:
        if is_input_type(type_):
            input_field = GraphQLInputField(type_)
        else:
            # invalid input field cannot be built with Python directly
            with raises(TypeError) as exc_info:
                GraphQLInputField(type_)
            assert str(exc_info.value) == (
                "Input field type must be a GraphQL input type."
            )
            # therefore we need to monkey-patch a valid input field
            input_field = GraphQLInputField(GraphQLString)
            input_field.type = type_
        bad_input_object_type = GraphQLInputObjectType(
            "BadInputObject", {"badField": input_field}
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

    @mark.parametrize("type_", input_types, ids=get_name)
    def accepts_an_input_type_as_an_input_field_type(type_):
        schema = _schema_with_input_field(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_input_field_type():
        # noinspection PyTypeChecker
        schema = _schema_with_input_field(None)  # type: ignore
        assert validate_schema(schema) == [
            {
                "message": "The type of BadInputObject.badField must be Input Type"
                " but got: None."
            }
        ]

    @mark.parametrize("type_", not_input_types, ids=get_name)
    def rejects_a_non_input_type_as_an_input_field_type(type_):
        schema = _schema_with_input_field(type_)
        assert validate_schema(schema) == [
            {
                "message": "The type of BadInputObject.badField must be Input Type"
                f" but got: {type_}."
            }
        ]

    @mark.parametrize("type_", not_graphql_types, ids=get_name)
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
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
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
        assert str(exc_info.value) == (
            "SomeInputObject fields cannot be resolved."
            " Input field type must be a GraphQL input type."
        )
        # therefore we need to monkey-patch a valid schema
        schema = build_schema(
            """
            type Query {
              test(arg: SomeInputObject): String
            }

            input SomeInputObject {
              foo: String
            }

            type SomeObject {
              bar: String
            }
            """
        )
        some_object = schema.get_type("SomeObject")
        some_input_object: Any = schema.get_type("SomeInputObject")
        some_input_object.fields["foo"].type = some_object
        assert validate_schema(schema) == [
            {
                "message": "The type of SomeInputObject.foo must be Input Type"
                " but got: SomeObject.",
                "locations": [(7, 20)],
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
                "message": "Object field AnotherObject.field includes required"
                " argument requiredArg that is missing from the"
                " Interface field AnotherInterface.field.",
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
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
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
        assert str(exc_info.value) == (
            "BadInterface interfaces must be specified as a collection"
            " of GraphQLInterfaceType instances."
        )
        # therefore we construct the invalid schema manually
        some_input_obj = GraphQLInputObjectType(
            "SomeInputObject", {"field": GraphQLInputField(GraphQLString)}
        )
        bad_interface = GraphQLInterfaceType(
            "BadInterface", {"field": GraphQLField(GraphQLString)}
        )
        # noinspection PyTypeChecker
        bad_interface.interfaces.append(some_input_obj)
        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"field": GraphQLField(GraphQLString)}),
            types=[bad_interface],
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
                "message": "Object field ChildInterface.field includes"
                " required argument requiredArg that is missing"
                " from the Interface field ParentInterface.field.",
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
    def do_not_throw_on_valid_schemas():
        schema = build_schema(
            (
                """
             type Query {
               foo: String
             }
            """
            )
        )
        assert_valid_schema(schema)

    def include_multiple_errors_into_a_description():
        schema = build_schema("type SomeType")
        with raises(TypeError) as exc_info:
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
