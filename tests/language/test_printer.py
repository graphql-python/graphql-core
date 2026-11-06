from copy import copy, deepcopy
from typing import Any

from pytest import raises

from graphql.error import GraphQLSyntaxError
from graphql.language import (
    FieldNode,
    ListTypeNode,
    ListValueNode,
    NamedTypeNode,
    NameNode,
    SelectionSetNode,
    Visitor,
    parse,
    parse_schema_coordinate,
    parse_value,
    print_ast,
    visit,
)

from graphql.language.printer import PrintBuffer, joined_length, print_for_error

from ..fixtures import kitchen_sink_query  # noqa: F401
from ..utils import dedent


def describe_printer_query_document():
    def limits_indentation_only_when_requested():
        ast = parse("{ a { b { c } } }")
        assert print_ast(ast, max_indent_depth=0) == "{ a { b { c } } }"
        assert print_ast(ast, max_indent_depth=1) == "{\n  a { b { c } }\n}"
        assert print_ast(ast, max_indent_depth=None) == print_ast(ast)

    def keeps_block_string_line_breaks():
        ast = parse_value('"""first\nsecond"""')
        assert print_ast(ast, max_indent_depth=0) == print_ast(ast)

    def caps_error_indentation_at_100_levels():
        selection_set = SelectionSetNode(selections=())
        for _level in range(300):
            selection_set = SelectionSetNode(
                selections=(
                    FieldNode(name=NameNode(value="a"), selection_set=selection_set),
                )
            )
        full = print_ast(selection_set)
        bounded = print_for_error(selection_set)
        assert "\n" + " " * 201 in full
        assert "\n" + " " * 200 in bounded
        assert "\n" + " " * 201 not in bounded
        assert "".join(bounded.split()) == "".join(full.split())

    def prints_deeply_nested_types_without_recursion():
        type_: Any = NamedTypeNode(name=NameNode(value="T"))
        for _depth in range(10_000):
            type_ = ListTypeNode(type=type_)

        assert print_ast(type_) == "[" * 10_000 + "T" + "]" * 10_000

    def prints_absent_variable_and_argument_definitions():
        class OptionalArrayRemover(Visitor):
            @staticmethod
            def enter_operation_definition(node, *_args):
                node = copy(node)
                node.variable_definitions = None
                return node

            @staticmethod
            def enter_field_definition(node, *_args):
                node = copy(node)
                node.arguments = None
                return node

            @staticmethod
            def enter_directive_definition(node, *_args):
                node = copy(node)
                node.arguments = None
                return node

        ast = visit(
            parse("query Q { f } type Query { f: String } directive @d on FIELD"),
            OptionalArrayRemover(),
        )

        assert print_ast(ast) == (
            "query Q {\n  f\n}\n\ntype Query {\n  f: String\n}"
            "\n\ndirective @d on FIELD"
        )

    def ignores_empty_items_when_wrapping_arguments():
        items = [PrintBuffer(), PrintBuffer("a"), PrintBuffer(), PrintBuffer("b")]
        assert joined_length(items, ", ") == 4

    def does_not_change_shared_input_nodes():
        value = parse_value("[1, 2]")
        ast = ListValueNode(values=(value, value))

        assert print_ast(ast) == "[[1, 2], [1, 2]]"
        assert print_ast(ast) == "[[1, 2], [1, 2]]"
        assert ast.values == (value, value)

    def prints_minimal_ast():
        ast = FieldNode(name=NameNode(value="foo"))
        assert print_ast(ast) == "foo"

    def produces_helpful_error_messages():
        bad_ast = {"random": "Data"}
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            print_ast(bad_ast)  # type: ignore
        assert str(exc_info.value) == "Not an AST Node: {'random': 'Data'}."
        corrupt_ast = FieldNode(name="random data")
        with raises(TypeError) as exc_info:
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
        assert print_ast(query_ast_with_artifacts) == dedent("""
            query ($foo: TestType) @testDirective {
              id
              name
            }
            """)

    def correctly_prints_mutation_operation_with_artifacts():
        mutation_ast_with_artifacts = parse(
            "mutation ($foo: TestType) @testDirective { id, name }"
        )
        assert print_ast(mutation_ast_with_artifacts) == dedent("""
            mutation ($foo: TestType) @testDirective {
              id
              name
            }
            """)

    def prints_query_with_variable_directives():
        query_ast_with_variable_directive = parse(
            "query ($foo: TestType = {a: 123}" " @testDirective(if: true) @test) { id }"
        )
        assert print_ast(query_ast_with_variable_directive) == dedent("""
            query ($foo: TestType = {a: 123} @testDirective(if: true) @test) {
              id
            }
            """)

    def keeps_arguments_on_one_line_if_line_has_80_chars_or_less():
        printed = print_ast(parse("{trip(wheelchair:false arriveBy:false){dateTime}}"))

        assert printed == dedent("""
            {
              trip(wheelchair: false, arriveBy: false) {
                dateTime
              }
            }
            """)

    def puts_arguments_on_multiple_lines_if_line_has_more_than_80_chars():
        printed = print_ast(
            parse(
                "{trip(wheelchair:false arriveBy:false includePlannedCancellations:true"
                " transitDistanceReluctance:2000){dateTime}}"
            )
        )

        assert printed == dedent("""
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
            """)

    def legacy_prints_fragment_with_variable_directives():
        query_ast_with_variable_directive = parse(
            "fragment Foo($foo: TestType @test) on TestType @testDirective { id }",
            allow_legacy_fragment_variables=True,
        )
        assert print_ast(query_ast_with_variable_directive) == dedent("""
            fragment Foo($foo: TestType @test) on TestType @testDirective {
              id
            }
            """)

    def experimental_prints_directives_on_directives():
        query_ast_with_variable_directive = parse(
            """
            directive @foo @bar on FIELD_DEFINITION
            extend directive @foo @baz
            """,
            experimental_directives_on_directive_definitions=True,
        )
        assert print_ast(query_ast_with_variable_directive) == dedent("""
            directive @foo @bar on FIELD_DEFINITION

            extend directive @foo @baz
            """)

    def legacy_correctly_prints_fragment_defined_variables():
        source = """
            fragment Foo($a: ComplexType, $b: Boolean = false) on TestType {
              id
            }
            """
        fragment_with_variable = parse(source, allow_legacy_fragment_variables=True)
        assert print_ast(fragment_with_variable) == dedent(source)

    def prints_fragment():
        printed = print_ast(parse('"Fragment description" fragment Foo on Bar { baz }'))
        assert printed == dedent("""
            "Fragment description"
            fragment Foo on Bar {
              baz
            }
            """)

    def prints_schema_coordinates():
        assert print_ast(parse_schema_coordinate("Name")) == "Name"
        assert print_ast(parse_schema_coordinate("Name.field")) == "Name.field"
        assert (
            print_ast(parse_schema_coordinate("Name.field(arg:)")) == "Name.field(arg:)"
        )
        assert print_ast(parse_schema_coordinate("@name")) == "@name"
        assert print_ast(parse_schema_coordinate("@name(arg:)")) == "@name(arg:)"
        assert print_ast(parse_schema_coordinate("__Type")) == "__Type"
        assert (
            print_ast(parse_schema_coordinate("Type.__metafield")) == "Type.__metafield"
        )
        assert (
            print_ast(parse_schema_coordinate("Type.__metafield(arg:)"))
            == "Type.__metafield(arg:)"
        )

    def throws_syntax_error_for_ignored_tokens_in_schema_coordinates():
        with raises(GraphQLSyntaxError) as exc_info:
            print_ast(parse_schema_coordinate("# foo\nName"))
        assert "Syntax Error: Invalid character: '#'" in str(exc_info.value)
        with raises(GraphQLSyntaxError) as exc_info:
            print_ast(parse_schema_coordinate("\nName"))
        assert "Syntax Error: Invalid character: U+000A." in str(exc_info.value)
        with raises(GraphQLSyntaxError) as exc_info:
            print_ast(parse_schema_coordinate("Name .field"))
        assert "Syntax Error: Invalid character: ' '" in str(exc_info.value)

    def prints_kitchen_sink_without_altering_ast(kitchen_sink_query):  # noqa: F811
        ast = parse(kitchen_sink_query, no_location=True)

        ast_before_print_call = deepcopy(ast)
        printed = print_ast(ast)
        printed_ast = parse(printed, no_location=True)
        assert printed_ast == ast
        assert deepcopy(ast) == ast_before_print_call

        assert printed == dedent(r'''
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
                obj: {key: "value", block: """
                block string uses \"""
                """}
              )
            }

            {
              unnamed(truthy: true, falsy: false, nullish: null)
              query
            }

            {
              __typename
            }
            ''')  # noqa: E501
