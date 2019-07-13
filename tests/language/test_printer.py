from copy import deepcopy

from pytest import raises  # type: ignore

from graphql.pyutils import dedent
from graphql.language import FieldNode, NameNode, parse, print_ast

# noinspection PyUnresolvedReferences
from ..fixtures import kitchen_sink_query  # noqa: F401


def describe_printer_query_document():

    # noinspection PyShadowingNames
    def does_not_alter_ast(kitchen_sink_query):  # noqa: F811
        ast = parse(kitchen_sink_query)
        ast_before = deepcopy(ast)
        print_ast(ast)
        assert ast == ast_before

    def prints_minimal_ast():
        ast = FieldNode(name=NameNode(value="foo"))
        assert print_ast(ast) == "foo"

    def produces_helpful_error_messages():
        bad_ast = {"random": "Data"}
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            print_ast(bad_ast)
        msg = str(exc_info.value)
        assert msg == "Not an AST Node: {'random': 'Data'}"

    def correctly_prints_query_operation_without_name():
        query_ast_shorthanded = parse("query { id, name }")
        assert print_ast(query_ast_shorthanded) == "{\n  id\n  name\n}\n"

    def correctly_prints_mutation_operation_without_name():
        mutation_ast = parse("mutation { id, name }")
        assert print_ast(mutation_ast) == "mutation {\n  id\n  name\n}\n"

    def correctly_prints_query_operation_with_artifacts():
        query_ast_with_artifacts = parse(
            "query ($foo: TestType) @testDirective { id, name }"
        )
        assert print_ast(query_ast_with_artifacts) == dedent(
            """
            query ($foo: TestType) @testDirective {
              id
              name
            }
            """
        )

    def correctly_prints_mutation_operation_with_artifacts():
        mutation_ast_with_artifacts = parse(
            "mutation ($foo: TestType) @testDirective { id, name }"
        )
        assert print_ast(mutation_ast_with_artifacts) == dedent(
            """
            mutation ($foo: TestType) @testDirective {
              id
              name
            }
            """
        )

    def prints_query_with_variable_directives():
        query_ast_with_variable_directive = parse(
            "query ($foo: TestType = {a: 123}" " @testDirective(if: true) @test) { id }"
        )
        assert print_ast(query_ast_with_variable_directive) == dedent(
            """
            query ($foo: TestType = {a: 123} @testDirective(if: true) @test) {
              id
            }
            """
        )

    def experimental_prints_fragment_with_variable_directives():
        query_ast_with_variable_directive = parse(
            "fragment Foo($foo: TestType @test) on TestType @testDirective { id }",
            experimental_fragment_variables=True,
        )
        assert print_ast(query_ast_with_variable_directive) == dedent(
            """
            fragment Foo($foo: TestType @test) on TestType @testDirective {
              id
            }
            """
        )

    def experimental_correctly_prints_fragment_defined_variables():
        source = """
            fragment Foo($a: ComplexType, $b: Boolean = false) on TestType {
              id
            }
            """
        fragment_with_variable = parse(source, experimental_fragment_variables=True)
        assert print_ast(fragment_with_variable) == dedent(source)

    # noinspection PyShadowingNames
    def prints_kitchen_sink(kitchen_sink_query):  # noqa: F811
        ast = parse(kitchen_sink_query)
        printed = print_ast(ast)
        assert printed == dedent(
            r'''
            query queryName($foo: ComplexType, $site: Site = MOBILE) @onQuery {
              whoever123is: node(id: [123, 456]) {
                id
                ... on User @onInlineFragment {
                  field2 {
                    id
                    alias: field1(first: 10, after: $foo) @include(if: $foo) {
                      id
                      ...frag @onFragmentSpread
                    }
                  }
                }
                ... @skip(unless: $foo) {
                  id
                }
                ... {
                  id
                }
              }
            }

            mutation likeStory @onMutation {
              like(story: 123) @onField {
                story {
                  id @onField
                }
              }
            }

            subscription StoryLikeSubscription($input: StoryLikeSubscribeInput) @onSubscription {
              storyLikeSubscribe(input: $input) {
                story {
                  likers {
                    count
                  }
                  likeSentence {
                    text
                  }
                }
              }
            }

            fragment frag on Friend @onFragmentDefinition {
              foo(size: $size, bar: $b, obj: {key: "value", block: """
                block string uses \"""
              """})
            }

            {
              unnamed(truthy: true, falsey: false, nullish: null)
              query
            }

            {
              __typename
            }
            '''  # noqa: E501
        )
