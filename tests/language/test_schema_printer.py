from copy import deepcopy

from pytest import raises  # type: ignore

from graphql.language import ScalarTypeDefinitionNode, NameNode, print_ast, parse
from graphql.pyutils import dedent

# noinspection PyUnresolvedReferences
from ..fixtures import kitchen_sink_sdl  # noqa: F401


def describe_printer_sdl_document():
    def prints_minimal_ast():
        node = ScalarTypeDefinitionNode(name=NameNode(value="foo"))
        assert print_ast(node) == "scalar foo"

    def produces_helpful_error_messages():
        bad_ast = {"random": "Data"}
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            print_ast(bad_ast)
        msg = str(exc_info.value)
        assert msg == "Not an AST Node: {'random': 'Data'}"

    # noinspection PyShadowingNames
    def does_not_alter_ast(kitchen_sink_sdl):  # noqa: F811
        ast = parse(kitchen_sink_sdl)
        ast_copy = deepcopy(ast)
        print_ast(ast)
        assert ast == ast_copy

    # noinspection PyShadowingNames
    def prints_kitchen_sink(kitchen_sink_sdl):  # noqa: F811
        ast = parse(kitchen_sink_sdl)
        printed = print_ast(ast)

        assert printed == dedent(
            '''
            schema {
              query: QueryType
              mutation: MutationType
            }

            """
            This is a description
            of the `Foo` type.
            """
            type Foo implements Bar & Baz {
              "Description of the `one` field."
              one: Type
              """This is a description of the `two` field."""
              two(
                """This is a description of the `argument` argument."""
                argument: InputType!
              ): Type
              """This is a description of the `three` field."""
              three(argument: InputType, other: String): Int
              four(argument: String = "string"): String
              five(argument: [String] = ["string", "string"]): String
              six(argument: InputType = {key: "value"}): Type
              seven(argument: Int = null): Type
            }

            type AnnotatedObject @onObject(arg: "value") {
              annotatedField(arg: Type = "default" @onArgumentDefinition): Type @onField
            }

            type UndefinedType

            extend type Foo {
              seven(argument: [String]): Type
            }

            extend type Foo @onType

            interface Bar {
              one: Type
              four(argument: String = "string"): String
            }

            interface AnnotatedInterface @onInterface {
              annotatedField(arg: Type @onArgumentDefinition): Type @onField
            }

            interface UndefinedInterface

            extend interface Bar {
              two(argument: InputType!): Type
            }

            extend interface Bar @onInterface

            union Feed = Story | Article | Advert

            union AnnotatedUnion @onUnion = A | B

            union AnnotatedUnionTwo @onUnion = A | B

            union UndefinedUnion

            extend union Feed = Photo | Video

            extend union Feed @onUnion

            scalar CustomScalar

            scalar AnnotatedScalar @onScalar

            extend scalar CustomScalar @onScalar

            enum Site {
              """This is a description of the `DESKTOP` value"""
              DESKTOP
              """This is a description of the `MOBILE` value"""
              MOBILE
              "This is a description of the `WEB` value"
              WEB
            }

            enum AnnotatedEnum @onEnum {
              ANNOTATED_VALUE @onEnumValue
              OTHER_VALUE
            }

            enum UndefinedEnum

            extend enum Site {
              VR
            }

            extend enum Site @onEnum

            input InputType {
              key: String!
              answer: Int = 42
            }

            input AnnotatedInput @onInputObject {
              annotatedField: Type @onInputFieldDefinition
            }

            input UndefinedInput

            extend input InputType {
              other: Float = 1.23e4 @onInputFieldDefinition
            }

            extend input InputType @onInputObject

            """This is a description of the `@skip` directive"""
            directive @skip(if: Boolean! @onArgumentDefinition) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            directive @include(if: Boolean!) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            directive @include2(if: Boolean!) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            directive @myRepeatableDir(name: String!) repeatable on OBJECT | INTERFACE

            extend schema @onSchema

            extend schema @onSchema {
              subscription: SubscriptionType
            }
            '''  # noqa: E501
        )
