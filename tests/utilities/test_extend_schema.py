from pytest import raises

from graphql import graphql_sync
from graphql.error import GraphQLError
from graphql.language import parse, print_ast, DirectiveLocation, DocumentNode
from graphql.pyutils import dedent
from graphql.type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
    is_non_null_type,
    is_scalar_type,
    specified_directives,
    validate_schema,
)
from graphql.utilities import extend_schema, print_schema

# Test schema.

SomeScalarType = GraphQLScalarType(name="SomeScalar", serialize=lambda x: x)

SomeInterfaceType = GraphQLInterfaceType(
    name="SomeInterface",
    fields=lambda: {
        "name": GraphQLField(GraphQLString),
        "some": GraphQLField(SomeInterfaceType),
    },
)

FooType = GraphQLObjectType(
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
    directives=specified_directives + (FooDirective,),
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

        assert (
            extended_schema.get_type("Query").fields["newField"].description
            == "New field description."
        )

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

        foo_type = extended_schema.get_type("Foo")
        foo_field = extended_schema.get_type("Query").fields["foo"]
        assert foo_field.type == foo_type

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
        enum_field = extended_schema.get_type("Query").fields["someEnum"]
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
        union_field = extended_schema.get_type("Query").fields["someUnion"]
        assert union_field.type == some_union_type

    def allows_extension_of_union_by_adding_itself():
        # invalid schema cannot be built with Python
        with raises(TypeError) as exc_info:
            extend_test_schema(
                """
                extend union SomeUnion = SomeUnion
                """
            )
        msg = str(exc_info.value)
        assert msg == "SomeUnion types must be GraphQLObjectType objects."

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
        input_field = extended_schema.get_type("Query").fields["someInput"]
        assert input_field.args["input"].type == some_input_type

        foo_directive = extended_schema.get_directive("foo")
        assert foo_directive.args["input"].type == some_input_type

    def extends_scalars_by_adding_new_directives():
        extended_schema = extend_test_schema(
            """
            extend scalar SomeScalar @foo
            """
        )

        some_scalar = extended_schema.get_type("SomeScalar")
        assert len(some_scalar.extension_ast_nodes) == 1
        assert print_ast(some_scalar.extension_ast_nodes[0]) == (
            "extend scalar SomeScalar @foo"
        )

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

            directive @test(arg: Int) on FIELD | SCALAR
            """
        )
        extended_twice_schema = extend_schema(extended_schema, ast)

        query = extended_twice_schema.get_type("Query")
        some_scalar = extended_twice_schema.get_type("SomeScalar")
        some_enum = extended_twice_schema.get_type("SomeEnum")
        some_union = extended_twice_schema.get_type("SomeUnion")
        some_input = extended_twice_schema.get_type("SomeInput")
        some_interface = extended_twice_schema.get_type("SomeInterface")

        test_input = extended_twice_schema.get_type("TestInput")
        test_enum = extended_twice_schema.get_type("TestEnum")
        test_union = extended_twice_schema.get_type("TestUnion")
        test_interface = extended_twice_schema.get_type("TestInterface")
        test_type = extended_twice_schema.get_type("TestType")
        test_directive = extended_twice_schema.get_directive("test")

        assert len(query.extension_ast_nodes) == 2
        assert len(some_scalar.extension_ast_nodes) == 2
        assert len(some_enum.extension_ast_nodes) == 2
        assert len(some_union.extension_ast_nodes) == 2
        assert len(some_input.extension_ast_nodes) == 2
        assert len(some_interface.extension_ast_nodes) == 2

        assert test_type.extension_ast_nodes is None
        assert test_enum.extension_ast_nodes is None
        assert test_union.extension_ast_nodes is None
        assert test_input.extension_ast_nodes is None
        assert test_interface.extension_ast_nodes is None

        restored_extension_ast = DocumentNode(
            definitions=[
                *query.extension_ast_nodes,
                *some_scalar.extension_ast_nodes,
                *some_enum.extension_ast_nodes,
                *some_union.extension_ast_nodes,
                *some_input.extension_ast_nodes,
                *some_interface.extension_ast_nodes,
                test_input.ast_node,
                test_enum.ast_node,
                test_union.ast_node,
                test_interface.ast_node,
                test_type.ast_node,
                test_directive.ast_node,
            ]
        )

        assert print_schema(
            extend_schema(test_schema, restored_extension_ast)
        ) == print_schema(extended_twice_schema)

        new_field = query.fields["newField"]
        assert print_ast(new_field.ast_node) == "newField(testArg: TestInput): TestEnum"
        assert print_ast(new_field.args["testArg"].ast_node) == "testArg: TestInput"
        assert (
            print_ast(query.fields["oneMoreNewField"].ast_node)
            == "oneMoreNewField: TestUnion"
        )
        assert print_ast(some_enum.values["NEW_VALUE"].ast_node) == "NEW_VALUE"
        assert (
            print_ast(some_enum.values["ONE_MORE_NEW_VALUE"].ast_node)
            == "ONE_MORE_NEW_VALUE"
        )
        assert print_ast(some_input.fields["newField"].ast_node) == "newField: String"
        assert (
            print_ast(some_input.fields["oneMoreNewField"].ast_node)
            == "oneMoreNewField: String"
        )
        assert (
            print_ast(some_interface.fields["newField"].ast_node) == "newField: String"
        )
        assert (
            print_ast(some_interface.fields["oneMoreNewField"].ast_node)
            == "oneMoreNewField: String"
        )

        assert (
            print_ast(test_input.fields["testInputField"].ast_node)
            == "testInputField: TestEnum"
        )
        assert print_ast(test_enum.values["TEST_VALUE"].ast_node) == "TEST_VALUE"
        assert (
            print_ast(test_interface.fields["interfaceField"].ast_node)
            == "interfaceField: String"
        )
        assert (
            print_ast(test_type.fields["interfaceField"].ast_node)
            == "interfaceField: String"
        )
        assert print_ast(test_directive.args["arg"].ast_node) == "arg: Int"

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
        deprecated_field_def = extended_schema.get_type(
            "TypeWithDeprecatedField"
        ).fields["newDeprecatedField"]
        assert deprecated_field_def.is_deprecated is True
        assert deprecated_field_def.deprecation_reason == "not used anymore"

        deprecated_enum_def = extended_schema.get_type(
            "EnumWithDeprecatedValue"
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
        deprecated_field_def = extended_schema.get_type("Foo").fields["deprecatedField"]
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

        deprecated_enum_def = extended_schema.get_type("SomeEnum").values["DEPRECATED"]
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
              newFieldA: Int
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
            directive @profile(enable: Boolean! tag: String) on QUERY | FIELD
            """
        )

        extended_directive = extended_schema.get_directive("profile")
        assert extended_directive.name == "profile"
        assert DirectiveLocation.QUERY in extended_directive.locations
        assert DirectiveLocation.FIELD in extended_directive.locations

        args = extended_directive.args
        assert list(args.keys()) == ["enable", "tag"]
        arg0, arg1 = args.values()
        assert is_non_null_type(arg0.type) is True
        assert is_scalar_type(arg0.type.of_type) is True
        assert is_scalar_type(arg1.type) is True

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
        with raises(GraphQLError) as exc_info:
            extend_test_schema(sdl)
        assert str(exc_info.value).startswith(
            "Directive 'include' already exists in the schema."
            " It cannot be redefined."
        )

    def does_not_allow_replacing_a_custom_directive():
        extended_schema = extend_test_schema(
            """
            directive @meow(if: Boolean!) on FIELD | FRAGMENT_SPREAD
            """
        )

        replacement_ast = parse(
            """
            directive @meow(if: Boolean!) on FIELD | QUERY
            """
        )

        with raises(GraphQLError) as exc_info:
            extend_schema(extended_schema, replacement_ast)
        assert str(exc_info.value).startswith(
            "Directive 'meow' already exists in the schema. It cannot be redefined."
        )

    def does_not_allow_replacing_an_existing_type():
        def existing_type_error(type_):
            return (
                f"Type '{type_}' already exists in the schema."
                " It cannot also be defined in this type definition."
            )

        type_sdl = """
            type Bar
            """
        with raises(GraphQLError) as exc_info:
            assert extend_test_schema(type_sdl)
        assert str(exc_info.value).startswith(existing_type_error("Bar"))

        scalar_sdl = """
            scalar SomeScalar
            """
        with raises(GraphQLError) as exc_info:
            assert extend_test_schema(scalar_sdl)
        assert str(exc_info.value).startswith(existing_type_error("SomeScalar"))

        enum_sdl = """
            enum SomeEnum
            """
        with raises(GraphQLError) as exc_info:
            assert extend_test_schema(enum_sdl)
        assert str(exc_info.value).startswith(existing_type_error("SomeEnum"))

        union_sdl = """
            union SomeUnion
            """
        with raises(GraphQLError) as exc_info:
            assert extend_test_schema(union_sdl)
        assert str(exc_info.value).startswith(existing_type_error("SomeUnion"))

        input_sdl = """
            input SomeInput
            """
        with raises(GraphQLError) as exc_info:
            assert extend_test_schema(input_sdl)
        assert str(exc_info.value).startswith(existing_type_error("SomeInput"))

    def does_not_allow_replacing_an_existing_field():
        def existing_field_error(type_, field):
            return (
                f"Field '{type_}.{field}' already exists in the schema."
                " It cannot also be defined in this type extension."
            )

        type_sdl = """
            extend type Bar {
              foo: Foo
            }
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(type_sdl)
        assert str(exc_info.value).startswith(existing_field_error("Bar", "foo"))

        interface_sdl = """
            extend interface SomeInterface {
              some: Foo
            }
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(interface_sdl)
        assert str(exc_info.value).startswith(
            existing_field_error("SomeInterface", "some")
        )

        input_sdl = """
            extend input SomeInput {
              fooArg: String
            }
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(input_sdl)
        assert str(exc_info.value).startswith(
            existing_field_error("SomeInput", "fooArg")
        )

    def does_not_allow_replacing_an_existing_enum_value():
        sdl = """
            extend enum SomeEnum {
              ONE
            }
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(sdl)
        assert str(exc_info.value).startswith(
            "Enum value 'SomeEnum.ONE' already exists in the schema."
            " It cannot also be defined in this type extension."
        )

    def does_not_allow_referencing_an_unknown_type():
        unknown_type_error = (
            "Unknown type: 'Quix'. Ensure that this type exists either"
            " in the original schema, or is added in a type definition."
        )

        type_sdl = """
            extend type Bar {
              quix: Quix
            }
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(type_sdl)
        assert str(exc_info.value).startswith(unknown_type_error)

        interface_sdl = """
            extend interface SomeInterface {
              quix: Quix
            }
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(interface_sdl)
        assert str(exc_info.value).startswith(unknown_type_error)

        input_sdl = """
            extend input SomeInput {
              quix: Quix
            }
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(input_sdl)
        assert str(exc_info.value).startswith(unknown_type_error)

    def does_not_allow_extending_an_unknown_type():
        for sdl in [
            "extend scalar UnknownType @foo",
            "extend type UnknownType @foo",
            "extend interface UnknownType @foo",
            "extend enum UnknownType @foo",
            "extend union UnknownType @foo",
            "extend input UnknownType @foo",
        ]:
            with raises(GraphQLError) as exc_info:
                extend_test_schema(sdl)
            assert str(exc_info.value).startswith(
                "Cannot extend type 'UnknownType'"
                " because it does not exist in the existing schema."
            )

    def it_does_not_allow_extending_a_mismatch_type():
        type_sdl = """
            extend type SomeInterface @foo
            """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(type_sdl)
        assert str(exc_info.value).startswith(
            "Cannot extend non-object type 'SomeInterface'."
        )

        interface_sdl = """
            extend interface Foo @foo
        """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(interface_sdl)
        assert str(exc_info.value).startswith("Cannot extend non-interface type 'Foo'.")

        enum_sdl = """
            extend enum Foo @foo
        """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(enum_sdl)
        assert str(exc_info.value).startswith("Cannot extend non-enum type 'Foo'.")

        union_sdl = """
            extend union Foo @foo
        """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(union_sdl)
        assert str(exc_info.value).startswith("Cannot extend non-union type 'Foo'.")

        input_sdl = """
            extend input Foo @foo
        """
        with raises(GraphQLError) as exc_info:
            extend_test_schema(input_sdl)
        assert str(exc_info.value).startswith(
            "Cannot extend non-input object type 'Foo'."
        )

    def describe_can_add_additional_root_operation_types():
        def does_not_automatically_include_common_root_type_names():
            schema = extend_test_schema(
                """
                type Mutation {
                  doSomething: String
                }
                """
            )
            assert schema.mutation_type is None

        def adds_schema_definition_missing_in_the_original_schema():
            schema = GraphQLSchema(directives=[FooDirective], types=[FooType])
            assert schema.query_type is None

            ast = parse(
                """
                schema @foo {
                  query: Foo
                }
                """
            )
            schema = extend_schema(schema, ast)
            query_type = schema.query_type
            assert query_type.name == "Foo"

        def adds_new_root_types_via_schema_extension():
            schema = extend_test_schema(
                """
                extend schema {
                  mutation: Mutation
                }

                type Mutation {
                  doSomething: String
                }
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

                type Mutation {
                  doSomething: String
                }

                type Subscription {
                  hearSomething: String
                }
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

                extend schema {
                  subscription: Subscription
                }

                type Mutation {
                  doSomething: String
                }

                type Subscription {
                  hearSomething: String
                }
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

                extend schema {
                  subscription: Subscription
                }

                type Mutation {
                  doSomething: String
                }

                type Subscription {
                  hearSomething: String
                }
                """
            )

            ast = parse(
                """
                extend schema @foo
                """
            )
            schema = extend_schema(schema, ast)

            nodes = schema.extension_ast_nodes
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

        def does_not_allow_redefining_an_existing_root_type():
            sdl = """
                extend schema {
                  query: SomeType
                }

                type SomeType {
                  seeSomething: String
                }
                """
            with raises(TypeError) as exc_info:
                extend_test_schema(sdl)
            assert str(exc_info.value).startswith(
                "Must provide only one query type in schema."
            )

        def does_not_allow_defining_a_root_operation_type_twice():
            sdl = """
                extend schema {
                  mutation: Mutation
                }

                extend schema {
                  mutation: Mutation
                }

                type Mutation {
                  doSomething: String
                }
                """
            with raises(TypeError) as exc_info:
                extend_test_schema(sdl)
            assert str(exc_info.value).startswith(
                "Must provide only one mutation type in schema."
            )

        def does_not_allow_defining_root_operation_type_with_different_types():
            sdl = """
                extend schema {
                  mutation: Mutation
                }

                extend schema {
                  mutation: SomethingElse
                }

                type Mutation {
                  doSomething: String
                }

                type SomethingElse {
                  doSomethingElse: String
                }
                """
            with raises(TypeError) as exc_info:
                extend_test_schema(sdl)
            assert str(exc_info.value).startswith(
                "Must provide only one mutation type in schema."
            )
