from collections import namedtuple
from typing import Union

from pytest import raises  # type: ignore

from graphql import graphql_sync
from graphql.language import parse, print_ast, DocumentNode, InterfaceTypeDefinitionNode
from graphql.type import (
    GraphQLDeprecatedDirective,
    GraphQLIncludeDirective,
    GraphQLSkipDirective,
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLString,
    GraphQLArgument,
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
    validate_schema,
)
from graphql.pyutils import dedent
from graphql.utilities import build_ast_schema, build_schema, print_schema, print_type


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


def print_ast_node(obj: TypeWithAstNode) -> str:
    assert obj is not None and obj.ast_node is not None
    return print_ast(obj.ast_node)


def print_all_ast_nodes(obj: TypeWithExtensionAstNodes) -> str:
    assert obj is not None and obj.extension_ast_nodes is not None
    return print_ast(DocumentNode(definitions=[obj.ast_node, *obj.extension_ast_nodes]))


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

    def maintains_skip_and_include_directives():
        schema = build_schema("type Query")

        assert len(schema.directives) == 3
        assert schema.get_directive("skip") is GraphQLSkipDirective
        assert schema.get_directive("include") is GraphQLIncludeDirective
        assert schema.get_directive("deprecated") is GraphQLDeprecatedDirective

    def overriding_directives_excludes_specified():
        schema = build_schema(
            """
            directive @skip on FIELD
            directive @include on FIELD
            directive @deprecated on FIELD_DEFINITION
            """
        )

        assert len(schema.directives) == 3
        get_directive = schema.get_directive
        assert get_directive("skip") is not GraphQLSkipDirective
        assert get_directive("skip") is not None
        assert get_directive("include") is not GraphQLIncludeDirective
        assert get_directive("include") is not None
        assert get_directive("deprecated") is not GraphQLDeprecatedDirective
        assert get_directive("deprecated") is not None

    def adding_directives_maintains_skip_and_include_directives():
        schema = build_schema(
            """
            directive @foo(arg: Int) on FIELD
            """
        )

        assert len(schema.directives) == 4
        assert schema.get_directive("skip") is GraphQLSkipDirective
        assert schema.get_directive("include") is GraphQLIncludeDirective
        assert schema.get_directive("deprecated") is GraphQLDeprecatedDirective
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

    def describe_specifying_union_type_using_typename():

        schema = build_schema(
            """
            type Query {
              fruits: [Fruit]
            }

            union Fruit = Apple | Banana

            type Apple {
              color: String
            }

            type Banana {
              length: Int
            }
            """
        )

        source = """
            {
              fruits {
                ... on Apple {
                  color
                }
                ... on Banana {
                  length
                }
              }
            }
            """

        expected = ({"fruits": [{"color": "green"}, {"length": 5}]}, None)

        def using_dicts():
            root_value = {
                "fruits": [
                    {"color": "green", "__typename": "Apple"},
                    {"length": 5, "__typename": "Banana"},
                ]
            }

            assert (
                graphql_sync(schema=schema, source=source, root_value=root_value)
                == expected
            )

        def using_objects():
            class Apple:
                __typename = "Apple"
                color = "green"

            class Banana:
                __typename = "Banana"
                length = 5

            class RootValue:
                fruits = [Apple(), Banana()]

            assert (
                graphql_sync(schema=schema, source=source, root_value=RootValue())
                == expected
            )

        def using_inheritance():
            class Fruit:
                __typename = "Fruit"

            class Apple(Fruit):
                __typename = "Apple"

            class Delicious(Apple):
                color = "golden or red"

            class GoldenDelicious(Delicious):
                color = "golden"

            class RedDelicious(Delicious):
                color = "red"

            class GrannySmith(Apple):
                color = "green"

            class Banana(Fruit):
                __typename = "Banana"
                length = 5

            class RootValue:
                fruits = [GrannySmith(), RedDelicious(), GoldenDelicious(), Banana()]

            assert graphql_sync(
                schema=schema, source=source, root_value=RootValue()
            ) == (
                {
                    "fruits": [
                        {"color": "green"},
                        {"color": "red"},
                        {"color": "golden"},
                        {"length": 5},
                    ]
                },
                None,
            )

    def describe_specifying_interface_type_using_typename():
        schema = build_schema(
            """
            type Query {
              characters: [Character]
            }

            interface Character {
              name: String!
            }

            type Human implements Character {
              name: String!
              totalCredits: Int
            }

            type Droid implements Character {
              name: String!
              primaryFunction: String
            }
            """
        )

        source = """
            {
              characters {
                name
                ... on Human {
                  totalCredits
                }
                ... on Droid {
                  primaryFunction
                }
              }
            }
            """

        expected = (
            {
                "characters": [
                    {"name": "Han Solo", "totalCredits": 10},
                    {"name": "R2-D2", "primaryFunction": "Astromech"},
                ]
            },
            None,
        )

        def using_dicts():
            root_value = {
                "characters": [
                    {"name": "Han Solo", "totalCredits": 10, "__typename": "Human"},
                    {
                        "name": "R2-D2",
                        "primaryFunction": "Astromech",
                        "__typename": "Droid",
                    },
                ]
            }

            assert (
                graphql_sync(schema=schema, source=source, root_value=root_value)
                == expected
            )

        def using_objects():
            class Human:
                __typename = "Human"
                name = "Han Solo"
                totalCredits = 10

            class Droid:
                __typename = "Droid"
                name = "R2-D2"
                primaryFunction = "Astromech"

            class RootValue:
                characters = [Human(), Droid()]

            assert (
                graphql_sync(schema=schema, source=source, root_value=RootValue())
                == expected
            )

        def using_inheritance():
            class Character:
                __typename = "Character"

            class Human(Character):
                __typename = "Human"

            class HanSolo(Human):
                name = "Han Solo"
                totalCredits = 10

            class Droid(Character):
                __typename = "Droid"

            class RemoteControlled:
                name = "R2"

            class Mobile:
                name = "D2"

            class R2D2(RemoteControlled, Droid, Mobile):
                name = "R2-D2"
                primaryFunction = "Astromech"

            class RootValue:
                characters = [HanSolo(), R2D2()]

            assert (
                graphql_sync(schema=schema, source=source, root_value=RootValue())
                == expected
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

            type Query {
              field1: String @deprecated
              field2: Int @deprecated(reason: "Because I said so")
              enum: MyEnum
            }
            """
        )
        assert cycle_sdl(sdl) == sdl

        schema = build_schema(sdl)

        my_enum = assert_enum_type(schema.get_type("MyEnum"))

        value = my_enum.values["VALUE"]
        assert value.is_deprecated is False

        old_value = my_enum.values["OLD_VALUE"]
        assert old_value.is_deprecated is True
        assert old_value.deprecation_reason == "No longer supported"

        other_value = my_enum.values["OTHER_VALUE"]
        assert other_value.is_deprecated is True
        assert other_value.deprecation_reason == "Terrible reasons"

        root_fields = assert_object_type(schema.get_type("Query")).fields
        field1 = root_fields["field1"]
        assert field1.is_deprecated is True
        assert field1.deprecation_reason == "No longer supported"
        field2 = root_fields["field2"]
        assert field2.is_deprecated is True
        assert field2.deprecation_reason == "Because I said so"

    def correctly_extend_scalar_type():
        scalar_sdl = dedent(
            """
            scalar SomeScalar

            extend scalar SomeScalar @foo

            extend scalar SomeScalar @bar
            """
        )
        schema = build_schema(
            scalar_sdl
            + dedent(
                """
                directive @foo on SCALAR
                directive @bar on SCALAR
                """
            )
        )

        some_scalar = assert_scalar_type(schema.get_type("SomeScalar"))
        assert print_type(some_scalar) + "\n" == dedent(
            """
            scalar SomeScalar
            """
        )

        assert print_all_ast_nodes(some_scalar) == scalar_sdl

    def correctly_extend_object_type():
        object_sdl = dedent(
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
            """
        )
        schema = build_schema(
            object_sdl
            + dedent(
                """
                interface Foo
                interface Bar
                interface Baz
                """
            )
        )

        some_object = assert_object_type(schema.get_type("SomeObject"))
        assert print_type(some_object) + "\n" == dedent(
            """
            type SomeObject implements Foo & Bar & Baz {
              first: String
              second: Int
              third: Float
            }
            """
        )

        assert print_all_ast_nodes(some_object) == object_sdl

    def correctly_extend_interface_type():
        interface_sdl = dedent(
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
        schema = build_schema(interface_sdl)

        some_interface = assert_interface_type(schema.get_type("SomeInterface"))
        assert print_type(some_interface) + "\n" == dedent(
            """
            interface SomeInterface {
              first: String
              second: Int
              third: Float
            }
            """
        )

        assert print_all_ast_nodes(some_interface) == interface_sdl

    def correctly_extend_union_type():
        union_sdl = dedent(
            """
            union SomeUnion = FirstType

            extend union SomeUnion = SecondType

            extend union SomeUnion = ThirdType
            """
        )
        schema = build_schema(
            union_sdl
            + dedent(
                """
                type FirstType
                type SecondType
                type ThirdType
                """
            )
        )

        some_union = assert_union_type(schema.get_type("SomeUnion"))
        assert print_type(some_union) + "\n" == dedent(
            """
            union SomeUnion = FirstType | SecondType | ThirdType
            """
        )

        assert print_all_ast_nodes(some_union) == union_sdl

    def correctly_extend_enum_type():
        enum_sdl = dedent(
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
        schema = build_schema(enum_sdl)

        some_enum = assert_enum_type(schema.get_type("SomeEnum"))
        assert print_type(some_enum) + "\n" == dedent(
            """
            enum SomeEnum {
              FIRST
              SECOND
              THIRD
            }
            """
        )

        assert print_all_ast_nodes(some_enum) == enum_sdl

    def correctly_extend_input_object_type():
        input_sdl = dedent(
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
        schema = build_schema(input_sdl)

        some_input = assert_input_object_type(schema.get_type("SomeInput"))
        assert print_type(some_input) + "\n" == dedent(
            """
            input SomeInput {
              first: String
              second: Int
              third: Float
            }
            """
        )

        assert print_all_ast_nodes(some_input) == input_sdl

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
        assert print_ast_node(test_field) == (
            "testField(testArg: TestInput): TestUnion"
        )
        assert print_ast_node(test_field.args["testArg"]) == "testArg: TestInput"
        assert print_ast_node(test_input.fields["testInputField"]) == (
            "testInputField: TestEnum"
        )
        test_enum_value = test_enum.values["TEST_VALUE"]
        assert test_enum_value
        assert print_ast_node(test_enum_value) == "TEST_VALUE"
        assert print_ast_node(test_interface.fields["interfaceField"]) == (
            "interfaceField: String"
        )
        assert print_ast_node(test_directive.args["arg"]) == "arg: TestScalar"

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
