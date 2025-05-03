from __future__ import annotations

from typing import Optional, Tuple, cast

import pytest

from graphql.error import GraphQLSyntaxError
from graphql.language import (
    ArgumentNode,
    DefinitionNode,
    DocumentNode,
    ErrorBoundaryNode,
    FieldNode,
    IntValueNode,
    ListNullabilityOperatorNode,
    ListTypeNode,
    ListValueNode,
    NamedTypeNode,
    NameNode,
    NonNullAssertionNode,
    NonNullTypeNode,
    NullabilityAssertionNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    Source,
    StringValueNode,
    Token,
    TokenKind,
    ValueNode,
    VariableNode,
    parse,
    parse_const_value,
    parse_type,
    parse_value,
)
from graphql.pyutils import inspect

from ..fixtures import kitchen_sink_query  # noqa: F401
from ..utils import dedent

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias


Location: TypeAlias = Optional[Tuple[int, int]]


def parse_ccn(source: str) -> DocumentNode:
    return parse(source, experimental_client_controlled_nullability=True)


def assert_syntax_error(text: str, message: str, location: Location) -> None:
    with pytest.raises(GraphQLSyntaxError) as exc_info:
        parse(text)
    error = exc_info.value
    assert error.message == f"Syntax Error: {message}"
    assert error.description == message
    assert error.locations == [location]


def assert_syntax_error_ccn(text: str, message: str, location: Location) -> None:
    with pytest.raises(GraphQLSyntaxError) as exc_info:
        parse_ccn(text)
    error = exc_info.value
    assert error.message == f"Syntax Error: {message}"
    assert error.description == message
    assert error.locations == [location]


def describe_parser():
    def parse_provides_useful_errors():
        with pytest.raises(GraphQLSyntaxError) as exc_info:
            parse("{")
        error = exc_info.value
        assert error.message == "Syntax Error: Expected Name, found <EOF>."
        assert error.positions == [1]
        assert error.locations == [(1, 2)]
        assert str(error) == dedent(
            """
            Syntax Error: Expected Name, found <EOF>.

            GraphQL request:1:2
            1 | {
              |  ^
            """
        )
        assert_syntax_error(
            "\n      { ...MissingOn }\n      fragment MissingOn Type",
            "Expected 'on', found Name 'Type'.",
            (3, 26),
        )
        assert_syntax_error("{ field: {} }", "Expected Name, found '{'.", (1, 10))
        assert_syntax_error(
            "notAnOperation Foo { field }", "Unexpected Name 'notAnOperation'.", (1, 1)
        )
        assert_syntax_error("...", "Unexpected '...'.", (1, 1))
        assert_syntax_error('{ ""', "Expected Name, found String ''.", (1, 3))

    def parse_provides_useful_error_when_using_source():
        with pytest.raises(GraphQLSyntaxError) as exc_info:
            parse(Source("query", "MyQuery.graphql"))
        error = exc_info.value
        assert str(error) == dedent(
            """
            Syntax Error: Expected '{', found <EOF>.

            MyQuery.graphql:1:6
            1 | query
              |      ^
            """
        )

    def limits_by_a_maximum_number_of_tokens():
        parse("{ foo }", max_tokens=3)
        with pytest.raises(
            GraphQLSyntaxError,
            match="Syntax Error:"
            r" Document contains more than 2 tokens\. Parsing aborted\.",
        ):
            parse("{ foo }", max_tokens=2)
        parse('{ foo(bar: "baz") }', max_tokens=8)
        with pytest.raises(
            GraphQLSyntaxError,
            match="Syntax Error:"
            r" Document contains more than 7 tokens\. Parsing aborted\.",
        ):
            parse('{ foo(bar: "baz") }', max_tokens=7)

    def parses_variable_inline_values():
        parse("{ field(complex: { a: { b: [ $var ] } }) }")

    def parses_constant_default_values():
        assert_syntax_error(
            "query Foo($x: Complex = { a: { b: [ $var ] } }) { field }",
            "Unexpected variable '$var' in constant value.",
            (1, 37),
        )

    def parses_variable_definition_directives():
        parse("query Foo($x: Boolean = false @bar) { field }")

    def does_not_accept_fragments_named_on():
        assert_syntax_error(
            "fragment on on on { on }", "Unexpected Name 'on'.", (1, 10)
        )

    def does_not_accept_fragments_spread_of_on():
        assert_syntax_error("{ ...on }", "Expected Name, found '}'.", (1, 9))

    def does_not_allow_true_false_or_null_as_enum_value():
        assert_syntax_error(
            "enum Test { VALID, true }",
            "Name 'true' is reserved and cannot be used for an enum value.",
            (1, 20),
        )
        assert_syntax_error(
            "enum Test { VALID, false }",
            "Name 'false' is reserved and cannot be used for an enum value.",
            (1, 20),
        )
        assert_syntax_error(
            "enum Test { VALID, null }",
            "Name 'null' is reserved and cannot be used for an enum value.",
            (1, 20),
        )

    def parses_multi_byte_characters():
        # Note: \u0A0A could be naively interpreted as two line-feed chars.
        doc = parse(
            """
            # This comment has a \u0a0a multi-byte character.
            { field(arg: "Has a \u0a0a multi-byte character.") }
            """
        )
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        selection_set = cast("OperationDefinitionNode", definitions[0]).selection_set
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        arguments = cast("FieldNode", selections[0]).arguments
        assert isinstance(arguments, tuple)
        assert len(arguments) == 1
        value = arguments[0].value
        assert isinstance(value, StringValueNode)
        assert value.value == "Has a \u0a0a multi-byte character."

    # noinspection PyShadowingNames
    def parses_kitchen_sink(kitchen_sink_query):  # noqa: F811
        parse_ccn(kitchen_sink_query)

    def allows_non_keywords_anywhere_a_name_is_allowed():
        non_keywords = (
            "on",
            "fragment",
            "query",
            "mutation",
            "subscription",
            "true",
            "false",
        )
        for keyword in non_keywords:
            # You can't define or reference a fragment named `on`.
            fragment_name = "a" if keyword == "on" else keyword
            document = f"""
                query {keyword} {{
                  ... {fragment_name}
                  ... on {keyword} {{ field }}
                }}
                fragment {fragment_name} on Type {{
                  {keyword}({keyword}: ${keyword})
                    @{keyword}({keyword}: {keyword})
                }}
                """
            parse(document)

    def parses_anonymous_mutation_operations():
        parse(
            """
            mutation {
              mutationField
            }
            """
        )

    def parses_anonymous_subscription_operations():
        parse(
            """
            subscription {
              subscriptionField
            }
            """
        )

    def parses_named_mutation_operations():
        parse(
            """
            mutation Foo {
              mutationField
            }
            """
        )

    def parses_named_subscription_operations():
        parse(
            """
            subscription Foo {
              subscriptionField
            }
            """
        )

    def parses_required_field():
        doc = parse_ccn("{ requiredField! }")
        assert isinstance(doc, DocumentNode)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast("OperationDefinitionNode", definitions[0])
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        nullability_assertion = field.nullability_assertion
        assert isinstance(nullability_assertion, NonNullAssertionNode)
        assert nullability_assertion.loc == (15, 16)
        assert nullability_assertion.nullability_assertion is None

    def parses_optional_field():
        parse_ccn("{ optionalField? }")

    def does_not_parse_field_with_multiple_designators():
        assert_syntax_error_ccn(
            "{ optionalField?! }", "Expected Name, found '!'.", (1, 17)
        )
        assert_syntax_error_ccn(
            "{ optionalField!? }", "Expected Name, found '?'.", (1, 17)
        )

    def parses_required_with_alias():
        parse_ccn("{ requiredField: field! }")

    def parses_optional_with_alias():
        parse_ccn("{ requiredField: field? }")

    def does_not_parse_aliased_field_with_bang_on_left_of_colon():
        assert_syntax_error_ccn(
            "{ requiredField!: field }", "Expected Name, found ':'.", (1, 17)
        )

    def does_not_parse_aliased_field_with_question_mark_on_left_of_colon():
        assert_syntax_error_ccn(
            "{ requiredField?: field }", "Expected Name, found ':'.", (1, 17)
        )

    def does_not_parse_aliased_field_with_bang_on_left_and_right_of_colon():
        assert_syntax_error_ccn(
            "{ requiredField!: field! }", "Expected Name, found ':'.", (1, 17)
        )

    def does_not_parse_aliased_field_with_question_mark_on_left_and_right_of_colon():
        assert_syntax_error_ccn(
            "{ requiredField?: field? }", "Expected Name, found ':'.", (1, 17)
        )

    def does_not_parse_designator_on_query():
        assert_syntax_error_ccn("query? { field }", "Expected '{', found '?'.", (1, 6))

    def parses_required_within_fragment():
        parse_ccn("fragment MyFragment on Query { field! }")

    def parses_optional_within_fragment():
        parse_ccn("fragment MyFragment on Query { field? }")

    def parses_field_with_required_list_elements():
        doc = parse_ccn("{ field[!] }")
        assert isinstance(doc, DocumentNode)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast("OperationDefinitionNode", definitions[0])
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        nullability_assertion: NullabilityAssertionNode | None = (
            field.nullability_assertion
        )
        assert isinstance(nullability_assertion, ListNullabilityOperatorNode)
        assert nullability_assertion.loc == (7, 10)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, NonNullAssertionNode)
        assert nullability_assertion.loc == (8, 9)
        assert nullability_assertion.nullability_assertion is None

    def parses_field_with_optional_list_elements():
        doc = parse_ccn("{ field[?] }")
        assert isinstance(doc, DocumentNode)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast("OperationDefinitionNode", definitions[0])
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        nullability_assertion: NullabilityAssertionNode | None = (
            field.nullability_assertion
        )
        assert isinstance(nullability_assertion, ListNullabilityOperatorNode)
        assert nullability_assertion.loc == (7, 10)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, ErrorBoundaryNode)
        assert nullability_assertion.loc == (8, 9)
        assert nullability_assertion.nullability_assertion is None

    def parses_field_with_required_list():
        doc = parse_ccn("{ field[]! }")
        assert isinstance(doc, DocumentNode)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast("OperationDefinitionNode", definitions[0])
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        nullability_assertion: NullabilityAssertionNode | None = (
            field.nullability_assertion
        )
        assert isinstance(nullability_assertion, NonNullAssertionNode)
        assert nullability_assertion.loc == (7, 10)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, ListNullabilityOperatorNode)
        assert nullability_assertion.loc == (7, 9)
        assert nullability_assertion.nullability_assertion is None

    def parses_field_with_optional_list():
        doc = parse_ccn("{ field[]? }")
        assert isinstance(doc, DocumentNode)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast("OperationDefinitionNode", definitions[0])
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        nullability_assertion: NullabilityAssertionNode | None = (
            field.nullability_assertion
        )
        assert isinstance(nullability_assertion, ErrorBoundaryNode)
        assert nullability_assertion.loc == (7, 10)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, ListNullabilityOperatorNode)
        assert nullability_assertion.loc == (7, 9)
        assert nullability_assertion.nullability_assertion is None

    def parses_field_with_mixed_list_elements():
        doc = parse_ccn("{ field[[[?]!]]! }")
        assert isinstance(doc, DocumentNode)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast("OperationDefinitionNode", definitions[0])
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        nullability_assertion: NullabilityAssertionNode | None = (
            field.nullability_assertion
        )
        assert isinstance(nullability_assertion, NonNullAssertionNode)
        assert nullability_assertion.loc == (7, 16)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, ListNullabilityOperatorNode)
        assert nullability_assertion.loc == (7, 15)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, ListNullabilityOperatorNode)
        assert nullability_assertion.loc == (8, 14)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, NonNullAssertionNode)
        assert nullability_assertion.loc == (9, 13)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, ListNullabilityOperatorNode)
        assert nullability_assertion.loc == (9, 12)
        nullability_assertion = nullability_assertion.nullability_assertion
        assert isinstance(nullability_assertion, ErrorBoundaryNode)
        assert nullability_assertion.loc == (10, 11)
        assert nullability_assertion.nullability_assertion is None

    def does_not_parse_field_with_unbalanced_brackets():
        assert_syntax_error_ccn("{ field[[] }", "Expected ']', found '}'.", (1, 12))
        assert_syntax_error_ccn("{ field[]] }", "Expected Name, found ']'.", (1, 10))
        assert_syntax_error_ccn("{ field] }", "Expected Name, found ']'.", (1, 8))
        assert_syntax_error_ccn("{ field[ }", "Expected ']', found '}'.", (1, 10))

    def does_not_parse_field_with_assorted_invalid_nullability_designators():
        assert_syntax_error_ccn("{ field[][] }", "Expected Name, found '['.", (1, 10))
        assert_syntax_error_ccn("{ field[!!] }", "Expected ']', found '!'.", (1, 10))
        assert_syntax_error_ccn("{ field[]?! }", "Expected Name, found '!'.", (1, 11))

    def creates_ast():
        doc = parse(
            dedent(
                """
                {
                  node(id: 4) {
                    id,
                    name
                  }
                }
                """
            )
        )
        assert isinstance(doc, DocumentNode)
        assert doc.loc == (0, 40)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast("OperationDefinitionNode", definitions[0])
        assert isinstance(definition, DefinitionNode)
        assert definition.loc == (0, 40)
        assert definition.operation == OperationType.QUERY
        assert definition.name is None
        assert definition.variable_definitions == ()
        assert definition.directives == ()
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        assert selection_set.loc == (0, 40)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        assert field.loc == (4, 38)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (4, 8)
        assert name.value == "node"
        arguments = field.arguments
        assert isinstance(arguments, tuple)
        assert len(arguments) == 1
        argument = arguments[0]
        assert isinstance(argument, ArgumentNode)
        name = argument.name
        assert isinstance(name, NameNode)
        assert name.loc == (9, 11)
        assert name.value == "id"
        value = argument.value
        assert isinstance(value, ValueNode)
        assert isinstance(value, IntValueNode)
        assert value.loc == (13, 14)
        assert value.value == "4"
        assert argument.loc == (9, 14)
        assert field.nullability_assertion is None
        assert field.directives == ()
        selection_set = field.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 2
        field = selections[0]
        assert isinstance(field, FieldNode)
        assert field.loc == (22, 24)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (22, 24)
        assert name.value == "id"
        assert field.arguments == ()
        assert field.nullability_assertion is None
        assert field.directives == ()
        assert field.selection_set is None
        field = selections[1]
        assert isinstance(field, FieldNode)
        assert field.loc == (30, 34)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (30, 34)
        assert name.value == "name"
        assert field.arguments == ()
        assert field.nullability_assertion is None
        assert field.directives == ()
        assert field.selection_set is None

    def creates_ast_from_nameless_query_without_variables():
        doc = parse(
            dedent(
                """
                query {
                  node {
                    id
                  }
                }
                """
            )
        )
        assert isinstance(doc, DocumentNode)
        assert doc.loc == (0, 29)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = definitions[0]
        assert isinstance(definition, OperationDefinitionNode)
        assert definition.loc == (0, 29)
        assert definition.operation == OperationType.QUERY
        assert definition.name is None
        assert definition.variable_definitions == ()
        assert definition.directives == ()
        selection_set: SelectionSetNode | None = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        assert selection_set.loc == (6, 29)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        assert field.loc == (10, 27)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (10, 14)
        assert name.value == "node"
        assert field.arguments == ()
        assert field.nullability_assertion is None
        assert field.directives == ()
        selection_set = field.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        assert selection_set.loc == (15, 27)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        assert field.loc == (21, 23)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (21, 23)
        assert name.value == "id"
        assert field.arguments == ()
        assert field.nullability_assertion is None
        assert field.directives == ()
        assert field.selection_set is None

    def allows_parsing_without_source_location_information():
        result = parse("{ id }", no_location=True)
        assert result.loc is None

    def legacy_allows_parsing_fragment_defined_variables():
        document = "fragment a($v: Boolean = false) on t { f(v: $v) }"
        parse(document, allow_legacy_fragment_variables=True)
        with pytest.raises(GraphQLSyntaxError):
            parse(document)

    def contains_location_information_that_only_stringifies_start_end():
        result = parse("{ id }")
        assert str(result.loc) == "0:6"
        assert repr(result.loc) == "<Location 0:6>"
        assert inspect(result.loc) == repr(result.loc)

    def contains_references_to_source():
        source = Source("{ id }")
        result = parse(source)
        assert result.loc
        assert result.loc.source is source

    def contains_references_to_start_and_end_tokens():
        result = parse("{ id }")
        start_token = result.loc and result.loc.start_token
        assert isinstance(start_token, Token)
        assert start_token.kind == TokenKind.SOF
        end_token = result.loc and result.loc.end_token
        assert isinstance(end_token, Token)
        assert end_token.kind == TokenKind.EOF

    def allows_comments_everywhere_in_the_source():
        # make sure first and last line can be comment
        result = parse(
            """# top comment
            {
              field # field comment
            }
            # bottom comment"""
        )
        top_comment = result.loc and result.loc.start_token.next
        assert top_comment
        assert top_comment.kind is TokenKind.COMMENT
        assert top_comment.value == " top comment"
        field_comment = top_comment.next.next.next  # type: ignore
        assert field_comment
        assert field_comment.kind is TokenKind.COMMENT
        assert field_comment.value == " field comment"
        bottom_comment = field_comment.next.next  # type: ignore
        assert bottom_comment
        assert bottom_comment.kind is TokenKind.COMMENT
        assert bottom_comment.value == " bottom comment"


def describe_parse_value():
    def parses_null_value():
        result = parse_value("null")
        assert isinstance(result, NullValueNode)
        assert result.loc == (0, 4)

    def parses_empty_strings():
        result = parse_value('""')
        assert isinstance(result, StringValueNode)
        assert result.value == ""
        assert result.loc == (0, 2)

    def parses_list_values():
        result = parse_value('[123 "abc"]')
        assert isinstance(result, ListValueNode)
        assert result.loc == (0, 11)
        values = result.values
        assert isinstance(values, tuple)
        assert len(values) == 2
        value = values[0]
        assert isinstance(value, IntValueNode)
        assert value.loc == (1, 4)
        assert value.value == "123"
        value = values[1]
        assert isinstance(value, StringValueNode)
        assert value.loc == (5, 10)
        assert value.value == "abc"

    def parses_block_strings():
        result = parse_value('["""long""" "short"]')
        assert isinstance(result, ListValueNode)
        assert result.loc == (0, 20)
        values = result.values
        assert isinstance(values, tuple)
        assert len(values) == 2
        value = values[0]
        assert isinstance(value, StringValueNode)
        assert value.loc == (1, 11)
        assert value.value == "long"
        assert value.block is True
        value = values[1]
        assert isinstance(value, StringValueNode)
        assert value.loc == (12, 19)
        assert value.value == "short"
        assert value.block is False

    def allows_variables():
        result = parse_value("{ field: $var }")
        assert isinstance(result, ObjectValueNode)
        assert result.loc == (0, 15)
        fields = result.fields
        assert len(fields) == 1
        field = fields[0]
        assert isinstance(field, ObjectFieldNode)
        assert field.loc == (2, 13)
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (2, 7)
        assert name.value == "field"
        value = field.value
        assert isinstance(value, VariableNode)
        assert value.loc == (9, 13)
        name = value.name
        assert isinstance(name, NameNode)
        assert name.loc == (10, 13)
        assert name.value == "var"

    def correct_message_for_incomplete_variable():
        with pytest.raises(GraphQLSyntaxError) as exc_info:
            parse_value("$")
        assert exc_info.value == {
            "message": "Syntax Error: Expected Name, found <EOF>.",
            "locations": [(1, 2)],
        }

    def correct_message_for_unexpected_token():
        with pytest.raises(GraphQLSyntaxError) as exc_info:
            parse_value(":")
        assert exc_info.value == {
            "message": "Syntax Error: Unexpected ':'.",
            "locations": [(1, 1)],
        }


def describe_parse_const_value():
    def parses_values():
        result = parse_const_value('[123 "abc"]')
        assert isinstance(result, ListValueNode)
        assert result.loc == (0, 11)
        values = result.values
        assert len(values) == 2
        value = values[0]
        assert isinstance(value, IntValueNode)
        assert value.loc == (1, 4)
        assert value.value == "123"
        value = values[1]
        assert isinstance(value, StringValueNode)
        assert value.loc == (5, 10)
        assert value.value == "abc"
        assert value.block is False

    def does_not_allow_variables():
        with pytest.raises(GraphQLSyntaxError) as exc_info:
            parse_const_value("{ field: $var }")
        assert exc_info.value == {
            "message": "Syntax Error: Unexpected variable '$var' in constant value.",
            "locations": [(1, 10)],
        }

    def correct_message_for_unexpected_token():
        with pytest.raises(GraphQLSyntaxError) as exc_info:
            parse_const_value("$$")
        assert exc_info.value == {
            "message": "Syntax Error: Unexpected '$'.",
            "locations": [(1, 1)],
        }


def describe_parse_type():
    def parses_well_known_types():
        result = parse_type("String")
        assert isinstance(result, NamedTypeNode)
        assert result.loc == (0, 6)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 6)
        assert name.value == "String"

    def parses_custom_types():
        result = parse_type("MyType")
        assert isinstance(result, NamedTypeNode)
        assert result.loc == (0, 6)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 6)
        assert name.value == "MyType"

    def parses_list_types():
        result = parse_type("[MyType]")
        assert isinstance(result, ListTypeNode)
        assert result.loc == (0, 8)
        type_ = result.type
        assert isinstance(type_, NamedTypeNode)
        assert type_.loc == (1, 7)
        name = type_.name
        assert isinstance(name, NameNode)
        assert name.loc == (1, 7)
        assert name.value == "MyType"

    def parses_non_null_types():
        result = parse_type("MyType!")
        assert isinstance(result, NonNullTypeNode)
        assert result.loc == (0, 7)
        type_ = result.type
        assert isinstance(type_, NamedTypeNode)
        assert type_.loc == (0, 6)
        name = type_.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 6)
        assert name.value == "MyType"

    def parses_nested_types():
        result = parse_type("[MyType!]")
        assert isinstance(result, ListTypeNode)
        assert result.loc == (0, 9)
        type_ = result.type
        assert isinstance(type_, NonNullTypeNode)
        assert type_.loc == (1, 8)
        type_ = type_.type
        assert isinstance(type_, NamedTypeNode)
        assert type_.loc == (1, 7)
        name = type_.name
        assert isinstance(name, NameNode)
        assert name.loc == (1, 7)
        assert name.value == "MyType"
