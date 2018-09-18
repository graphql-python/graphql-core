from copy import deepcopy

from pytest import raises

from graphql.language import ScalarTypeDefinitionNode, NameNode, print_ast, parse
from graphql.pyutils import dedent

# noinspection PyUnresolvedReferences
from . import schema_kitchen_sink as kitchen_sink  # noqa: F401


def describe_printer_sdl_document():
    def prints_minimal_ast():
        node = ScalarTypeDefinitionNode(name=NameNode(value="foo"))
        assert print_ast(node) == "scalar foo"

    def produces_helpful_error_messages():
        bad_ast1 = {"random": "Data"}
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            print_ast(bad_ast1)
        msg = str(exc_info.value)
        assert msg == "Not an AST Node: {'random': 'Data'}"

    # noinspection PyShadowingNames
    def does_not_alter_ast(kitchen_sink):  # noqa: F811
        ast = parse(kitchen_sink)
        ast_copy = deepcopy(ast)
        print_ast(ast)
        assert ast == ast_copy

    # noinspection PyShadowingNames
    def prints_kitchen_sink(kitchen_sink):  # noqa: F811
        ast = parse(kitchen_sink)
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
              one: Type
              """
              This is a description of the `two` field.
              """
              two(
                """
                This is a description of the `argument` argument.
                """
                argument: InputType!
              ): Type
              three(argument: InputType, other: String): Int
              four(argument: String = "string"): String
              five(argument: [String] = ["string", "string"]): String
              six(argument: InputType = {key: "value"}): Type
              seven(argument: Int = null): Type
            }

            type AnnotatedObject @onObject(arg: "value") {
              annotatedField(arg: Type = "default" @onArg): Type @onField
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
              annotatedField(arg: Type @onArg): Type @onField
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
              DESKTOP
              MOBILE
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
              annotatedField: Type @onField
            }

            input UndefinedInput

            extend input InputType {
              other: Float = 1.23e4
            }

            extend input InputType @onInputObject

            directive @skip(if: Boolean!) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            directive @include(if: Boolean!) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            directive @include2(if: Boolean!) on FIELD | FRAGMENT_SPREAD | INLINE_FRAGMENT

            extend schema @onSchema

            extend schema @onSchema {
              subscription: SubscriptionType
            }
            '''
        )  # noqa
