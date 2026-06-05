from copy import deepcopy

import pytest

from graphql.language import FieldNode, NameNode, parse, print_ast

from ..fixtures import kitchen_sink_query  # noqa: F401
from ..utils import dedent


def describe_printer_query_document():
    def prints_minimal_ast():
        ast = FieldNode(name=NameNode(value="foo"))
        assert print_ast(ast) == "foo"

    def produces_helpful_error_messages():
        bad_ast = {"random": "Data"}
        with pytest.raises(TypeError) as exc_info:
            print_ast(bad_ast)  # type: ignore
        assert str(exc_info.value) == "Not an AST Node: {'random': 'Data'}."
        corrupt_ast = FieldNode(name="random data")  # type: ignore[arg-type]
        with pytest.raises(TypeError) as exc_info:
            print_ast(corrupt_ast)
        assert str(exc_info.value) == "Invalid AST Node: 'random data'."

    def correctly_prints_query_operation_without_name():
        query_ast_shorthanded = parse("query { id, name }")
        assert print_ast(query_ast_shorthanded) == "{\n  id\n  name\n}"

    def correctly_prints_mutation_operation_without_name():
        mutation_ast = parse("mutation { id, name }")
        assert print_ast(mutation_ast) == "mutation {\n  id\n  name\n}"

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
            "query ($foo: TestType = { a: 123 } @testDirective(if: true) @test) { id }"
        )
        assert print_ast(query_ast_with_variable_directive) == dedent(
            """
            query ($foo: TestType = { a: 123 } @testDirective(if: true) @test) {
              id
            }
            """
        )

    def keeps_arguments_on_one_line_if_line_has_80_chars_or_less():
        printed = print_ast(parse("{trip(wheelchair:false arriveBy:false){dateTime}}"))

        assert printed == dedent(
            """
            {
              trip(wheelchair: false, arriveBy: false) {
                dateTime
              }
            }
            """
        )

    def puts_arguments_on_multiple_lines_if_line_has_more_than_80_chars():
        printed = print_ast(
            parse(
                "{trip(wheelchair:false arriveBy:false includePlannedCancellations:true"
                " transitDistanceReluctance:2000){dateTime}}"
            )
        )

        assert printed == dedent(
            """
            {
              trip(
                wheelchair: false
                arriveBy: false
                includePlannedCancellations: true
                transitDistanceReluctance: 2000
              ) {
                dateTime
              }
            }
            """
        )

    def puts_large_object_values_on_multiple_lines_if_line_has_more_than_80_chars():
        printed = print_ast(
            parse(
                "{trip(obj:{wheelchair:false,smallObj:{a: 1},largeObj:"
                "{wheelchair:false,smallObj:{a: 1},arriveBy:false,"
                "includePlannedCancellations:true,transitDistanceReluctance:2000,"
                'anotherLongFieldName:"Lots and lots and lots and lots of text"},'
                "arriveBy:false,includePlannedCancellations:true,"
                "transitDistanceReluctance:2000,anotherLongFieldName:"
                '"Lots and lots and lots and lots of text"}){dateTime}}'
            )
        )

        assert printed == dedent(
            """
            {
              trip(
                obj: {
                  wheelchair: false
                  smallObj: { a: 1 }
                  largeObj: {
                    wheelchair: false
                    smallObj: { a: 1 }
                    arriveBy: false
                    includePlannedCancellations: true
                    transitDistanceReluctance: 2000
                    anotherLongFieldName: "Lots and lots and lots and lots of text"
                  }
                  arriveBy: false
                  includePlannedCancellations: true
                  transitDistanceReluctance: 2000
                  anotherLongFieldName: "Lots and lots and lots and lots of text"
                }
              ) {
                dateTime
              }
            }
            """
        )

    def puts_large_list_values_on_multiple_lines_if_line_has_more_than_80_chars():
        printed = print_ast(
            parse(
                '{trip(list:[["small array", "small", "small"],'
                ' ["Lots and lots and lots and lots of text",'
                ' "Lots and lots and lots and lots of text",'
                ' "Lots and lots and lots and lots of text"]]){dateTime}}'
            )
        )

        assert printed == dedent(
            """
            {
              trip(
                list: [
                  ["small array", "small", "small"]
                  [
                    "Lots and lots and lots and lots of text"
                    "Lots and lots and lots and lots of text"
                    "Lots and lots and lots and lots of text"
                  ]
                ]
              ) {
                dateTime
              }
            }
            """
        )

    def prints_fragment_with_argument_definition_directives():
        fragment_with_argument_definition_directive = parse(
            "fragment Foo($foo: TestType @test) on TestType @testDirective { id }",
            experimental_fragment_arguments=True,
        )
        assert print_ast(fragment_with_argument_definition_directive) == dedent(
            """
            fragment Foo($foo: TestType @test) on TestType @testDirective {
              id
            }
            """
        )

    def correctly_prints_fragment_defined_arguments():
        source = """
            fragment Foo($a: ComplexType, $b: Boolean = false) on TestType {
              id
            }
            """
        fragment_with_argument_definition = parse(
            source, experimental_fragment_arguments=True
        )
        assert print_ast(fragment_with_argument_definition) == dedent(source)

    def prints_fragment_spread_with_arguments():
        fragment_spread_with_arguments = parse(
            "fragment Foo on TestType { ...Bar(a: {x: $x}, b: true) }",
            experimental_fragment_arguments=True,
        )
        assert print_ast(fragment_spread_with_arguments) == dedent(
            """
            fragment Foo on TestType {
              ...Bar(a: { x: $x }, b: true)
            }
            """
        )

    def prints_fragment_spread_with_multi_line_arguments():
        fragment_spread_with_arguments = parse(
            "fragment Foo on TestType { ...Bar(a: {x: $x, y: $y, z: $z, xy: $xy},"
            ' b: true, c: "a long string extending arguments over max length") }',
            experimental_fragment_arguments=True,
        )
        assert print_ast(fragment_spread_with_arguments) == dedent(
            """
            fragment Foo on TestType {
              ...Bar(
                a: { x: $x, y: $y, z: $z, xy: $xy }
                b: true
                c: "a long string extending arguments over max length"
              )
            }
            """
        )

    def prints_fragment():
        printed = print_ast(parse('"Fragment description" fragment Foo on Bar { baz }'))
        assert printed == dedent(
            """
            "Fragment description"
            fragment Foo on Bar {
              baz
            }
            """
        )

    def prints_kitchen_sink_without_altering_ast(kitchen_sink_query):  # noqa: F811
        ast = parse(kitchen_sink_query, no_location=True)

        ast_before_print_call = deepcopy(ast)
        printed = print_ast(ast)
        printed_ast = parse(printed, no_location=True)
        assert printed_ast == ast
        assert deepcopy(ast) == ast_before_print_call

        assert printed == dedent(
            r'''
            "Query description"
            query queryName(
            "Very complex variable"
            $foo: ComplexType
            $site: Site = MOBILE
            ) @onQuery {
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

            subscription StoryLikeSubscription($input: StoryLikeSubscribeInput @onVariableDefinition) @onSubscription {
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

            """Fragment description"""
            fragment frag on Friend @onFragmentDefinition {
              foo(
                size: $size
                bar: $b
                obj: { key: "value", block: """
                block string uses \"""
                """ }
              )
            }

            {
              unnamed(truthy: true, falsy: false, nullish: null)
              query
            }

            {
              __typename
            }
            '''  # noqa: E501
        )
