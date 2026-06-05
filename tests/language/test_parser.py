from typing import cast, Optional, Tuple

from pytest import raises

from graphql.error import GraphQLSyntaxError
from graphql.language import (
    ArgumentCoordinateNode,
    ArgumentNode,
    DefinitionNode,
    DirectiveArgumentCoordinateNode,
    DirectiveCoordinateNode,
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    IntValueNode,
    ListTypeNode,
    ListValueNode,
    MemberCoordinateNode,
    NameNode,
    NamedTypeNode,
    NonNullTypeNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    StringValueNode,
    TypeCoordinateNode,
    ValueNode,
    VariableDefinitionNode,
    VariableNode,
    Token,
    TokenKind,
    parse,
    parse_schema_coordinate,
    parse_type,
    parse_value,
    parse_const_value,
    Source,
)
from graphql.pyutils import inspect

from ..fixtures import kitchen_sink_query  # noqa: F401
from ..utils import dedent

Location = Optional[Tuple[int, int]]


def assert_syntax_error(text: str, message: str, location: Location) -> None:
    with raises(GraphQLSyntaxError) as exc_info:
        parse(text)
    error = exc_info.value
    assert error.message == f"Syntax Error: {message}"
    assert error.description == message
    assert error.locations == [location]


def describe_parser():
    def parse_provides_useful_errors():
        with raises(GraphQLSyntaxError) as exc_info:
            parse("{")
        error = exc_info.value
        assert error.message == "Syntax Error: Expected Name, found <EOF>."
        assert error.positions == [1]
        assert error.locations == [(1, 2)]
        assert str(error) == dedent("""
            Syntax Error: Expected Name, found <EOF>.

            GraphQL request:1:2
            1 | {
              |  ^
            """)
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
        with raises(GraphQLSyntaxError) as exc_info:
            parse(Source("query", "MyQuery.graphql"))
        error = exc_info.value
        assert str(error) == dedent("""
            Syntax Error: Expected '{', found <EOF>.

            MyQuery.graphql:1:6
            1 | query
              |      ^
            """)

    def exposes_the_token_count():
        assert parse("{ foo }").token_count == 3
        assert parse('{ foo(bar: "baz") }').token_count == 8

    def limits_maximum_number_of_tokens():
        assert parse("{ foo }", max_tokens=3)
        with raises(
            GraphQLSyntaxError,
            match="Syntax Error: Document contains more than 2 tokens."
            " Parsing aborted.",
        ):
            assert parse("{ foo }", max_tokens=2)

        assert parse('{ foo(bar: "baz") }', max_tokens=8)
        with raises(
            GraphQLSyntaxError,
            match="Syntax Error: Document contains more than 7 tokens."
            " Parsing aborted.",
        ):
            assert parse('{ foo(bar: "baz") }', max_tokens=7)

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
        doc = parse("""
            # This comment has a \u0a0a multi-byte character.
            { field(arg: "Has a \u0a0a multi-byte character.") }
            """)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        selection_set = cast(OperationDefinitionNode, definitions[0]).selection_set
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        arguments = cast(FieldNode, selections[0]).arguments
        assert isinstance(arguments, tuple)
        assert len(arguments) == 1
        value = arguments[0].value
        assert isinstance(value, StringValueNode)
        assert value.value == "Has a \u0a0a multi-byte character."

    # noinspection PyShadowingNames
    def parses_kitchen_sink(kitchen_sink_query):  # noqa: F811
        parse(kitchen_sink_query)

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
        parse("""
            mutation {
              mutationField
            }
            """)

    def parses_anonymous_subscription_operations():
        parse("""
            subscription {
              subscriptionField
            }
            """)

    def parses_named_mutation_operations():
        parse("""
            mutation Foo {
              mutationField
            }
            """)

    def parses_named_subscription_operations():
        parse("""
            subscription Foo {
              subscriptionField
            }
            """)

    def creates_ast():
        doc = parse(dedent("""
                {
                  node(id: 4) {
                    id,
                    name
                  }
                }
                """))
        assert isinstance(doc, DocumentNode)
        assert doc.loc == (0, 40)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = cast(OperationDefinitionNode, definitions[0])
        assert isinstance(definition, DefinitionNode)
        assert definition.loc == (0, 40)
        assert definition.operation == OperationType.QUERY
        assert definition.description is None
        assert definition.name is None
        assert definition.variable_definitions == ()
        assert definition.directives == ()
        selection_set: Optional[SelectionSetNode] = definition.selection_set
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
        assert field.directives == ()
        assert field.selection_set is None
        field = selections[0]
        assert isinstance(field, FieldNode)
        assert field.loc == (22, 24)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (22, 24)
        assert name.value == "id"
        assert field.arguments == ()
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
        assert field.directives == ()
        assert field.selection_set is None

    def creates_ast_from_nameless_query_without_variables():
        doc = parse(dedent("""
                query {
                  node {
                    id
                  }
                }
                """))
        assert isinstance(doc, DocumentNode)
        assert doc.loc == (0, 29)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = definitions[0]
        assert isinstance(definition, OperationDefinitionNode)
        assert definition.loc == (0, 29)
        assert definition.operation == OperationType.QUERY
        assert definition.description is None
        assert definition.name is None
        assert definition.variable_definitions == ()
        assert definition.directives == ()
        selection_set: Optional[SelectionSetNode] = definition.selection_set
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
        assert field.directives == ()
        assert field.selection_set is None

    def creates_ast_from_nameless_query_with_description():
        doc = parse(dedent("""
                "Description"
                query {
                  node {
                    id
                  }
                }
                """))
        assert isinstance(doc, DocumentNode)
        assert doc.loc == (0, 43)
        definitions = doc.definitions
        assert isinstance(definitions, tuple)
        assert len(definitions) == 1
        definition = definitions[0]
        assert isinstance(definition, OperationDefinitionNode)
        assert definition.loc == (0, 43)
        description = definition.description
        assert isinstance(description, StringValueNode)
        assert description.loc == (0, 13)
        assert description.value == "Description"
        assert description.block is False
        assert definition.operation == OperationType.QUERY
        assert definition.name is None
        assert definition.variable_definitions == ()
        assert definition.directives == ()
        selection_set: Optional[SelectionSetNode] = definition.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        assert selection_set.loc == (20, 43)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        assert field.loc == (24, 41)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (24, 28)
        assert name.value == "node"
        assert field.arguments == ()
        assert field.directives == ()
        selection_set = field.selection_set
        assert isinstance(selection_set, SelectionSetNode)
        assert selection_set.loc == (29, 41)
        selections = selection_set.selections
        assert isinstance(selections, tuple)
        assert len(selections) == 1
        field = selections[0]
        assert isinstance(field, FieldNode)
        assert field.loc == (35, 37)
        assert field.alias is None
        name = field.name
        assert isinstance(name, NameNode)
        assert name.loc == (35, 37)
        assert name.value == "id"
        assert field.arguments == ()
        assert field.directives == ()
        assert field.selection_set is None

    def allows_parsing_without_source_location_information():
        result = parse("{ id }", no_location=True)
        assert result.loc is None

    def legacy_allows_parsing_fragment_defined_variables():
        document = "fragment a($v: Boolean = false) on t { f(v: $v) }"
        parse(document, allow_legacy_fragment_variables=True)
        with raises(GraphQLSyntaxError):
            parse(document)

    def contains_location_information_that_only_stringifies_start_end():
        result = parse("{ id }")
        assert str(result.loc) == "0:6"
        assert repr(result.loc) == "<Location 0:6>"
        assert inspect(result.loc) == repr(result.loc)

    def contains_references_to_source():
        source = Source("{ id }")
        result = parse(source)
        assert result.loc and result.loc.source is source

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
        result = parse("""# top comment
            {
              field # field comment
            }
            # bottom comment""")
        top_comment = result.loc and result.loc.start_token.next
        assert top_comment and top_comment.kind is TokenKind.COMMENT
        assert top_comment.value == " top comment"
        field_comment = top_comment.next.next.next  # type: ignore
        assert field_comment and field_comment.kind is TokenKind.COMMENT
        assert field_comment.value == " field comment"
        bottom_comment = field_comment.next.next  # type: ignore
        assert bottom_comment and bottom_comment.kind is TokenKind.COMMENT
        assert bottom_comment.value == " bottom comment"

    def describe_operation_and_variable_definition_descriptions():
        def parses_operation_with_description_and_variable_descriptions():
            source = (
                '"Operation description"\n'
                "query myQuery(\n"
                '  "Variable a description"\n'
                "  $a: Int,\n"
                '  """Variable b\nmultiline description"""\n'
                "  $b: String\n"
                ") {\n"
                "  field(a: $a, b: $b)\n"
                "}"
            )
            doc = parse(source)
            op_def = doc.definitions[0]
            assert isinstance(op_def, OperationDefinitionNode)
            assert op_def.operation == OperationType.QUERY
            assert op_def.loc == (0, 158)
            description = op_def.description
            assert isinstance(description, StringValueNode)
            assert description.value == "Operation description"
            assert description.block is False
            assert description.loc == (0, 23)
            name = op_def.name
            assert isinstance(name, NameNode)
            assert name.value == "myQuery"
            assert name.loc == (30, 37)
            var_defs = op_def.variable_definitions
            assert isinstance(var_defs, tuple)
            assert len(var_defs) == 2
            var_def = var_defs[0]
            assert isinstance(var_def, VariableDefinitionNode)
            assert var_def.loc == (41, 75)
            description = var_def.description
            assert isinstance(description, StringValueNode)
            assert description.value == "Variable a description"
            assert description.block is False
            assert description.loc == (41, 65)
            variable = var_def.variable
            assert isinstance(variable, VariableNode)
            assert variable.loc == (68, 70)
            assert variable.name.value == "a"
            assert variable.name.loc == (69, 70)
            type_ = var_def.type
            assert isinstance(type_, NamedTypeNode)
            assert type_.name.value == "Int"
            assert type_.loc == (72, 75)
            assert var_def.default_value is None
            assert var_def.directives == ()
            var_def = var_defs[1]
            assert isinstance(var_def, VariableDefinitionNode)
            assert var_def.loc == (79, 130)
            description = var_def.description
            assert isinstance(description, StringValueNode)
            assert description.value == "Variable b\nmultiline description"
            assert description.block is True
            assert description.loc == (79, 117)
            variable = var_def.variable
            assert isinstance(variable, VariableNode)
            assert variable.loc == (120, 122)
            assert variable.name.value == "b"
            assert variable.name.loc == (121, 122)
            type_ = var_def.type
            assert isinstance(type_, NamedTypeNode)
            assert type_.name.value == "String"
            assert type_.loc == (124, 130)
            assert var_def.default_value is None
            assert var_def.directives == ()
            assert op_def.directives == ()
            selection_set = op_def.selection_set
            assert isinstance(selection_set, SelectionSetNode)
            assert selection_set.loc == (133, 158)
            field = selection_set.selections[0]
            assert isinstance(field, FieldNode)
            assert field.name.value == "field"
            assert field.name.loc == (137, 142)
            assert field.loc == (137, 156)
            args = field.arguments
            assert isinstance(args, tuple)
            assert len(args) == 2
            assert args[0].name.value == "a"
            assert args[0].loc == (143, 148)
            assert args[1].name.value == "b"
            assert args[1].loc == (150, 155)

        def descriptions_on_a_short_hand_query_produce_a_sensible_error():
            with raises(GraphQLSyntaxError) as exc_info:
                parse('"""Invalid"""\n        { __typename }')
            assert exc_info.value.message == (
                "Syntax Error: Unexpected description,"
                " descriptions are not supported on shorthand queries."
            )

        def parses_variable_definition_with_description_default_and_directives():
            doc = parse(dedent("""
                query (
                  "desc"
                  $foo: Int = 42 @dir
                ) {
                  field(foo: $foo)
                }
                """))
            op_def = doc.definitions[0]
            assert isinstance(op_def, OperationDefinitionNode)
            var_def = op_def.variable_definitions[0]
            assert isinstance(var_def, VariableDefinitionNode)
            assert var_def.loc == (10, 38)
            default_value = var_def.default_value
            assert isinstance(default_value, IntValueNode)
            assert default_value.value == "42"
            assert default_value.loc == (31, 33)
            directives = var_def.directives
            assert isinstance(directives, tuple)
            assert len(directives) == 1
            directive = directives[0]
            assert directive.name.value == "dir"
            assert directive.name.loc == (35, 38)
            assert directive.arguments == ()
            assert directive.loc == (34, 38)
            description = var_def.description
            assert isinstance(description, StringValueNode)
            assert description.value == "desc"
            assert description.block is False
            assert description.loc == (10, 16)
            variable = var_def.variable
            assert isinstance(variable, VariableNode)
            assert variable.name.value == "foo"
            assert variable.name.loc == (20, 23)
            assert variable.loc == (19, 23)
            type_ = var_def.type
            assert isinstance(type_, NamedTypeNode)
            assert type_.name.value == "Int"
            assert type_.loc == (25, 28)

        def parses_fragment_with_variable_description_legacy():
            doc = parse(
                'fragment Foo("desc" $foo: Int) on Bar { baz }',
                allow_legacy_fragment_variables=True,
            )
            frag_def = doc.definitions[0]
            assert isinstance(frag_def, FragmentDefinitionNode)
            var_def = frag_def.variable_definitions[0]
            assert isinstance(var_def, VariableDefinitionNode)
            assert var_def.loc == (13, 29)
            description = var_def.description
            assert isinstance(description, StringValueNode)
            assert description.value == "desc"
            assert description.block is False
            assert description.loc == (13, 19)
            variable = var_def.variable
            assert isinstance(variable, VariableNode)
            assert variable.name.value == "foo"
            assert variable.name.loc == (21, 24)
            assert variable.loc == (20, 24)
            type_ = var_def.type
            assert isinstance(type_, NamedTypeNode)
            assert type_.name.value == "Int"
            assert type_.loc == (26, 29)
            assert var_def.default_value is None
            assert var_def.directives == ()


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
        with raises(GraphQLSyntaxError) as exc_info:
            parse_value("$")
        assert exc_info.value == {
            "message": "Syntax Error: Expected Name, found <EOF>.",
            "locations": [(1, 2)],
        }

    def correct_message_for_unexpected_token():
        with raises(GraphQLSyntaxError) as exc_info:
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
        with raises(GraphQLSyntaxError) as exc_info:
            parse_const_value("{ field: $var }")
        assert exc_info.value == {
            "message": "Syntax Error: Unexpected variable '$var' in constant value.",
            "locations": [(1, 10)],
        }

    def correct_message_for_unexpected_token():
        with raises(GraphQLSyntaxError) as exc_info:
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


def describe_parse_schema_coordinate():
    def parses_name():
        result = parse_schema_coordinate("MyType")
        assert isinstance(result, TypeCoordinateNode)
        assert result.loc == (0, 6)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 6)
        assert name.value == "MyType"

    def parses_name_dot_name():
        result = parse_schema_coordinate("MyType.field")
        assert isinstance(result, MemberCoordinateNode)
        assert result.loc == (0, 12)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 6)
        assert name.value == "MyType"
        member_name = result.member_name
        assert isinstance(member_name, NameNode)
        assert member_name.loc == (7, 12)
        assert member_name.value == "field"

    def rejects_name_dot_name_dot_name():
        with raises(GraphQLSyntaxError) as exc_info:
            parse_schema_coordinate("MyType.field.deep")
        assert exc_info.value == {
            "message": "Syntax Error: Expected <EOF>, found '.'.",
            "locations": [(1, 13)],
        }

    def parses_name_dot_name_argument():
        result = parse_schema_coordinate("MyType.field(arg:)")
        assert isinstance(result, ArgumentCoordinateNode)
        assert result.loc == (0, 18)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 6)
        assert name.value == "MyType"
        field_name = result.field_name
        assert isinstance(field_name, NameNode)
        assert field_name.loc == (7, 12)
        assert field_name.value == "field"
        argument_name = result.argument_name
        assert isinstance(argument_name, NameNode)
        assert argument_name.loc == (13, 16)
        assert argument_name.value == "arg"

    def rejects_name_dot_name_argument_with_value():
        with raises(GraphQLSyntaxError) as exc_info:
            parse_schema_coordinate("MyType.field(arg: value)")
        assert exc_info.value == {
            "message": "Syntax Error: Invalid character: ' '.",
            "locations": [(1, 18)],
        }

    def parses_directive():
        result = parse_schema_coordinate("@myDirective")
        assert isinstance(result, DirectiveCoordinateNode)
        assert result.loc == (0, 12)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (1, 12)
        assert name.value == "myDirective"

    def parses_directive_argument():
        result = parse_schema_coordinate("@myDirective(arg:)")
        assert isinstance(result, DirectiveArgumentCoordinateNode)
        assert result.loc == (0, 18)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (1, 12)
        assert name.value == "myDirective"
        argument_name = result.argument_name
        assert isinstance(argument_name, NameNode)
        assert argument_name.loc == (13, 16)
        assert argument_name.value == "arg"

    def parses_meta_type():
        result = parse_schema_coordinate("__Type")
        assert isinstance(result, TypeCoordinateNode)
        assert result.loc == (0, 6)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 6)
        assert name.value == "__Type"

    def parses_meta_field():
        result = parse_schema_coordinate("Type.__metafield")
        assert isinstance(result, MemberCoordinateNode)
        assert result.loc == (0, 16)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 4)
        assert name.value == "Type"
        member_name = result.member_name
        assert isinstance(member_name, NameNode)
        assert member_name.loc == (5, 16)
        assert member_name.value == "__metafield"

    def parses_meta_field_argument():
        result = parse_schema_coordinate("Type.__metafield(arg:)")
        assert isinstance(result, ArgumentCoordinateNode)
        assert result.loc == (0, 22)
        name = result.name
        assert isinstance(name, NameNode)
        assert name.loc == (0, 4)
        assert name.value == "Type"
        field_name = result.field_name
        assert isinstance(field_name, NameNode)
        assert field_name.loc == (5, 16)
        assert field_name.value == "__metafield"
        argument_name = result.argument_name
        assert isinstance(argument_name, NameNode)
        assert argument_name.loc == (17, 20)
        assert argument_name.value == "arg"

    def rejects_directive_dot_name():
        with raises(GraphQLSyntaxError) as exc_info:
            parse_schema_coordinate("@myDirective.field")
        assert exc_info.value == {
            "message": "Syntax Error: Expected <EOF>, found '.'.",
            "locations": [(1, 13)],
        }

    def accepts_a_source_object():
        assert parse_schema_coordinate("MyType") == parse_schema_coordinate(
            Source("MyType")
        )
