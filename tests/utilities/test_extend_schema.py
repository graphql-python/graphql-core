from typing import Union

from pytest import raises  # type: ignore

from graphql import graphql_sync
from graphql.language import parse, print_ast, DirectiveLocation, DocumentNode
from graphql.pyutils import dedent
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
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
    specified_directives,
    validate_schema,
)
from graphql.utilities import build_schema, extend_schema, print_schema

# Test schema.

SomeScalarType = GraphQLScalarType(name="SomeScalar")

SomeInterfaceType: GraphQLInterfaceType = GraphQLInterfaceType(
    name="SomeInterface",
    fields=lambda: {
        "name": GraphQLField(GraphQLString),
        "some": GraphQLField(SomeInterfaceType),
    },
)

FooType: GraphQLObjectType = GraphQLObjectType(
    name="Foo",
    interfaces=[SomeInterfaceType],
    fields=lambda: {
        "name": GraphQLField(GraphQLString),
        "some": GraphQLField(SomeInterfaceType),
        "tree": GraphQLField(GraphQLNonNull(GraphQLList(FooType))),
    },
)

BarType = GraphQLObjectType(
    name="Bar",
    interfaces=[SomeInterfaceType],
    fields=lambda: {
        "name": GraphQLField(GraphQLString),
        "some": GraphQLField(SomeInterfaceType),
        "foo": GraphQLField(FooType),
    },
)

BizType = GraphQLObjectType(
    name="Biz", fields=lambda: {"fizz": GraphQLField(GraphQLString)}
)

SomeUnionType = GraphQLUnionType(name="SomeUnion", types=[FooType, BizType])

SomeEnumType = GraphQLEnumType(
    name="SomeEnum", values={"ONE": GraphQLEnumValue(1), "TWO": GraphQLEnumValue(2)}
)

SomeInputType = GraphQLInputObjectType(
    "SomeInput", lambda: {"fooArg": GraphQLInputField(GraphQLString)}
)

FooDirective = GraphQLDirective(
    name="foo",
    args={"input": GraphQLArgument(SomeInputType)},
    is_repeatable=True,
    locations=[
        DirectiveLocation.SCHEMA,
        DirectiveLocation.SCALAR,
        DirectiveLocation.OBJECT,
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.ARGUMENT_DEFINITION,
        DirectiveLocation.INTERFACE,
        DirectiveLocation.UNION,
        DirectiveLocation.ENUM,
        DirectiveLocation.ENUM_VALUE,
        DirectiveLocation.INPUT_OBJECT,
        DirectiveLocation.INPUT_FIELD_DEFINITION,
    ],
)

test_schema = GraphQLSchema(
    query=GraphQLObjectType(
        name="Query",
        fields=lambda: {
            "foo": GraphQLField(FooType),
            "someScalar": GraphQLField(SomeScalarType),
            "someUnion": GraphQLField(SomeUnionType),
            "someEnum": GraphQLField(SomeEnumType),
            "someInterface": GraphQLField(
                SomeInterfaceType,
                args={"id": GraphQLArgument(GraphQLNonNull(GraphQLID))},
            ),
            "someInput": GraphQLField(
                GraphQLString, args={"input": GraphQLArgument(SomeInputType)}
            ),
        },
    ),
    types=[FooType, BarType],
    directives=specified_directives + [FooDirective],
)


def extend_test_schema(sdl, **options) -> GraphQLSchema:
    original_print = print_schema(test_schema)
    ast = parse(sdl)
    extended_schema = extend_schema(test_schema, ast, **options)
    assert print_schema(test_schema) == original_print
    return extended_schema


test_schema_ast = parse(print_schema(test_schema))
test_schema_definitions = [print_ast(node) for node in test_schema_ast.definitions]


def print_test_schema_changes(extended_schema):
    ast = parse(print_schema(extended_schema))
    ast.definitions = [
        node
        for node in ast.definitions
        if print_ast(node) not in test_schema_definitions
    ]
    return print_ast(ast)


TypeWithAstNode = Union[
    GraphQLArgument, GraphQLEnumValue, GraphQLField, GraphQLInputField, GraphQLNamedType
]


def print_ast_node(obj: TypeWithAstNode) -> str:
    assert obj is not None and obj.ast_node is not None
    return print_ast(obj.ast_node)


def describe_extend_schema():
    def returns_the_original_schema_when_there_are_no_type_definitions():
        extended_schema = extend_test_schema("{ field }")
        assert extended_schema == test_schema

    def extends_without_altering_original_schema():
        extended_schema = extend_test_schema(
            """
            extend type Query {
             newField: String
            }
            """
        )
        assert extend_schema != test_schema
        assert "newField" in print_schema(extended_schema)
        assert "newField" not in print_schema(test_schema)

    def can_be_used_for_limited_execution():
        extended_schema = extend_test_schema(
            """
            extend type Query {
              newField: String
            }
            """
        )

        result = graphql_sync(extended_schema, "{ newField }", {"newField": 123})
        assert result == ({"newField": "123"}, None)

    def can_describe_the_extended_fields():
        extended_schema = extend_test_schema(
            """
            extend type Query {
              "New field description."
              newField: String
            }
            """
        )
        query_type = assert_object_type(extended_schema.get_type("Query"))

        assert query_type.fields["newField"].description == "New field description."

    def extends_objects_by_adding_new_fields():
        extended_schema = extend_test_schema(
            """
            extend type Foo {
              newField: String
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Foo implements SomeInterface {
              name: String
              some: SomeInterface
              tree: [Foo]!
              newField: String
            }
            """
        )

        foo_type = assert_object_type(extended_schema.get_type("Foo"))
        query_type = assert_object_type(extended_schema.get_type("Query"))
        assert query_type.fields["foo"].type == foo_type

    def extends_objects_with_standard_type_fields():
        schema = build_schema("type Query")

        # Only String and Boolean are used by introspection types
        assert schema.get_type("Int") is None
        assert schema.get_type("Float") is None
        assert schema.get_type("String") is GraphQLString
        assert schema.get_type("Boolean") is GraphQLBoolean
        assert schema.get_type("ID") is None

        extend_ast = parse(
            """
            extend type Query {
              bool: Boolean
            }
            """
        )
        extended_schema = extend_schema(schema, extend_ast)

        assert extended_schema.get_type("Int") is None
        assert extended_schema.get_type("Float") is None
        assert extended_schema.get_type("String") is GraphQLString
        assert extended_schema.get_type("Boolean") is GraphQLBoolean
        assert extended_schema.get_type("ID") is None

        extend_twice_ast = parse(
            """
            extend type Query {
              int: Int
              float: Float
              id: ID
            }
            """
        )
        extended_twice_schema = extend_schema(schema, extend_twice_ast)

        assert extended_twice_schema.get_type("Int") is GraphQLInt
        assert extended_twice_schema.get_type("Float") is GraphQLFloat
        assert extended_twice_schema.get_type("String") is GraphQLString
        assert extended_twice_schema.get_type("Boolean") is GraphQLBoolean
        assert extended_twice_schema.get_type("ID") is GraphQLID

    def extends_enums_by_adding_new_values():
        extended_schema = extend_test_schema(
            """
            extend enum SomeEnum {
              NEW_ENUM
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            enum SomeEnum {
              ONE
              TWO
              NEW_ENUM
            }
            """
        )

        some_enum_type = extended_schema.get_type("SomeEnum")
        query_type = assert_object_type(extended_schema.get_type("Query"))
        enum_field = query_type.fields["someEnum"]
        assert enum_field.type == some_enum_type

    def extends_unions_by_adding_new_types():
        extended_schema = extend_test_schema(
            """
            extend union SomeUnion = Bar
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            union SomeUnion = Foo | Biz | Bar
            """
        )

        some_union_type = extended_schema.get_type("SomeUnion")
        query_type = assert_object_type(extended_schema.get_type("Query"))
        union_field = query_type.fields["someUnion"]
        assert union_field.type == some_union_type

    def allows_extension_of_union_by_adding_itself():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            extend_test_schema(
                """
                extend union SomeUnion = SomeUnion
                """
            )
        assert str(exc_info.value) == (
            "SomeUnion types must be specified"
            " as a sequence of GraphQLObjectType instances."
        )

    def extends_inputs_by_adding_new_fields():
        extended_schema = extend_test_schema(
            """
            extend input SomeInput {
              newField: String
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            input SomeInput {
              fooArg: String
              newField: String
            }
            """
        )

        some_input_type = extended_schema.get_type("SomeInput")
        query_type = assert_object_type(extended_schema.get_type("Query"))
        input_field = query_type.fields["someInput"]
        assert input_field.args["input"].type == some_input_type

        foo_directive = assert_directive(extended_schema.get_directive("foo"))
        assert foo_directive.args["input"].type == some_input_type

    def extends_scalars_by_adding_new_directives():
        extended_schema = extend_test_schema(
            """
            extend scalar SomeScalar @foo
            """
        )

        some_scalar = assert_scalar_type(extended_schema.get_type("SomeScalar"))
        assert some_scalar.extension_ast_nodes
        assert list(map(print_ast, some_scalar.extension_ast_nodes)) == [
            "extend scalar SomeScalar @foo"
        ]

    def correctly_assigns_ast_nodes_to_new_and_extended_types():
        extended_schema = extend_test_schema(
            """
            extend type Query {
              newField(testArg: TestInput): TestEnum
            }

            extend scalar SomeScalar @foo

            extend enum SomeEnum {
              NEW_VALUE
            }

            extend union SomeUnion = Bar

            extend input SomeInput {
              newField: String
            }

            extend interface SomeInterface {
              newField: String
            }

            enum TestEnum {
              TEST_VALUE
            }

            input TestInput {
              testInputField: TestEnum
            }
            """
        )
        ast = parse(
            """
            extend type Query {
              oneMoreNewField: TestUnion
            }

            extend scalar SomeScalar @test

            extend enum SomeEnum {
              ONE_MORE_NEW_VALUE
            }

            extend union SomeUnion = TestType

            extend input SomeInput {
              oneMoreNewField: String
            }

            extend interface SomeInterface {
              oneMoreNewField: String
            }

            union TestUnion = TestType

            interface TestInterface {
              interfaceField: String
            }

            type TestType implements TestInterface {
              interfaceField: String
            }

            directive @test(arg: Int) repeatable on FIELD | SCALAR
            """
        )
        extended_twice_schema = extend_schema(extended_schema, ast)

        query = assert_object_type(extended_twice_schema.get_type("Query"))
        some_enum = assert_enum_type(extended_twice_schema.get_type("SomeEnum"))
        some_union = assert_union_type(extended_twice_schema.get_type("SomeUnion"))
        some_scalar = assert_scalar_type(extended_twice_schema.get_type("SomeScalar"))
        some_input = assert_input_object_type(
            extended_twice_schema.get_type("SomeInput")
        )
        some_interface = assert_interface_type(
            extended_twice_schema.get_type("SomeInterface")
        )

        test_input = assert_input_object_type(
            extended_twice_schema.get_type("TestInput")
        )
        test_enum = assert_enum_type(extended_twice_schema.get_type("TestEnum"))
        test_union = assert_union_type(extended_twice_schema.get_type("TestUnion"))
        test_type = assert_object_type(extended_twice_schema.get_type("TestType"))
        test_interface = assert_interface_type(
            extended_twice_schema.get_type("TestInterface")
        )
        test_directive = assert_directive(extended_twice_schema.get_directive("test"))

        assert test_type.extension_ast_nodes is None
        assert test_enum.extension_ast_nodes is None
        assert test_union.extension_ast_nodes is None
        assert test_input.extension_ast_nodes is None
        assert test_interface.extension_ast_nodes is None

        assert len(query.extension_ast_nodes) == 2
        assert len(some_scalar.extension_ast_nodes) == 2
        assert len(some_enum.extension_ast_nodes) == 2
        assert len(some_union.extension_ast_nodes) == 2
        assert len(some_input.extension_ast_nodes) == 2
        assert len(some_interface.extension_ast_nodes) == 2

        definitions = [
            test_input.ast_node,
            test_enum.ast_node,
            test_union.ast_node,
            test_interface.ast_node,
            test_type.ast_node,
            test_directive.ast_node,
        ]
        for extension_ast_nodes in [
            query.extension_ast_nodes,
            some_scalar.extension_ast_nodes,
            some_enum.extension_ast_nodes,
            some_union.extension_ast_nodes,
            some_input.extension_ast_nodes,
            some_interface.extension_ast_nodes,
        ]:
            if extension_ast_nodes:
                definitions.extend(extension_ast_nodes)
        restored_extension_ast = DocumentNode(definitions=definitions)

        assert print_schema(
            extend_schema(test_schema, restored_extension_ast)
        ) == print_schema(extended_twice_schema)

        new_field = query.fields["newField"]
        assert print_ast_node(new_field) == "newField(testArg: TestInput): TestEnum"
        assert print_ast_node(new_field.args["testArg"]) == "testArg: TestInput"
        assert (
            print_ast_node(query.fields["oneMoreNewField"])
            == "oneMoreNewField: TestUnion"
        )

        new_value = some_enum.values["NEW_VALUE"]
        assert some_enum
        assert print_ast_node(new_value) == "NEW_VALUE"

        one_more_new_value = some_enum.values["ONE_MORE_NEW_VALUE"]
        assert one_more_new_value
        assert print_ast_node(one_more_new_value) == "ONE_MORE_NEW_VALUE"
        assert print_ast_node(some_input.fields["newField"]) == "newField: String"
        assert (
            print_ast_node(some_input.fields["oneMoreNewField"])
            == "oneMoreNewField: String"
        )
        assert print_ast_node(some_interface.fields["newField"]) == "newField: String"
        assert (
            print_ast_node(some_interface.fields["oneMoreNewField"])
            == "oneMoreNewField: String"
        )

        assert (
            print_ast_node(test_input.fields["testInputField"])
            == "testInputField: TestEnum"
        )

        test_value = test_enum.values["TEST_VALUE"]
        assert test_value
        assert print_ast_node(test_value) == "TEST_VALUE"

        assert (
            print_ast_node(test_interface.fields["interfaceField"])
            == "interfaceField: String"
        )
        assert (
            print_ast_node(test_type.fields["interfaceField"])
            == "interfaceField: String"
        )
        assert print_ast_node(test_directive.args["arg"]) == "arg: Int"

    def builds_types_with_deprecated_fields_and_values():
        extended_schema = extend_test_schema(
            """
            type TypeWithDeprecatedField {
              newDeprecatedField: String @deprecated(reason: "not used anymore")
            }

            enum EnumWithDeprecatedValue {
              DEPRECATED @deprecated(reason: "do not use")
            }
            """
        )

        deprecated_field_def = assert_object_type(
            extended_schema.get_type("TypeWithDeprecatedField")
        ).fields["newDeprecatedField"]
        assert deprecated_field_def.is_deprecated is True
        assert deprecated_field_def.deprecation_reason == "not used anymore"

        deprecated_enum_def = assert_enum_type(
            extended_schema.get_type("EnumWithDeprecatedValue")
        ).values["DEPRECATED"]
        assert deprecated_enum_def.is_deprecated is True
        assert deprecated_enum_def.deprecation_reason == "do not use"

    def extends_objects_with_deprecated_fields():
        extended_schema = extend_test_schema(
            """
            extend type Foo {
              deprecatedField: String @deprecated(reason: "not used anymore")
            }
            """
        )
        foo_type = assert_object_type(extended_schema.get_type("Foo"))
        deprecated_field_def = foo_type.fields["deprecatedField"]
        assert deprecated_field_def.is_deprecated is True
        assert deprecated_field_def.deprecation_reason == "not used anymore"

    def extend_enums_with_deprecated_values():
        extended_schema = extend_test_schema(
            """
            extend enum SomeEnum {
              DEPRECATED @deprecated(reason: "do not use")
            }
            """
        )
        enum_type = assert_enum_type(extended_schema.get_type("SomeEnum"))
        deprecated_enum_def = enum_type.values["DEPRECATED"]
        assert deprecated_enum_def.is_deprecated is True
        assert deprecated_enum_def.deprecation_reason == "do not use"

    def adds_new_unused_object_type():
        extended_schema = extend_test_schema(
            """
            type Unused {
              someField: String
            }
            """
        )
        assert extended_schema != test_schema
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Unused {
              someField: String
            }
            """
        )

    def adds_new_unused_enum_type():
        extended_schema = extend_test_schema(
            """
            enum UnusedEnum {
              SOME
            }
            """
        )
        assert extended_schema != test_schema
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            enum UnusedEnum {
              SOME
            }
            """
        )

    def adds_new_unused_input_object_type():
        extended_schema = extend_test_schema(
            """
            input UnusedInput {
              someInput: String
            }
            """
        )
        assert extended_schema != test_schema
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            input UnusedInput {
              someInput: String
            }
            """
        )

    def adds_new_union_using_new_object_type():
        extended_schema = extend_test_schema(
            """
            type DummyUnionMember {
              someField: String
            }

            union UnusedUnion = DummyUnionMember
            """
        )
        assert extended_schema != test_schema
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type DummyUnionMember {
              someField: String
            }

            union UnusedUnion = DummyUnionMember
            """
        )

    def extends_objects_by_adding_new_fields_with_arguments():
        extended_schema = extend_test_schema(
            """
            extend type Foo {
              newField(arg1: String, arg2: NewInputObj!): String
            }

            input NewInputObj {
              field1: Int
              field2: [Float]
              field3: String!
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Foo implements SomeInterface {
              name: String
              some: SomeInterface
              tree: [Foo]!
              newField(arg1: String, arg2: NewInputObj!): String
            }

            input NewInputObj {
              field1: Int
              field2: [Float]
              field3: String!
            }
            """
        )

    def extends_objects_by_adding_new_fields_with_existing_types():
        extended_schema = extend_test_schema(
            """
            extend type Foo {
              newField(arg1: SomeEnum!): SomeEnum
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Foo implements SomeInterface {
              name: String
              some: SomeInterface
              tree: [Foo]!
              newField(arg1: SomeEnum!): SomeEnum
            }
            """
        )

    def extends_objects_by_adding_implemented_interfaces():
        extended_schema = extend_test_schema(
            """
            extend type Biz implements SomeInterface {
              name: String
              some: SomeInterface
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Biz implements SomeInterface {
              fizz: String
              name: String
              some: SomeInterface
            }
            """
        )

    def extends_objects_by_including_new_types():
        extended_schema = extend_test_schema(
            """
            extend type Foo {
              newObject: NewObject
              newInterface: NewInterface
              newUnion: NewUnion
              newScalar: NewScalar
              newEnum: NewEnum
              newTree: [Foo]!
            }

            type NewObject implements NewInterface {
              baz: String
            }

            type NewOtherObject {
              fizz: Int
            }

            interface NewInterface {
              baz: String
            }

            union NewUnion = NewObject | NewOtherObject

            scalar NewScalar

            enum NewEnum {
              OPTION_A
              OPTION_B
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Foo implements SomeInterface {
              name: String
              some: SomeInterface
              tree: [Foo]!
              newObject: NewObject
              newInterface: NewInterface
              newUnion: NewUnion
              newScalar: NewScalar
              newEnum: NewEnum
              newTree: [Foo]!
            }

            enum NewEnum {
              OPTION_A
              OPTION_B
            }

            interface NewInterface {
              baz: String
            }

            type NewObject implements NewInterface {
              baz: String
            }

            type NewOtherObject {
              fizz: Int
            }

            scalar NewScalar

            union NewUnion = NewObject | NewOtherObject
            """
        )

    def extends_objects_by_adding_implemented_new_interfaces():
        extended_schema = extend_test_schema(
            """
            extend type Foo implements NewInterface {
              baz: String
            }

            interface NewInterface {
              baz: String
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Foo implements SomeInterface & NewInterface {
              name: String
              some: SomeInterface
              tree: [Foo]!
              baz: String
            }

            interface NewInterface {
              baz: String
            }
            """
        )

    def extends_different_types_multiple_times():
        extended_schema = extend_test_schema(
            """
            extend type Biz implements NewInterface {
              buzz: String
            }

            extend type Biz implements SomeInterface {
              name: String
              some: SomeInterface
              newFieldA: Int
            }

            extend type Biz {
              newFieldB: Float
            }

            interface NewInterface {
              buzz: String
            }

            extend enum SomeEnum {
              THREE
            }

            extend enum SomeEnum {
              FOUR
            }

            extend union SomeUnion = Boo

            extend union SomeUnion = Joo

            type Boo {
              fieldA: String
            }

            type Joo {
              fieldB: String
            }

            extend input SomeInput {
              fieldA: String
            }

            extend input SomeInput {
              fieldB: String
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Biz implements NewInterface & SomeInterface {
              fizz: String
              buzz: String
              name: String
              some: SomeInterface
              newFieldA: Int
              newFieldB: Float
            }

            type Boo {
              fieldA: String
            }

            type Joo {
              fieldB: String
            }

            interface NewInterface {
              buzz: String
            }

            enum SomeEnum {
              ONE
              TWO
              THREE
              FOUR
            }

            input SomeInput {
              fooArg: String
              fieldA: String
              fieldB: String
            }

            union SomeUnion = Foo | Biz | Boo | Joo
            """
        )

    def extends_interfaces_by_adding_new_fields():
        extended_schema = extend_test_schema(
            """
            extend interface SomeInterface {
              newField: String
            }

            extend type Bar {
              newField: String
            }

            extend type Foo {
              newField: String
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            type Bar implements SomeInterface {
              name: String
              some: SomeInterface
              foo: Foo
              newField: String
            }

            type Foo implements SomeInterface {
              name: String
              some: SomeInterface
              tree: [Foo]!
              newField: String
            }

            interface SomeInterface {
              name: String
              some: SomeInterface
              newField: String
            }
            """
        )

    def allows_extension_of_interface_with_missing_object_fields():
        extended_schema = extend_test_schema(
            """
            extend interface SomeInterface {
              newField: String
            }
            """
        )
        errors = validate_schema(extended_schema)
        assert errors
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            interface SomeInterface {
              name: String
              some: SomeInterface
              newField: String
            }
            """
        )

    def extends_interfaces_multiple_times():
        extended_schema = extend_test_schema(
            """
            extend interface SomeInterface {
              newFieldA: Int
            }

            extend interface SomeInterface {
              newFieldB(test: Boolean): String
            }
            """
        )
        assert print_test_schema_changes(extended_schema) == dedent(
            """
            interface SomeInterface {
              name: String
              some: SomeInterface
              newFieldA: Int
              newFieldB(test: Boolean): String
            }
            """
        )

    def may_extend_mutations_and_subscriptions():
        mutationSchema = GraphQLSchema(
            query=GraphQLObjectType(
                name="Query", fields=lambda: {"queryField": GraphQLField(GraphQLString)}
            ),
            mutation=GraphQLObjectType(
                name="Mutation",
                fields=lambda: {"mutationField": GraphQLField(GraphQLString)},
            ),
            subscription=GraphQLObjectType(
                name="Subscription",
                fields=lambda: {"subscriptionField": GraphQLField(GraphQLString)},
            ),
        )

        ast = parse(
            """
            extend type Query {
              newQueryField: Int
            }

            extend type Mutation {
              newMutationField: Int
            }

            extend type Subscription {
              newSubscriptionField: Int
            }
            """
        )
        original_print = print_schema(mutationSchema)
        extended_schema = extend_schema(mutationSchema, ast)
        assert extended_schema != mutationSchema
        assert print_schema(mutationSchema) == original_print
        assert print_schema(extended_schema) == dedent(
            """
            type Mutation {
              mutationField: String
              newMutationField: Int
            }

            type Query {
              queryField: String
              newQueryField: Int
            }

            type Subscription {
              subscriptionField: String
              newSubscriptionField: Int
            }
            """
        )

    def may_extend_directives_with_new_simple_directive():
        extended_schema = extend_test_schema(
            """
            directive @neat on QUERY
            """
        )

        new_directive = extended_schema.get_directive("neat")
        assert new_directive.name == "neat"
        assert DirectiveLocation.QUERY in new_directive.locations

    def sets_correct_description_when_extending_with_a_new_directive():
        extended_schema = extend_test_schema(
            '''
            """
            new directive
            """
            directive @new on QUERY
            '''
        )

        new_directive = extended_schema.get_directive("new")
        assert new_directive.description == "new directive"

    def may_extend_directives_with_new_complex_directive():
        extended_schema = extend_test_schema(
            """
            directive @profile(enable: Boolean! tag: String) repeatable on QUERY | FIELD
            """
        )

        extended_directive = assert_directive(extended_schema.get_directive("profile"))
        assert extended_directive.name == "profile"
        assert extended_directive.locations == [
            DirectiveLocation.QUERY,
            DirectiveLocation.FIELD,
        ]

        args = extended_directive.args
        assert list(args) == ["enable", "tag"]
        assert [str(arg.type) for arg in args.values()] == ["Boolean!", "String"]

    def rejects_invalid_sdl():
        sdl = """
            extend schema @unknown
            """
        with raises(TypeError) as exc_info:
            extend_test_schema(sdl)
        msg = str(exc_info.value)
        assert msg == "Unknown directive 'unknown'."

    def allows_to_disable_sdl_validation():
        sdl = """
            extend schema @unknown
            """
        extend_test_schema(sdl, assume_valid=True)
        extend_test_schema(sdl, assume_valid_sdl=True)

    def does_not_allow_replacing_a_default_directive():
        sdl = """
            directive @include(if: Boolean!) on FIELD | FRAGMENT_SPREAD
            """
        with raises(TypeError) as exc_info:
            extend_test_schema(sdl)
        assert str(exc_info.value).startswith(
            "Directive 'include' already exists in the schema."
            " It cannot be redefined."
        )

    def does_not_allow_replacing_an_existing_enum_value():
        sdl = """
            extend enum SomeEnum {
              ONE
            }
            """
        with raises(TypeError) as exc_info:
            extend_test_schema(sdl)
        assert str(exc_info.value).startswith(
            "Enum value 'SomeEnum.ONE' already exists in the schema."
            " It cannot also be defined in this type extension."
        )

    def describe_can_add_additional_root_operation_types():
        def does_not_automatically_include_common_root_type_names():
            schema = extend_test_schema("type Mutation")
            assert schema.mutation_type is None

        def adds_schema_definition_missing_in_the_original_schema():
            schema = GraphQLSchema(directives=[FooDirective], types=[FooType])
            assert schema.query_type is None

            extension_sdl = dedent(
                """
                schema @foo {
                  query: Foo
                }
                """
            )
            schema = extend_schema(schema, parse(extension_sdl))
            query_type = schema.query_type
            assert query_type.name == "Foo"
            assert print_ast_node(schema) == extension_sdl.rstrip()

        def adds_new_root_types_via_schema_extension():
            schema = extend_test_schema(
                """
                extend schema {
                  mutation: Mutation
                }

                type Mutation
                """
            )
            mutation_type = schema.mutation_type
            assert mutation_type.name == "Mutation"

        def adds_multiple_new_root_types_via_schema_extension():
            schema = extend_test_schema(
                """
                extend schema {
                  mutation: Mutation
                  subscription: Subscription
                }

                type Mutation
                type Subscription
                """
            )
            mutation_type = schema.mutation_type
            subscription_type = schema.subscription_type
            assert mutation_type.name == "Mutation"
            assert subscription_type.name == "Subscription"

        def applies_multiple_schema_extensions():
            schema = extend_test_schema(
                """
                extend schema {
                  mutation: Mutation
                }
                type Mutation

                extend schema {
                  subscription: Subscription
                }
                type Subscription
                """
            )
            mutation_type = schema.mutation_type
            subscription_type = schema.subscription_type
            assert mutation_type.name == "Mutation"
            assert subscription_type.name == "Subscription"

        def schema_extension_ast_are_available_from_schema_object():
            schema = extend_test_schema(
                """
                extend schema {
                  mutation: Mutation
                }
                type Mutation

                extend schema {
                  subscription: Subscription
                }
                type Subscription
                """
            )

            ast = parse(
                """
                extend schema @foo
                """
            )
            schema = extend_schema(schema, ast)

            nodes = schema.extension_ast_nodes or []
            assert "".join(print_ast(node) + "\n" for node in nodes) == dedent(
                """
                extend schema {
                  mutation: Mutation
                }
                extend schema {
                  subscription: Subscription
                }
                extend schema @foo
                """
            )
