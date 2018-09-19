from collections import namedtuple
from typing import cast

from pytest import raises

from graphql import graphql_sync
from graphql.language import parse, print_ast, DocumentNode
from graphql.type import (
    GraphQLDeprecatedDirective,
    GraphQLIncludeDirective,
    GraphQLSkipDirective,
    GraphQLEnumType,
    GraphQLObjectType,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    validate_schema,
)
from graphql.pyutils import dedent
from graphql.utilities import build_ast_schema, build_schema, print_schema


def cycle_output(body: str) -> str:
    """Full cycle test.

    This function does a full cycle of going from a string with the contents of
    the DSL, parsed in a schema AST, materializing that schema AST into an in-
    memory GraphQLSchema, and then finally printing that GraphQL into the DSL.
    """
    ast = parse(body)
    schema = build_ast_schema(ast)
    return print_schema(schema)


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

        data = namedtuple("Data", "str")(123)

        result = graphql_sync(schema, "{ str }", data)
        assert result == ({"str": "123"}, None)

    def can_build_a_schema_directly_from_the_source():
        schema = build_schema(
            """
            type Query {
              add(x: Int, y: Int): Int
            }
            """
        )

        # noinspection PyMethodMayBeStatic
        class Root:
            def add(self, _info, x, y):
                return x + y

        assert graphql_sync(schema, "{ add(x: 34, y: 55) }", Root()) == (
            {"add": 89},
            None,
        )

    def simple_type():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

    def with_directives():
        body = dedent(
            """
            directive @foo(arg: Int) on FIELD

            type Query {
              str: String
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def supports_descriptions():
        body = dedent(
            '''
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
        output = cycle_output(body)
        assert output == body

    def maintains_skip_and_include_directives():
        body = dedent(
            """
            type Query {
                str: String
            }
            """
        )
        schema = build_ast_schema(parse(body))
        assert len(schema.directives) == 3
        assert schema.get_directive("skip") is GraphQLSkipDirective
        assert schema.get_directive("include") is GraphQLIncludeDirective
        assert schema.get_directive("deprecated") is GraphQLDeprecatedDirective

    def overriding_directives_excludes_specified():
        body = dedent(
            """
            directive @skip on FIELD
            directive @include on FIELD
            directive @deprecated on FIELD_DEFINITION

            type Query {
                str: String
            }
            """
        )
        schema = build_ast_schema(parse(body))
        assert len(schema.directives) == 3
        get_directive = schema.get_directive
        assert get_directive("skip") is not GraphQLSkipDirective
        assert get_directive("skip") is not None
        assert get_directive("include") is not GraphQLIncludeDirective
        assert get_directive("include") is not None
        assert get_directive("deprecated") is not GraphQLDeprecatedDirective
        assert get_directive("deprecated") is not None

    def overriding_skip_directive_excludes_built_in_one():
        body = dedent(
            """
            directive @skip on FIELD

            type Query {
                str: String
            }
            """
        )
        schema = build_ast_schema(parse(body))
        assert len(schema.directives) == 3
        assert schema.get_directive("skip") is not GraphQLSkipDirective
        assert schema.get_directive("skip") is not None
        assert schema.get_directive("include") is GraphQLIncludeDirective
        assert schema.get_directive("deprecated") is GraphQLDeprecatedDirective

    def adding_directives_maintains_skip_and_include_directives():
        body = dedent(
            """
            directive @foo(arg: Int) on FIELD

            type Query {
                str: String
            }
            """
        )
        schema = build_ast_schema(parse(body))
        assert len(schema.directives) == 4
        assert schema.get_directive("skip") is GraphQLSkipDirective
        assert schema.get_directive("include") is GraphQLIncludeDirective
        assert schema.get_directive("deprecated") is GraphQLDeprecatedDirective
        assert schema.get_directive("foo") is not None

    def type_modifiers():
        body = dedent(
            """
            type Query {
              nonNullStr: String!
              listOfStrs: [String]
              listOfNonNullStrs: [String!]
              nonNullListOfStrs: [String]!
              nonNullListOfNonNullStrs: [String!]!
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def recursive_type():
        body = dedent(
            """
            type Query {
              str: String
              recurse: Query
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def two_types_circular():
        body = dedent(
            """
            schema {
              query: TypeOne
            }

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
        output = cycle_output(body)
        assert output == body

    def single_argument_field():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

    def simple_type_with_multiple_arguments():
        body = dedent(
            """
            type Query {
              str(int: Int, bool: Boolean): String
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def simple_type_with_interface():
        body = dedent(
            """
            type Query implements WorldInterface {
              str: String
            }

            interface WorldInterface {
              str: String
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def simple_output_enum():
        body = dedent(
            """
            enum Hello {
              WORLD
            }

            type Query {
              hello: Hello
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def simple_input_enum():
        body = dedent(
            """
            enum Hello {
              WORLD
            }

            type Query {
              str(hello: Hello): String
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def multiple_value_enum():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

    def simple_union():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

    def multiple_union():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

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
        msg = str(exc_info.value)
        assert msg == "Hello types must be GraphQLObjectType objects."

    def specifying_union_type_using_typename():
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

        query = """
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

        root = {
            "fruits": [
                {"color": "green", "__typename": "Apple"},
                {"length": 5, "__typename": "Banana"},
            ]
        }

        assert graphql_sync(schema, query, root) == (
            {"fruits": [{"color": "green"}, {"length": 5}]},
            None,
        )

    def specifying_interface_type_using_typename():
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

        query = """
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

        root = {
            "characters": [
                {"name": "Han Solo", "totalCredits": 10, "__typename": "Human"},
                {
                    "name": "R2-D2",
                    "primaryFunction": "Astromech",
                    "__typename": "Droid",
                },
            ]
        }

        assert graphql_sync(schema, query, root) == (
            {
                "characters": [
                    {"name": "Han Solo", "totalCredits": 10},
                    {"name": "R2-D2", "primaryFunction": "Astromech"},
                ]
            },
            None,
        )

    def custom_scalar():
        body = dedent(
            """
            scalar CustomScalar

            type Query {
              customScalar: CustomScalar
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def input_object():
        body = dedent(
            """
            input Input {
              int: Int
            }

            type Query {
              field(in: Input): String
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def simple_argument_field_with_default():
        body = dedent(
            """
            type Query {
              str(int: Int = 2): String
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def custom_scalar_argument_field_with_default():
        body = dedent(
            """
            scalar CustomScalar

            type Query {
              str(int: CustomScalar = 2): String
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def simple_type_with_mutation():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

    def simple_type_with_subscription():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

    def unreferenced_type_implementing_referenced_interface():
        body = dedent(
            """
            type Concrete implements Iface {
              key: String
            }

            interface Iface {
              key: String
            }

            type Query {
              iface: Iface
            }
            """
        )
        output = cycle_output(body)
        assert output == body

    def unreferenced_type_implementing_referenced_union():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

    def supports_deprecated_directive():
        body = dedent(
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
        output = cycle_output(body)
        assert output == body

        ast = parse(body)
        schema = build_ast_schema(ast)

        my_enum = schema.get_type("MyEnum")
        my_enum = cast(GraphQLEnumType, my_enum)

        value = my_enum.values["VALUE"]
        assert value.is_deprecated is False

        old_value = my_enum.values["OLD_VALUE"]
        assert old_value.is_deprecated is True
        assert old_value.deprecation_reason == "No longer supported"

        other_value = my_enum.values["OTHER_VALUE"]
        assert other_value.is_deprecated is True
        assert other_value.deprecation_reason == "Terrible reasons"

        root_fields = schema.get_type("Query").fields
        field1 = root_fields["field1"]
        assert field1.is_deprecated is True
        assert field1.deprecation_reason == "No longer supported"
        field2 = root_fields["field2"]
        assert field2.is_deprecated is True
        assert field2.deprecation_reason == "Because I said so"

    def correctly_assign_ast_nodes():
        schema_ast = parse(
            dedent(
                """
            schema {
              query: Query
            }

            type Query
            {
              testField(testArg: TestInput): TestUnion
            }

            input TestInput
            {
              testInputField: TestEnum
            }

            enum TestEnum
            {
              TEST_VALUE
            }

            union TestUnion = TestType

            interface TestInterface
            {
              interfaceField: String
            }

            type TestType implements TestInterface
            {
              interfaceField: String
            }

            scalar TestScalar

            directive @test(arg: TestScalar) on FIELD
            """
            )
        )
        schema = build_ast_schema(schema_ast)
        query = schema.get_type("Query")
        query = cast(GraphQLObjectType, query)
        test_input = schema.get_type("TestInput")
        test_input = cast(GraphQLInputObjectType, test_input)
        test_enum = schema.get_type("TestEnum")
        test_enum = cast(GraphQLEnumType, test_enum)
        test_union = schema.get_type("TestUnion")
        test_interface = schema.get_type("TestInterface")
        test_interface = cast(GraphQLInterfaceType, test_interface)
        test_type = schema.get_type("TestType")
        test_scalar = schema.get_type("TestScalar")
        test_directive = schema.get_directive("test")

        restored_schema_ast = DocumentNode(
            definitions=[
                schema.ast_node,
                query.ast_node,
                test_input.ast_node,
                test_enum.ast_node,
                test_union.ast_node,
                test_interface.ast_node,
                test_type.ast_node,
                test_scalar.ast_node,
                test_directive.ast_node,
            ]
        )
        assert print_ast(restored_schema_ast) == print_ast(schema_ast)

        test_field = query.fields["testField"]
        assert print_ast(test_field.ast_node) == (
            "testField(testArg: TestInput): TestUnion"
        )
        assert print_ast(test_field.args["testArg"].ast_node) == ("testArg: TestInput")
        assert print_ast(test_input.fields["testInputField"].ast_node) == (
            "testInputField: TestEnum"
        )
        assert print_ast(test_enum.values["TEST_VALUE"].ast_node) == ("TEST_VALUE")
        assert print_ast(test_interface.fields["interfaceField"].ast_node) == (
            "interfaceField: String"
        )
        assert print_ast(test_directive.args["arg"].ast_node) == ("arg: TestScalar")

    def root_operation_type_with_custom_names():
        schema = build_schema(
            dedent(
                """
            schema {
              query: SomeQuery
              mutation: SomeMutation
              subscription: SomeSubscription
            }
            type SomeQuery { str: String }
            type SomeMutation { str: String }
            type SomeSubscription { str: String }
        """
            )
        )

        assert schema.query_type.name == "SomeQuery"
        assert schema.mutation_type.name == "SomeMutation"
        assert schema.subscription_type.name == "SomeSubscription"

    def default_root_operation_type_names():
        schema = build_schema(
            dedent(
                """
            type Query { str: String }
            type Mutation { str: String }
            type Subscription { str: String }
        """
            )
        )

        assert schema.query_type.name == "Query"
        assert schema.mutation_type.name == "Mutation"
        assert schema.subscription_type.name == "Subscription"

    def can_build_invalid_schema():
        schema = build_schema(
            dedent(
                """
            # Invalid schema, because it is missing query root type
            type Mutation {
              str: String
            }
            """
            )
        )
        errors = validate_schema(schema)
        assert errors

    def rejects_invalid_sdl():
        doc = parse(
            """
            type Query {
              foo: String @unknown
            }
            """
        )
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Unknown directive 'unknown'."

    def allows_to_disable_sdl_validation():
        body = """
            type Query {
              foo: String @unknown
            }
            """
        build_schema(body, assume_valid=True)
        build_schema(body, assume_valid_sdl=True)


def describe_failures():
    def allows_only_a_single_query_type():
        body = dedent(
            """
            schema {
              query: Hello
              query: Yellow
            }

            type Hello {
              bar: String
            }

            type Yellow {
              isColor: Boolean
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Must provide only one query type in schema."

    def allows_only_a_single_mutation_type():
        body = dedent(
            """
            schema {
              query: Hello
              mutation: Hello
              mutation: Yellow
            }

            type Hello {
              bar: String
            }

            type Yellow {
              isColor: Boolean
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Must provide only one mutation type in schema."

    def allows_only_a_single_subscription_type():
        body = dedent(
            """
            schema {
              query: Hello
              subscription: Hello
              subscription: Yellow
            }
            type Hello {
              bar: String
            }

            type Yellow {
              isColor: Boolean
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Must provide only one subscription type in schema."

    def unknown_type_referenced():
        body = dedent(
            """
            schema {
              query: Hello
            }

            type Hello {
              bar: Bar
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert "Type 'Bar' not found in document." in msg

    def unknown_type_in_interface_list():
        body = dedent(
            """
            type Query implements Bar {
              field: String
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert "Type 'Bar' not found in document." in msg

    def unknown_type_in_union_list():
        body = dedent(
            """
            union TestUnion = Bar
            type Query { testUnion: TestUnion }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert "Type 'Bar' not found in document." in msg

    def unknown_query_type():
        body = dedent(
            """
            schema {
              query: Wat
            }

            type Hello {
              str: String
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Specified query type 'Wat' not found in document."

    def unknown_mutation_type():
        body = dedent(
            """
            schema {
              query: Hello
              mutation: Wat
            }

            type Hello {
              str: String
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Specified mutation type 'Wat' not found in document."

    def unknown_subscription_type():
        body = dedent(
            """
            schema {
              query: Hello
              mutation: Wat
              subscription: Awesome
            }

            type Hello {
              str: String
            }

            type Wat {
              str: String
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == ("Specified subscription type 'Awesome' not found in document.")

    def does_not_consider_directive_names():
        body = dedent(
            """
            schema {
              query: Foo
            }

            directive @ Foo on QUERY
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Specified query type 'Foo' not found in document."

    def does_not_consider_operation_names():
        body = dedent(
            """
            schema {
              query: Foo
            }

            type Hello {
              str: String
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Specified query type 'Foo' not found in document."

    def does_not_consider_fragment_names():
        body = dedent(
            """
            schema {
              query: Foo
            }

            fragment Foo on Type { field }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Specified query type 'Foo' not found in document."

    def forbids_duplicate_type_definitions():
        body = dedent(
            """
            schema {
              query: Repeated
            }

            type Repeated {
              id: Int
            }

            type Repeated {
              id: String
            }
            """
        )
        doc = parse(body)
        with raises(TypeError) as exc_info:
            build_ast_schema(doc)
        msg = str(exc_info.value)
        assert msg == "Type 'Repeated' was defined more than once."
