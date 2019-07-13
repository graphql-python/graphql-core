from functools import partial
from typing import cast, List

from pytest import mark, raises  # type: ignore

from graphql.language import parse
from graphql.pyutils import FrozenList
from graphql.type import (
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputType,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
    validate_schema,
    GraphQLArgument,
    GraphQLDirective,
)
from graphql.utilities import build_schema, extend_schema


SomeScalarType = GraphQLScalarType(name="SomeScalar")

SomeObjectType: GraphQLObjectType

SomeInterfaceType = GraphQLInterfaceType(
    name="SomeInterface", fields=lambda: {"f": GraphQLField(SomeObjectType)}
)

SomeObjectType = GraphQLObjectType(
    name="SomeObject",
    fields=lambda: {"f": GraphQLField(SomeObjectType)},
    interfaces=[SomeInterfaceType],
)

SomeUnionType = GraphQLUnionType(name="SomeUnion", types=[SomeObjectType])

SomeEnumType = GraphQLEnumType(name="SomeEnum", values={"ONLY": GraphQLEnumValue()})

SomeInputObjectType = GraphQLInputObjectType(
    name="SomeInputObject",
    fields={"val": GraphQLInputField(GraphQLString, default_value="hello")},
)


def with_modifiers(types: List) -> List:
    # noinspection PyTypeChecker
    return (
        types
        + [GraphQLList(t) for t in types]
        + [GraphQLNonNull(t) for t in types]
        + [GraphQLNonNull(GraphQLList(t)) for t in types]
    )


output_types: List[GraphQLOutputType] = with_modifiers(
    [
        GraphQLString,
        SomeScalarType,
        SomeEnumType,
        SomeObjectType,
        SomeUnionType,
        SomeInterfaceType,
    ]
)

not_output_types: List[GraphQLInputType] = with_modifiers([SomeInputObjectType])

input_types: List[GraphQLInputType] = with_modifiers(
    [GraphQLString, SomeScalarType, SomeEnumType, SomeInputObjectType]
)

not_input_types: List[GraphQLOutputType] = with_modifiers(
    [SomeObjectType, SomeUnionType, SomeInterfaceType]
)

parametrize_type = partial(
    mark.parametrize("type_", ids=lambda type_: type_.__class__.__name__)
)


def schema_with_field_type(type_):
    return GraphQLSchema(
        query=GraphQLObjectType(name="Query", fields={"f": GraphQLField(type_)}),
        types=[type_],
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

    def rejects_a_schema_whose_directives_are_incorrectly_typed():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            GraphQLSchema(
                SomeObjectType, directives=[cast(GraphQLDirective, "somedirective")]
            )
        msg = str(exc_info.value)
        assert msg == (
            "Schema directives must be specified"
            " as a sequence of GraphQLDirective instances."
        )

        schema = GraphQLSchema(SomeObjectType)
        schema.directives = FrozenList([cast(GraphQLDirective, "somedirective")])

        msg = validate_schema(schema)[0].message
        assert msg == "Expected directive but got: 'somedirective'."


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
            GraphQLObjectType(
                "SomeObject", {"bad-name-with-dashes": GraphQLField(GraphQLString)}
            )
        )
        msg = validate_schema(schema)[0].message
        assert msg == (
            "Names must match /^[_a-zA-Z][_a-zA-Z0-9]*$/"
            " but 'bad-name-with-dashes' does not."
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

    def reject_field_args_with_invalid_names():
        QueryType = GraphQLObjectType(
            "SomeObject",
            {
                "badField": GraphQLField(
                    GraphQLString,
                    args={"bad-name-with-dashes": GraphQLArgument(GraphQLString)},
                )
            },
        )
        schema = GraphQLSchema(QueryType)
        msg = validate_schema(schema)[0].message
        assert msg == (
            "Names must match /^[_a-zA-Z][_a-zA-Z0-9]*$/"
            " but 'bad-name-with-dashes' does not."
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
                "message": "Union type BadUnion must define one or more"
                " member types.",
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
            " as a sequence of GraphQLObjectType instances."
        )

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
            # invalid schema cannot be built with Python
            with raises(TypeError) as exc_info:
                schema_with_field_type(
                    GraphQLUnionType("BadUnion", types=[member_type])
                )
            assert str(exc_info.value) == (
                "BadUnion types must be specified"
                " as a sequence of GraphQLObjectType instances."
            )


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
        msg = str(exc_info.value)
        assert msg == (
            "SomeInputObject fields cannot be resolved:"
            " Input field type must be a GraphQL input type."
        )


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
        def schema_with_enum(name):
            return schema_with_field_type(
                GraphQLEnumType("SomeEnum", {name: GraphQLEnumValue(1)})
            )

        schema1 = schema_with_enum("#value")
        msg = validate_schema(schema1)[0].message
        assert msg == (
            "Names must match /^[_a-zA-Z][_a-zA-Z0-9]*$/ but '#value' does not."
        )

        schema2 = schema_with_enum("1value")
        msg = validate_schema(schema2)[0].message
        assert msg == (
            "Names must match /^[_a-zA-Z][_a-zA-Z0-9]*$/ but '1value' does not."
        )

        schema3 = schema_with_enum("KEBAB-CASE")
        msg = validate_schema(schema3)[0].message
        assert msg == (
            "Names must match /^[_a-zA-Z][_a-zA-Z0-9]*$/ but 'KEBAB-CASE' does not."
        )

        schema4 = schema_with_enum("true")
        msg = validate_schema(schema4)[0].message
        assert msg == "Enum type SomeEnum cannot include value: true."

        schema5 = schema_with_enum("false")
        msg = validate_schema(schema5)[0].message
        assert msg == "Enum type SomeEnum cannot include value: false."

        schema6 = schema_with_enum("null")
        msg = validate_schema(schema6)[0].message
        assert msg == "Enum type SomeEnum cannot include value: null."


def describe_type_system_object_fields_must_have_output_types():
    def _schema_with_object_field_of_type(field_type: GraphQLOutputType):
        BadObjectType = GraphQLObjectType(
            "BadObject", {"badField": GraphQLField(field_type)}
        )
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(BadObjectType)}),
            types=[SomeObjectType],
        )

    @parametrize_type(output_types)
    def accepts_an_output_type_as_an_object_field_type(type_):
        schema = _schema_with_object_field_of_type(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_object_field_type():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_object_field_of_type(None)
        msg = str(exc_info.value)
        assert msg == "Field type must be an output type."

    @parametrize_type(not_output_types)
    def rejects_a_non_output_type_as_an_object_field_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_object_field_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Field type must be an output type."

    @parametrize_type([int, float, str])
    def rejects_a_non_type_value_as_an_object_field_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_object_field_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Field type must be an output type."

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
        msg = str(exc_info.value)
        assert msg == (
            "Query fields cannot be resolved: Field type must be an output type."
        )


def describe_type_system_objects_can_only_implement_unique_interfaces():
    def rejects_an_object_implementing_a_non_type_values():
        schema = GraphQLSchema(
            query=GraphQLObjectType(
                "BadObject", {"f": GraphQLField(GraphQLString)}, interfaces=[]
            )
        )
        schema.query_type.interfaces.append(None)

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
            " as a sequence of GraphQLInterfaceType instances."
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
    def _schema_with_interface_field_of_type(field_type: GraphQLOutputType):
        BadInterfaceType = GraphQLInterfaceType(
            "BadInterface", {"badField": GraphQLField(field_type)}
        )
        BadImplementingType = GraphQLObjectType(
            "BadImplementing",
            {"badField": GraphQLField(field_type)},
            interfaces=[BadInterfaceType],
        )
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(BadInterfaceType)}),
            types=[BadImplementingType, SomeObjectType],
        )

    @parametrize_type(output_types)
    def accepts_an_output_type_as_an_interface_field_type(type_):
        schema = _schema_with_interface_field_of_type(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_interface_field_type():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_interface_field_of_type(None)
        msg = str(exc_info.value)
        assert msg == "Field type must be an output type."

    @parametrize_type(not_output_types)
    def rejects_a_non_output_type_as_an_interface_field_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_interface_field_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Field type must be an output type."

    @parametrize_type([int, float, str])
    def rejects_a_non_type_value_as_an_interface_field_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_interface_field_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Field type must be an output type."

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
        msg = str(exc_info.value)
        assert msg == (
            "SomeInterface fields cannot be resolved:"
            " Field type must be an output type."
        )

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


def describe_type_system_field_arguments_must_have_input_types():
    def _schema_with_arg_of_type(arg_type: GraphQLInputType):
        BadObjectType = GraphQLObjectType(
            "BadObject",
            {
                "badField": GraphQLField(
                    GraphQLString, args={"badArg": GraphQLArgument(arg_type)}
                )
            },
        )
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(BadObjectType)})
        )

    @parametrize_type(input_types)
    def accepts_an_input_type_as_a_field_arg_type(type_):
        schema = _schema_with_arg_of_type(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_field_arg_type():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_arg_of_type(None)
        msg = str(exc_info.value)
        assert msg == "Argument type must be a GraphQL input type."

    @parametrize_type(not_input_types)
    def rejects_a_non_input_type_as_a_field_arg_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_arg_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Argument type must be a GraphQL input type."

    @parametrize_type([int, float, str])
    def rejects_a_non_type_value_as_a_field_arg_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_arg_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Argument type must be a GraphQL input type."

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
        msg = str(exc_info.value)
        assert msg == (
            "Query fields cannot be resolved:"
            " Argument type must be a GraphQL input type."
        )


def describe_type_system_input_object_fields_must_have_input_types():
    def _schema_with_input_field_of_type(input_field_type: GraphQLInputType):
        BadInputObjectType = GraphQLInputObjectType(
            "BadInputObject", {"badField": GraphQLInputField(input_field_type)}
        )
        return GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "f": GraphQLField(
                        GraphQLString,
                        args={"badArg": GraphQLArgument(BadInputObjectType)},
                    )
                },
            )
        )

    @parametrize_type(input_types)
    def accepts_an_input_type_as_an_input_fieldtype(type_):
        schema = _schema_with_input_field_of_type(type_)
        assert validate_schema(schema) == []

    def rejects_an_empty_input_field_type():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_input_field_of_type(None)
        msg = str(exc_info.value)
        assert msg == "Input field type must be a GraphQL input type."

    @parametrize_type(not_input_types)
    def rejects_a_non_input_type_as_an_input_field_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_input_field_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Input field type must be a GraphQL input type."

    @parametrize_type([int, float, str])
    def rejects_a_non_type_value_as_an_input_field_type(type_):
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            _schema_with_input_field_of_type(type_)
        msg = str(exc_info.value)
        assert msg == "Input field type must be a GraphQL input type."

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
        msg = str(exc_info.value)
        assert msg == (
            "SomeInputObject fields cannot be resolved:"
            " Input field type must be a GraphQL input type."
        )


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

    def rejects_an_object_with_an_incorrectly_typed_field_and__argument():
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

    def rejects_a_object_with_a_list_interface_field_non_list_type():
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

    def rejects_a_object_with_a_superset_nullable_interface_field_type():
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
