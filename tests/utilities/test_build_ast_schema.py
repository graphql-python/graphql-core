from collections import namedtuple
from typing import Union

from pytest import raises

from graphql import graphql_sync
from graphql.language import parse, print_ast, DocumentNode, InterfaceTypeDefinitionNode
from graphql.type import (
    GraphQLDeprecatedDirective,
    GraphQLIncludeDirective,
    GraphQLSchema,
    GraphQLSkipDirective,
    GraphQLSpecifiedByDirective,
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLString,
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLNamedType,
    assert_directive,
    assert_enum_type,
    assert_input_object_type,
    assert_interface_type,
    assert_object_type,
    assert_scalar_type,
    assert_union_type,
    introspection_types,
    validate_schema,
)
from graphql.utilities import build_ast_schema, build_schema, print_schema, print_type

from ..utils import dedent


def cycle_sdl(sdl: str) -> str:
    """Full cycle test.

    This function does a full cycle of going from a string with the contents of the SDL,
    parsed in a schema AST, materializing that schema AST into an in-memory
    GraphQLSchema, and then finally printing that GraphQL into the SDÖ.
    """
    ast = parse(sdl)
    schema = build_ast_schema(ast)
    return print_schema(schema)


TypeWithAstNode = Union[
    GraphQLArgument, GraphQLEnumValue, GraphQLField, GraphQLInputField, GraphQLNamedType
]

TypeWithExtensionAstNodes = GraphQLNamedType


def expect_ast_node(obj: TypeWithAstNode, expected: str) -> None:
    assert obj is not None and obj.ast_node is not None
    assert print_ast(obj.ast_node) == expected


def expect_extension_ast_nodes(obj: TypeWithExtensionAstNodes, expected: str) -> None:
    assert obj is not None and obj.extension_ast_nodes is not None
    assert "\n\n".join(print_ast(node) for node in obj.extension_ast_nodes) == expected


def describe_schema_builder():
    def can_use_built_schema_for_limited_execution():
        schema = build_ast_schema(
            parse(
                """
                type Query {
                  str: String
                }
                """
            )
        )

        root_value = namedtuple("Data", "str")(123)  # type: ignore

        result = graphql_sync(schema=schema, source="{ str }", root_value=root_value)
        assert result == ({"str": "123"}, None)

    def can_build_a_schema_directly_from_the_source():
        schema = build_schema(
            """
            type Query {
              add(x: Int, y: Int): Int
            }
            """
        )
        source = "{ add(x: 34, y: 55) }"

        # noinspection PyMethodMayBeStatic
        class RootValue:
            def add(self, _info, x, y):
                return x + y

        assert graphql_sync(schema=schema, source=source, root_value=RootValue()) == (
            {"add": 89},
            None,
        )

    def ignores_non_type_system_definitions():
        sdl = """
            type Query {
              str: String
            }

            fragment SomeFragment on Query {
              str
            }
            """
        build_schema(sdl)

    def match_order_of_default_types_and_directives():
        schema = GraphQLSchema()
        sdl_schema = build_ast_schema(DocumentNode(definitions=[]))

        assert sdl_schema.directives == schema.directives
        assert sdl_schema.type_map == schema.type_map

    def empty_type():
        sdl = dedent(
            """
            type EmptyType
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_type():
        sdl = dedent(
            """
            type Query {
              str: String
              int: Int
              float: Float
              id: ID
              bool: Boolean
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

        schema = build_schema(sdl)
        # Built-ins are used
        assert schema.get_type("Int") is GraphQLInt
        assert schema.get_type("Float") is GraphQLFloat
        assert schema.get_type("String") is GraphQLString
        assert schema.get_type("Boolean") is GraphQLBoolean
        assert schema.get_type("ID") is GraphQLID

    def include_standard_type_only_if_it_is_used():
        schema = build_schema("type Query")

        # Only String and Boolean are used by introspection types
        assert schema.get_type("Int") is None
        assert schema.get_type("Float") is None
        assert schema.get_type("String") is GraphQLString
        assert schema.get_type("Boolean") is GraphQLBoolean
        assert schema.get_type("ID") is None

    def with_directives():
        sdl = dedent(
            """
            directive @foo(arg: Int) on FIELD

            directive @repeatableFoo(arg: Int) repeatable on FIELD
            """
        )
        assert cycle_sdl(sdl) == sdl

    def supports_descriptions():
        sdl = dedent(
            '''
            """Do you agree that this is the most creative schema ever?"""
            schema {
              query: Query
            }

            """This is a directive"""
            directive @foo(
              """It has an argument"""
              arg: Int
            ) on FIELD

            """Who knows what's inside this scalar?"""
            scalar MysteryScalar

            """This is an input object type"""
            input FooInput {
              """It has a field"""
              field: Int
            }

            """This is an interface type"""
            interface Energy {
              """It also has a field"""
              str: String
            }

            """There is nothing inside!"""
            union BlackHole

            """With an enum"""
            enum Color {
              RED

              """Not a creative color"""
              GREEN
              BLUE
            }

            """What a great type"""
            type Query {
              """And a field to boot"""
              str: String
            }
            '''
        )
        assert cycle_sdl(sdl) == sdl

    def maintains_include_skip_and_specified_by_url_directives():
        schema = build_schema("type Query")

        assert len(schema.directives) == 4
        assert schema.get_directive("skip") is GraphQLSkipDirective
        assert schema.get_directive("include") is GraphQLIncludeDirective
        assert schema.get_directive("deprecated") is GraphQLDeprecatedDirective
        assert schema.get_directive("specifiedBy") is GraphQLSpecifiedByDirective

    def overriding_directives_excludes_specified():
        schema = build_schema(
            """
            directive @skip on FIELD
            directive @include on FIELD
            directive @deprecated on FIELD_DEFINITION
            directive @specifiedBy on FIELD_DEFINITION
            """
        )

        assert len(schema.directives) == 4
        get_directive = schema.get_directive
        assert get_directive("skip") is not GraphQLSkipDirective
        assert get_directive("skip") is not None
        assert get_directive("include") is not GraphQLIncludeDirective
        assert get_directive("include") is not None
        assert get_directive("deprecated") is not GraphQLDeprecatedDirective
        assert get_directive("deprecated") is not None
        assert get_directive("specifiedBy") is not GraphQLSpecifiedByDirective
        assert get_directive("specifiedBy") is not None

    def adding_directives_maintains_include_skip_and_specified_by_directives():
        schema = build_schema(
            """
            directive @foo(arg: Int) on FIELD
            """
        )

        assert len(schema.directives) == 5
        assert schema.get_directive("skip") is GraphQLSkipDirective
        assert schema.get_directive("include") is GraphQLIncludeDirective
        assert schema.get_directive("deprecated") is GraphQLDeprecatedDirective
        assert schema.get_directive("specifiedBy") is GraphQLSpecifiedByDirective
        assert schema.get_directive("foo") is not None

    def type_modifiers():
        sdl = dedent(
            """
            type Query {
              nonNullStr: String!
              listOfStrings: [String]
              listOfNonNullStrings: [String!]
              nonNullListOfStrings: [String]!
              nonNullListOfNonNullStrings: [String!]!
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def recursive_type():
        sdl = dedent(
            """
            type Query {
              str: String
              recurse: Query
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def two_types_circular():
        sdl = dedent(
            """
            type TypeOne {
              str: String
              typeTwo: TypeTwo
            }

            type TypeTwo {
              str: String
              typeOne: TypeOne
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def single_argument_field():
        sdl = dedent(
            """
            type Query {
              str(int: Int): String
              floatToStr(float: Float): String
              idToStr(id: ID): String
              booleanToStr(bool: Boolean): String
              strToStr(bool: String): String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_type_with_multiple_arguments():
        sdl = dedent(
            """
            type Query {
              str(int: Int, bool: Boolean): String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def empty_interface():
        sdl = dedent(
            """
            interface EmptyInterface
            """
        )

        definition = parse(sdl).definitions[0]
        assert isinstance(definition, InterfaceTypeDefinitionNode)
        assert definition.interfaces == []

        assert cycle_sdl(sdl) == sdl

    def simple_type_with_interface():
        sdl = dedent(
            """
            type Query implements WorldInterface {
              str: String
            }

            interface WorldInterface {
              str: String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_interface_hierarchy():
        sdl = dedent(
            """
            schema {
              query: Child
            }

            interface Child implements Parent {
              str: String
            }

            type Hello implements Parent & Child {
              str: String
            }

            interface Parent {
              str: String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def empty_enum():
        sdl = dedent(
            """
            enum EmptyEnum
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_output_enum():
        sdl = dedent(
            """
            enum Hello {
              WORLD
            }

            type Query {
              hello: Hello
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_input_enum():
        sdl = dedent(
            """
            enum Hello {
              WORLD
            }

            type Query {
              str(hello: Hello): String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def multiple_value_enum():
        sdl = dedent(
            """
            enum Hello {
              WO
              RLD
            }

            type Query {
              hello: Hello
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

        # check that the internal values are the same as the names
        schema = build_schema(sdl)
        enum_type = schema.get_type("Hello")
        assert isinstance(enum_type, GraphQLEnumType)
        assert [value.value for value in enum_type.values.values()] == ["WO", "RLD"]

    def empty_union():
        sdl = dedent(
            """
            union EmptyUnion
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_union():
        sdl = dedent(
            """
            union Hello = World

            type Query {
              hello: Hello
            }

            type World {
              str: String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def multiple_union():
        sdl = dedent(
            """
            union Hello = WorldOne | WorldTwo

            type Query {
              hello: Hello
            }

            type WorldOne {
              str: String
            }

            type WorldTwo {
              str: String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def can_build_recursive_union():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            build_schema(
                """
                union Hello = Hello

                type Query {
                  hello: Hello
                }
                """
            )
        assert (
            str(exc_info.value) == "Hello types must be specified"
            " as a collection of GraphQLObjectType instances."
        )

    def custom_scalar():
        sdl = dedent(
            """
            scalar CustomScalar

            type Query {
              customScalar: CustomScalar
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def empty_input_object():
        sdl = dedent(
            """
            input EmptyInputObject
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_input_object():
        sdl = dedent(
            """
            input Input {
              int: Int
            }

            type Query {
              field(in: Input): String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_argument_field_with_default():
        sdl = dedent(
            """
            type Query {
              str(int: Int = 2): String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def custom_scalar_argument_field_with_default():
        sdl = dedent(
            """
            scalar CustomScalar

            type Query {
              str(int: CustomScalar = 2): String
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_type_with_mutation():
        sdl = dedent(
            """
            schema {
              query: HelloScalars
              mutation: Mutation
            }

            type HelloScalars {
              str: String
              int: Int
              bool: Boolean
            }

            type Mutation {
              addHelloScalars(str: String, int: Int, bool: Boolean): HelloScalars
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def simple_type_with_subscription():
        sdl = dedent(
            """
            schema {
              query: HelloScalars
              subscription: Subscription
            }

            type HelloScalars {
              str: String
              int: Int
              bool: Boolean
            }

            type Subscription {
              subscribeHelloScalars(str: String, int: Int, bool: Boolean): HelloScalars
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def unreferenced_type_implementing_referenced_interface():
        sdl = dedent(
            """
            type Concrete implements Interface {
              key: String
            }

            interface Interface {
              key: String
            }

            type Query {
              interface: Interface
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def unreferenced_interface_implementing_referenced_interface():
        sdl = dedent(
            """
            interface Child implements Parent {
              key: String
            }

            interface Parent {
              key: String
            }

            type Query {
              interfaceField: Parent
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

    def unreferenced_type_implementing_referenced_union():
        sdl = dedent(
            """
            type Concrete {
              key: String
            }

            type Query {
              union: Union
            }

            union Union = Concrete
            """
        )
        assert cycle_sdl(sdl) == sdl

    def supports_deprecated_directive():
        sdl = dedent(
            """
            enum MyEnum {
              VALUE
              OLD_VALUE @deprecated
              OTHER_VALUE @deprecated(reason: "Terrible reasons")
            }

            input MyInput {
              oldInput: String @deprecated
              otherInput: String @deprecated(reason: "Use newInput")
              newInput: String
            }

            type Query {
              field1: String @deprecated
              field2: Int @deprecated(reason: "Because I said so")
              enum: MyEnum
              field3(oldArg: String @deprecated, arg: String): String
              field4(oldArg: String @deprecated(reason: "Why not?"), arg: String): String
              field5(arg: MyInput): String
            }
            """  # noqa: E501
        )
        assert cycle_sdl(sdl) == sdl

        schema = build_schema(sdl)

        my_enum = assert_enum_type(schema.get_type("MyEnum"))

        value = my_enum.values["VALUE"]
        assert value.deprecation_reason is None

        old_value = my_enum.values["OLD_VALUE"]
        assert old_value.deprecation_reason == "No longer supported"

        other_value = my_enum.values["OTHER_VALUE"]
        assert other_value.deprecation_reason == "Terrible reasons"

        root_fields = assert_object_type(schema.get_type("Query")).fields
        field1 = root_fields["field1"]
        assert field1.deprecation_reason == "No longer supported"
        field2 = root_fields["field2"]
        assert field2.deprecation_reason == "Because I said so"

        input_fields = assert_input_object_type(schema.get_type("MyInput")).fields

        new_input = input_fields["newInput"]
        assert new_input.deprecation_reason is None

        old_input = input_fields["oldInput"]
        assert old_input.deprecation_reason == "No longer supported"

        other_input = input_fields["otherInput"]
        assert other_input.deprecation_reason == "Use newInput"

        field3_old_arg = root_fields["field3"].args["oldArg"]
        assert field3_old_arg.deprecation_reason == "No longer supported"

        field4_old_arg = root_fields["field4"].args["oldArg"]
        assert field4_old_arg.deprecation_reason == "Why not?"

    def supports_specified_by_directives():
        sdl = dedent(
            """
            scalar Foo @specifiedBy(url: "https://example.com/foo_spec")

            type Query {
              foo: Foo @deprecated
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

        schema = build_schema(sdl)

        foo_scalar = assert_scalar_type(schema.get_type("Foo"))
        assert foo_scalar.specified_by_url == "https://example.com/foo_spec"

    def correctly_extend_scalar_type():
        schema = build_schema(
            """
            scalar SomeScalar
            extend scalar SomeScalar @foo
            extend scalar SomeScalar @bar

            directive @foo on SCALAR
            directive @bar on SCALAR
            """
        )

        some_scalar = assert_scalar_type(schema.get_type("SomeScalar"))
        assert print_type(some_scalar) == dedent(
            """
            scalar SomeScalar
            """
        )

        expect_ast_node(some_scalar, "scalar SomeScalar")
        expect_extension_ast_nodes(
            some_scalar,
            dedent(
                """
            extend scalar SomeScalar @foo

            extend scalar SomeScalar @bar
            """
            ),
        )

    def correctly_extend_object_type():
        schema = build_schema(
            """
            type SomeObject implements Foo {
              first: String
            }

            extend type SomeObject implements Bar {
              second: Int
            }

            extend type SomeObject implements Baz {
              third: Float
            }

            interface Foo
            interface Bar
            interface Baz
            """
        )

        some_object = assert_object_type(schema.get_type("SomeObject"))
        assert print_type(some_object) == dedent(
            """
            type SomeObject implements Foo & Bar & Baz {
              first: String
              second: Int
              third: Float
            }
            """
        )

        expect_ast_node(
            some_object,
            dedent(
                """
            type SomeObject implements Foo {
              first: String
            }
            """
            ),
        )
        expect_extension_ast_nodes(
            some_object,
            dedent(
                """
            extend type SomeObject implements Bar {
              second: Int
            }

            extend type SomeObject implements Baz {
              third: Float
            }
            """
            ),
        )

    def correctly_extend_interface_type():
        schema = build_schema(
            """
            interface SomeInterface {
              first: String
            }

            extend interface SomeInterface {
              second: Int
            }

            extend interface SomeInterface {
              third: Float
            }
            """
        )

        some_interface = assert_interface_type(schema.get_type("SomeInterface"))
        assert print_type(some_interface) == dedent(
            """
            interface SomeInterface {
              first: String
              second: Int
              third: Float
            }
            """
        )

        expect_ast_node(
            some_interface,
            dedent(
                """
            interface SomeInterface {
              first: String
            }
            """
            ),
        )
        expect_extension_ast_nodes(
            some_interface,
            dedent(
                """
            extend interface SomeInterface {
              second: Int
            }

            extend interface SomeInterface {
              third: Float
            }
            """
            ),
        )

    def correctly_extend_union_type():
        schema = build_schema(
            """
            union SomeUnion = FirstType
            extend union SomeUnion = SecondType
            extend union SomeUnion = ThirdType

            type FirstType
            type SecondType
            type ThirdType
            """
        )

        some_union = assert_union_type(schema.get_type("SomeUnion"))
        assert print_type(some_union) == dedent(
            """
            union SomeUnion = FirstType | SecondType | ThirdType
            """
        )

        expect_ast_node(some_union, "union SomeUnion = FirstType")
        expect_extension_ast_nodes(
            some_union,
            dedent(
                """
            extend union SomeUnion = SecondType

            extend union SomeUnion = ThirdType
            """
            ),
        )

    def correctly_extend_enum_type():
        schema = build_schema(
            """
            enum SomeEnum {
              FIRST
            }

            extend enum SomeEnum {
              SECOND
            }

            extend enum SomeEnum {
              THIRD
            }
            """
        )

        some_enum = assert_enum_type(schema.get_type("SomeEnum"))
        assert print_type(some_enum) == dedent(
            """
            enum SomeEnum {
              FIRST
              SECOND
              THIRD
            }
            """
        )

        expect_ast_node(
            some_enum,
            dedent(
                """
            enum SomeEnum {
              FIRST
            }
            """
            ),
        )
        expect_extension_ast_nodes(
            some_enum,
            dedent(
                """
            extend enum SomeEnum {
              SECOND
            }

            extend enum SomeEnum {
              THIRD
            }
            """
            ),
        )

    def correctly_extend_input_object_type():
        schema = build_schema(
            """
            input SomeInput {
              first: String
            }

            extend input SomeInput {
              second: Int
            }

            extend input SomeInput {
              third: Float
            }
            """
        )

        some_input = assert_input_object_type(schema.get_type("SomeInput"))
        assert print_type(some_input) == dedent(
            """
            input SomeInput {
              first: String
              second: Int
              third: Float
            }
            """
        )

        expect_ast_node(
            some_input,
            dedent(
                """
            input SomeInput {
              first: String
            }
            """
            ),
        )
        expect_extension_ast_nodes(
            some_input,
            dedent(
                """
            extend input SomeInput {
              second: Int
            }

            extend input SomeInput {
              third: Float
            }
            """
            ),
        )

    def correctly_assign_ast_nodes():
        sdl = dedent(
            """
            schema {
              query: Query
            }

            type Query {
              testField(testArg: TestInput): TestUnion
            }

            input TestInput {
              testInputField: TestEnum
            }

            enum TestEnum {
              TEST_VALUE
            }

            union TestUnion = TestType

            interface TestInterface {
              interfaceField: String
            }

            type TestType implements TestInterface {
              interfaceField: String
            }

            scalar TestScalar

            directive @test(arg: TestScalar) on FIELD
            """
        )
        ast = parse(sdl, no_location=True)

        schema = build_ast_schema(ast)
        query = assert_object_type(schema.get_type("Query"))
        test_input = assert_input_object_type(schema.get_type("TestInput"))
        test_enum = assert_enum_type(schema.get_type("TestEnum"))
        test_union = assert_union_type(schema.get_type("TestUnion"))
        test_interface = assert_interface_type(schema.get_type("TestInterface"))
        test_type = assert_object_type(schema.get_type("TestType"))
        test_scalar = assert_scalar_type(schema.get_type("TestScalar"))
        test_directive = assert_directive(schema.get_directive("test"))

        assert [
            schema.ast_node,
            query.ast_node,
            test_input.ast_node,
            test_enum.ast_node,
            test_union.ast_node,
            test_interface.ast_node,
            test_type.ast_node,
            test_scalar.ast_node,
            test_directive.ast_node,
        ] == ast.definitions

        test_field = query.fields["testField"]
        expect_ast_node(test_field, "testField(testArg: TestInput): TestUnion")
        expect_ast_node(test_field.args["testArg"], "testArg: TestInput")
        expect_ast_node(test_input.fields["testInputField"], "testInputField: TestEnum")
        test_enum_value = test_enum.values["TEST_VALUE"]
        expect_ast_node(test_enum_value, "TEST_VALUE")
        expect_ast_node(
            test_interface.fields["interfaceField"], "interfaceField: String"
        )
        expect_ast_node(test_directive.args["arg"], "arg: TestScalar")

    def root_operation_types_with_custom_names():
        schema = build_schema(
            """
            schema {
              query: SomeQuery
              mutation: SomeMutation
              subscription: SomeSubscription
            }
            type SomeQuery
            type SomeMutation
            type SomeSubscription
            """
        )

        assert schema.query_type
        assert schema.query_type.name == "SomeQuery"
        assert schema.mutation_type
        assert schema.mutation_type.name == "SomeMutation"
        assert schema.subscription_type
        assert schema.subscription_type.name == "SomeSubscription"

    def default_root_operation_type_names():
        schema = build_schema(
            """
            type Query
            type Mutation
            type Subscription
            """
        )

        assert schema.query_type
        assert schema.query_type.name == "Query"
        assert schema.mutation_type
        assert schema.mutation_type.name == "Mutation"
        assert schema.subscription_type
        assert schema.subscription_type.name == "Subscription"

    def can_build_invalid_schema():
        # Invalid schema, because it is missing query root type
        schema = build_schema("type Mutation")
        errors = validate_schema(schema)
        assert errors

    def do_not_override_standard_types():
        # Note: not sure it's desired behaviour to just silently ignore override
        # attempts so just documenting it here.

        schema = build_schema(
            """
            scalar ID

            scalar __Schema
            """
        )

        assert schema.get_type("ID") is GraphQLID
        assert schema.get_type("__Schema") is introspection_types["__Schema"]

    def allows_to_reference_introspection_types():
        schema = build_schema(
            """
            type Query {
              introspectionField: __EnumValue
            }
            """
        )

        query_type = assert_object_type(schema.get_type("Query"))
        __EnumValue = introspection_types["__EnumValue"]
        assert query_type.fields["introspectionField"].type is __EnumValue
        assert schema.get_type("__EnumValue") is introspection_types["__EnumValue"]

    def rejects_invalid_sdl():
        sdl = """
            type Query {
              foo: String @unknown
            }
            """
        with raises(TypeError) as exc_info:
            build_schema(sdl)
        assert str(exc_info.value) == "Unknown directive '@unknown'."

    def allows_to_disable_sdl_validation():
        sdl = """
            type Query {
              foo: String @unknown
            }
            """
        build_schema(sdl, assume_valid=True)
        build_schema(sdl, assume_valid_sdl=True)

    def throws_on_unknown_types():
        sdl = """
            type Query {
              unknown: UnknownType
            }
            """
        with raises(TypeError) as exc_info:
            build_schema(sdl, assume_valid_sdl=True)
        assert str(exc_info.value).endswith("Unknown type: 'UnknownType'.")

    def rejects_invalid_ast():
        with raises(TypeError) as exc_info:
            build_ast_schema(None)  # type: ignore
        assert str(exc_info.value) == "Must provide valid Document AST."
        with raises(TypeError) as exc_info:
            build_ast_schema({})  # type: ignore
        assert str(exc_info.value) == "Must provide valid Document AST."
