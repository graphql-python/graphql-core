from typing import Callable, List, Optional, Union, cast, Dict
from functools import partial

from .ast import (
    ArgumentNode,
    BooleanValueNode,
    DefinitionNode,
    DirectiveDefinitionNode,
    DirectiveNode,
    DocumentNode,
    EnumTypeDefinitionNode,
    EnumTypeExtensionNode,
    EnumValueDefinitionNode,
    EnumValueNode,
    ExecutableDefinitionNode,
    FieldDefinitionNode,
    FieldNode,
    FloatValueNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    InputObjectTypeDefinitionNode,
    InputObjectTypeExtensionNode,
    InputValueDefinitionNode,
    IntValueNode,
    InterfaceTypeDefinitionNode,
    InterfaceTypeExtensionNode,
    ListTypeNode,
    ListValueNode,
    Location,
    NameNode,
    NamedTypeNode,
    Node,
    NonNullTypeNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectTypeDefinitionNode,
    ObjectTypeExtensionNode,
    ObjectValueNode,
    OperationDefinitionNode,
    OperationType,
    OperationTypeDefinitionNode,
    ScalarTypeDefinitionNode,
    ScalarTypeExtensionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    SelectionNode,
    SelectionSetNode,
    StringValueNode,
    TypeNode,
    TypeSystemDefinitionNode,
    TypeSystemExtensionNode,
    UnionTypeDefinitionNode,
    UnionTypeExtensionNode,
    ValueNode,
    VariableDefinitionNode,
    VariableNode,
)
from .directive_locations import DirectiveLocation
from .ast import Token
from .lexer import Lexer
from .source import Source
from .token_kind import TokenKind
from ..error import GraphQLError, GraphQLSyntaxError
from ..pyutils import inspect

__all__ = ["parse", "parse_type", "parse_value"]

SourceType = Union[Source, str]


def parse(
    source: SourceType, no_location=False, experimental_fragment_variables=False
) -> DocumentNode:
    """Given a GraphQL source, parse it into a Document.

    Throws GraphQLError if a syntax error is encountered.

    By default, the parser creates AST nodes that know the location in the source that
    they correspond to. The `no_location` option disables that behavior for performance
    or testing.

    Experimental features:

    If `experimental_fragment_variables` is set to True, the parser will understand
    and parse variable definitions contained in a fragment definition. They'll be
    represented in the `variable_definitions` field of the `FragmentDefinitionNode`.

    The syntax is identical to normal, query-defined variables. For example::

        fragment A($var: Boolean = false) on T  {
          ...
        }
    """
    if isinstance(source, str):
        source = Source(source)
    elif not isinstance(source, Source):
        raise TypeError(f"Must provide Source. Received: {inspect(source)}")
    lexer = Lexer(
        source,
        no_location=no_location,
        experimental_fragment_variables=experimental_fragment_variables,
    )
    return parse_document(lexer)


def parse_value(source: SourceType, **options: dict) -> ValueNode:
    """Parse the AST for a given string containing a GraphQL value.

    Throws GraphQLError if a syntax error is encountered.

    This is useful within tools that operate upon GraphQL Values directly and in
    isolation of complete GraphQL documents.

    Consider providing the results to the utility function: `value_from_ast()`.
    """
    if isinstance(source, str):
        source = Source(source)
    lexer = Lexer(source, **options)
    expect_token(lexer, TokenKind.SOF)
    value = parse_value_literal(lexer, False)
    expect_token(lexer, TokenKind.EOF)
    return value


def parse_type(source: SourceType, **options: dict) -> TypeNode:
    """Parse the AST for a given string containing a GraphQL Type.

    Throws GraphQLError if a syntax error is encountered.

    This is useful within tools that operate upon GraphQL Types directly and
    in isolation of complete GraphQL documents.

    Consider providing the results to the utility function: `type_from_ast()`.
    """
    if isinstance(source, str):
        source = Source(source)
    lexer = Lexer(source, **options)
    expect_token(lexer, TokenKind.SOF)
    type_ = parse_type_reference(lexer)
    expect_token(lexer, TokenKind.EOF)
    return type_


def parse_name(lexer: Lexer) -> NameNode:
    """Convert a name lex token into a name parse node."""
    token = expect_token(lexer, TokenKind.NAME)
    return NameNode(value=token.value, loc=loc(lexer, token))


# Implement the parsing rules in the Document section.


def parse_document(lexer: Lexer) -> DocumentNode:
    """Document: Definition+"""
    start = lexer.token
    return DocumentNode(
        definitions=many_nodes(lexer, TokenKind.SOF, parse_definition, TokenKind.EOF),
        loc=loc(lexer, start),
    )


def parse_definition(lexer: Lexer) -> DefinitionNode:
    """Definition: ExecutableDefinition or TypeSystemDefinition"""
    if peek(lexer, TokenKind.NAME):
        func = _parse_definition_functions.get(cast(str, lexer.token.value))
        if func:
            return func(lexer)
    elif peek(lexer, TokenKind.BRACE_L):
        return parse_executable_definition(lexer)
    elif peek_description(lexer):
        return parse_type_system_definition(lexer)
    raise unexpected(lexer)


def parse_executable_definition(lexer: Lexer) -> ExecutableDefinitionNode:
    """ExecutableDefinition: OperationDefinition or FragmentDefinition"""
    if peek(lexer, TokenKind.NAME):
        func = _parse_executable_definition_functions.get(cast(str, lexer.token.value))
        if func:
            return func(lexer)
    elif peek(lexer, TokenKind.BRACE_L):
        return parse_operation_definition(lexer)
    raise unexpected(lexer)


# Implement the parsing rules in the Operations section.


def parse_operation_definition(lexer: Lexer) -> OperationDefinitionNode:
    """OperationDefinition"""
    start = lexer.token
    if peek(lexer, TokenKind.BRACE_L):
        return OperationDefinitionNode(
            operation=OperationType.QUERY,
            name=None,
            variable_definitions=[],
            directives=[],
            selection_set=parse_selection_set(lexer),
            loc=loc(lexer, start),
        )
    operation = parse_operation_type(lexer)
    name = parse_name(lexer) if peek(lexer, TokenKind.NAME) else None
    return OperationDefinitionNode(
        operation=operation,
        name=name,
        variable_definitions=parse_variable_definitions(lexer),
        directives=parse_directives(lexer, False),
        selection_set=parse_selection_set(lexer),
        loc=loc(lexer, start),
    )


def parse_operation_type(lexer: Lexer) -> OperationType:
    """OperationType: one of query mutation subscription"""
    operation_token = expect_token(lexer, TokenKind.NAME)
    try:
        return OperationType(operation_token.value)
    except ValueError:
        raise unexpected(lexer, operation_token)


def parse_variable_definitions(lexer: Lexer) -> List[VariableDefinitionNode]:
    """VariableDefinitions: (VariableDefinition+)"""
    return (
        cast(
            List[VariableDefinitionNode],
            many_nodes(
                lexer, TokenKind.PAREN_L, parse_variable_definition, TokenKind.PAREN_R
            ),
        )
        if peek(lexer, TokenKind.PAREN_L)
        else []
    )


def parse_variable_definition(lexer: Lexer) -> VariableDefinitionNode:
    """VariableDefinition: Variable: Type DefaultValue? Directives[Const]?"""
    start = lexer.token
    return VariableDefinitionNode(
        variable=parse_variable(lexer),
        type=expect_token(lexer, TokenKind.COLON) and parse_type_reference(lexer),
        default_value=parse_value_literal(lexer, True)
        if expect_optional_token(lexer, TokenKind.EQUALS)
        else None,
        directives=parse_directives(lexer, True),
        loc=loc(lexer, start),
    )


def parse_variable(lexer: Lexer) -> VariableNode:
    """Variable: $Name"""
    start = lexer.token
    expect_token(lexer, TokenKind.DOLLAR)
    return VariableNode(name=parse_name(lexer), loc=loc(lexer, start))


def parse_selection_set(lexer: Lexer) -> SelectionSetNode:
    """SelectionSet: {Selection+}"""
    start = lexer.token
    return SelectionSetNode(
        selections=many_nodes(
            lexer, TokenKind.BRACE_L, parse_selection, TokenKind.BRACE_R
        ),
        loc=loc(lexer, start),
    )


def parse_selection(lexer: Lexer) -> SelectionNode:
    """Selection: Field or FragmentSpread or InlineFragment"""
    return (parse_fragment if peek(lexer, TokenKind.SPREAD) else parse_field)(lexer)


def parse_field(lexer: Lexer) -> FieldNode:
    """Field: Alias? Name Arguments? Directives? SelectionSet?"""
    start = lexer.token
    name_or_alias = parse_name(lexer)
    if expect_optional_token(lexer, TokenKind.COLON):
        alias: Optional[NameNode] = name_or_alias
        name = parse_name(lexer)
    else:
        alias = None
        name = name_or_alias
    return FieldNode(
        alias=alias,
        name=name,
        arguments=parse_arguments(lexer, False),
        directives=parse_directives(lexer, False),
        selection_set=parse_selection_set(lexer)
        if peek(lexer, TokenKind.BRACE_L)
        else None,
        loc=loc(lexer, start),
    )


def parse_arguments(lexer: Lexer, is_const: bool) -> List[ArgumentNode]:
    """Arguments[Const]: (Argument[?Const]+)"""
    item = parse_const_argument if is_const else parse_argument
    return (
        cast(
            List[ArgumentNode],
            many_nodes(lexer, TokenKind.PAREN_L, item, TokenKind.PAREN_R),
        )
        if peek(lexer, TokenKind.PAREN_L)
        else []
    )


def parse_argument(lexer: Lexer) -> ArgumentNode:
    """Argument: Name : Value"""
    start = lexer.token
    name = parse_name(lexer)

    expect_token(lexer, TokenKind.COLON)
    return ArgumentNode(
        name=name, value=parse_value_literal(lexer, False), loc=loc(lexer, start)
    )


def parse_const_argument(lexer: Lexer) -> ArgumentNode:
    """Argument[Const]: Name : Value[?Const]"""
    start = lexer.token
    return ArgumentNode(
        name=parse_name(lexer),
        value=expect_token(lexer, TokenKind.COLON) and parse_const_value(lexer),
        loc=loc(lexer, start),
    )


# Implement the parsing rules in the Fragments section.


def parse_fragment(lexer: Lexer) -> Union[FragmentSpreadNode, InlineFragmentNode]:
    """Corresponds to both FragmentSpread and InlineFragment in the spec.

    FragmentSpread: ... FragmentName Directives?
    InlineFragment: ... TypeCondition? Directives? SelectionSet
    """
    start = lexer.token
    expect_token(lexer, TokenKind.SPREAD)

    has_type_condition = expect_optional_keyword(lexer, "on")
    if not has_type_condition and peek(lexer, TokenKind.NAME):
        return FragmentSpreadNode(
            name=parse_fragment_name(lexer),
            directives=parse_directives(lexer, False),
            loc=loc(lexer, start),
        )
    return InlineFragmentNode(
        type_condition=parse_named_type(lexer) if has_type_condition else None,
        directives=parse_directives(lexer, False),
        selection_set=parse_selection_set(lexer),
        loc=loc(lexer, start),
    )


def parse_fragment_definition(lexer: Lexer) -> FragmentDefinitionNode:
    """FragmentDefinition"""
    start = lexer.token
    expect_keyword(lexer, "fragment")
    # Experimental support for defining variables within fragments changes the grammar
    # of FragmentDefinition
    if lexer.experimental_fragment_variables:
        return FragmentDefinitionNode(
            name=parse_fragment_name(lexer),
            variable_definitions=parse_variable_definitions(lexer),
            type_condition=parse_type_condition(lexer),
            directives=parse_directives(lexer, False),
            selection_set=parse_selection_set(lexer),
            loc=loc(lexer, start),
        )
    return FragmentDefinitionNode(
        name=parse_fragment_name(lexer),
        type_condition=parse_type_condition(lexer),
        directives=parse_directives(lexer, False),
        selection_set=parse_selection_set(lexer),
        loc=loc(lexer, start),
    )


_parse_executable_definition_functions: Dict[str, Callable] = {
    **dict.fromkeys(("query", "mutation", "subscription"), parse_operation_definition),
    **dict.fromkeys(("fragment",), parse_fragment_definition),
}


def parse_fragment_name(lexer: Lexer) -> NameNode:
    """FragmentName: Name but not `on`"""
    if lexer.token.value == "on":
        raise unexpected(lexer)
    return parse_name(lexer)


def parse_type_condition(lexer: Lexer) -> NamedTypeNode:
    """TypeCondition: NamedType"""
    expect_keyword(lexer, "on")
    return parse_named_type(lexer)


# Implement the parsing rules in the Values section.


def parse_value_literal(lexer: Lexer, is_const: bool) -> ValueNode:
    func = _parse_value_literal_functions.get(lexer.token.kind)
    if func:
        return func(lexer, is_const)  # type: ignore
    raise unexpected(lexer)


def parse_string_literal(lexer: Lexer, _is_const=True) -> StringValueNode:
    token = lexer.token
    lexer.advance()
    return StringValueNode(
        value=token.value,
        block=token.kind == TokenKind.BLOCK_STRING,
        loc=loc(lexer, token),
    )


def parse_const_value(lexer: Lexer) -> ValueNode:
    return parse_value_literal(lexer, True)


def parse_value_value(lexer: Lexer) -> ValueNode:
    return parse_value_literal(lexer, False)


def parse_list(lexer: Lexer, is_const: bool) -> ListValueNode:
    """ListValue[Const]"""
    start = lexer.token
    item = parse_const_value if is_const else parse_value_value
    return ListValueNode(
        values=any_nodes(lexer, TokenKind.BRACKET_L, item, TokenKind.BRACKET_R),
        loc=loc(lexer, start),
    )


def parse_object_field(lexer: Lexer, is_const: bool) -> ObjectFieldNode:
    start = lexer.token
    name = parse_name(lexer)
    expect_token(lexer, TokenKind.COLON)

    return ObjectFieldNode(
        name=name, value=parse_value_literal(lexer, is_const), loc=loc(lexer, start)
    )


def parse_object(lexer: Lexer, is_const: bool) -> ObjectValueNode:
    """ObjectValue[Const]"""
    start = lexer.token
    item = cast(Callable[[Lexer], Node], partial(parse_object_field, is_const=is_const))
    return ObjectValueNode(
        fields=any_nodes(lexer, TokenKind.BRACE_L, item, TokenKind.BRACE_R),
        loc=loc(lexer, start),
    )


def parse_int(lexer: Lexer, _is_const=True) -> IntValueNode:
    token = lexer.token
    lexer.advance()
    return IntValueNode(value=token.value, loc=loc(lexer, token))


def parse_float(lexer: Lexer, _is_const=True) -> FloatValueNode:
    token = lexer.token
    lexer.advance()
    return FloatValueNode(value=token.value, loc=loc(lexer, token))


def parse_named_values(lexer: Lexer, _is_const=True) -> ValueNode:
    token = lexer.token
    value = token.value
    lexer.advance()
    if value in ("true", "false"):
        return BooleanValueNode(value=value == "true", loc=loc(lexer, token))
    elif value == "null":
        return NullValueNode(loc=loc(lexer, token))
    else:
        return EnumValueNode(value=value, loc=loc(lexer, token))


def parse_variable_value(lexer: Lexer, is_const) -> VariableNode:
    if not is_const:
        return parse_variable(lexer)
    raise unexpected(lexer)


_parse_value_literal_functions = {
    TokenKind.BRACKET_L: parse_list,
    TokenKind.BRACE_L: parse_object,
    TokenKind.INT: parse_int,
    TokenKind.FLOAT: parse_float,
    TokenKind.STRING: parse_string_literal,
    TokenKind.BLOCK_STRING: parse_string_literal,
    TokenKind.NAME: parse_named_values,
    TokenKind.DOLLAR: parse_variable_value,
}


# Implement the parsing rules in the Directives section.


def parse_directives(lexer: Lexer, is_const: bool) -> List[DirectiveNode]:
    """Directives[Const]: Directive[?Const]+"""
    directives: List[DirectiveNode] = []
    append = directives.append
    while peek(lexer, TokenKind.AT):
        append(parse_directive(lexer, is_const))
    return directives


def parse_directive(lexer: Lexer, is_const: bool) -> DirectiveNode:
    """Directive[Const]: @ Name Arguments[?Const]?"""
    start = lexer.token
    expect_token(lexer, TokenKind.AT)
    return DirectiveNode(
        name=parse_name(lexer),
        arguments=parse_arguments(lexer, is_const),
        loc=loc(lexer, start),
    )


# Implement the parsing rules in the Types section.


def parse_type_reference(lexer: Lexer) -> TypeNode:
    """Type: NamedType or ListType or NonNullType"""
    start = lexer.token
    if expect_optional_token(lexer, TokenKind.BRACKET_L):
        type_ = parse_type_reference(lexer)
        expect_token(lexer, TokenKind.BRACKET_R)
        type_ = ListTypeNode(type=type_, loc=loc(lexer, start))
    else:
        type_ = parse_named_type(lexer)
    if expect_optional_token(lexer, TokenKind.BANG):
        return NonNullTypeNode(type=type_, loc=loc(lexer, start))
    return type_


def parse_named_type(lexer: Lexer) -> NamedTypeNode:
    """NamedType: Name"""
    start = lexer.token
    return NamedTypeNode(name=parse_name(lexer), loc=loc(lexer, start))


# Implement the parsing rules in the Type Definition section.


def parse_type_system_definition(lexer: Lexer) -> TypeSystemDefinitionNode:
    """TypeSystemDefinition"""
    # Many definitions begin with a description and require a lookahead.
    keyword_token = lexer.lookahead() if peek_description(lexer) else lexer.token
    func = _parse_type_system_definition_functions.get(cast(str, keyword_token.value))
    if func:
        return func(lexer)
    raise unexpected(lexer, keyword_token)


def parse_type_system_extension(lexer: Lexer) -> TypeSystemExtensionNode:
    """TypeSystemExtension"""
    keyword_token = lexer.lookahead()
    if keyword_token.kind == TokenKind.NAME:
        func = _parse_type_extension_functions.get(cast(str, keyword_token.value))
        if func:
            return func(lexer)
    raise unexpected(lexer, keyword_token)


_parse_definition_functions: Dict[str, Callable] = {
    **dict.fromkeys(
        ("query", "mutation", "subscription", "fragment"), parse_executable_definition
    ),
    **dict.fromkeys(
        (
            "schema",
            "scalar",
            "type",
            "interface",
            "union",
            "enum",
            "input",
            "directive",
        ),
        parse_type_system_definition,
    ),
    "extend": parse_type_system_extension,
}


def peek_description(lexer: Lexer) -> bool:
    return peek(lexer, TokenKind.STRING) or peek(lexer, TokenKind.BLOCK_STRING)


def parse_description(lexer: Lexer) -> Optional[StringValueNode]:
    """Description: StringValue"""
    if peek_description(lexer):
        return parse_string_literal(lexer)
    return None


def parse_schema_definition(lexer: Lexer) -> SchemaDefinitionNode:
    """SchemaDefinition"""
    start = lexer.token
    expect_keyword(lexer, "schema")
    directives = parse_directives(lexer, True)
    operation_types = many_nodes(
        lexer, TokenKind.BRACE_L, parse_operation_type_definition, TokenKind.BRACE_R
    )
    return SchemaDefinitionNode(
        directives=directives, operation_types=operation_types, loc=loc(lexer, start)
    )


def parse_operation_type_definition(lexer: Lexer) -> OperationTypeDefinitionNode:
    """OperationTypeDefinition: OperationType : NamedType"""
    start = lexer.token
    operation = parse_operation_type(lexer)
    expect_token(lexer, TokenKind.COLON)
    type_ = parse_named_type(lexer)
    return OperationTypeDefinitionNode(
        operation=operation, type=type_, loc=loc(lexer, start)
    )


def parse_scalar_type_definition(lexer: Lexer) -> ScalarTypeDefinitionNode:
    """ScalarTypeDefinition: Description? scalar Name Directives[Const]?"""
    start = lexer.token
    description = parse_description(lexer)
    expect_keyword(lexer, "scalar")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    return ScalarTypeDefinitionNode(
        description=description, name=name, directives=directives, loc=loc(lexer, start)
    )


def parse_object_type_definition(lexer: Lexer) -> ObjectTypeDefinitionNode:
    """ObjectTypeDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    expect_keyword(lexer, "type")
    name = parse_name(lexer)
    interfaces = parse_implements_interfaces(lexer)
    directives = parse_directives(lexer, True)
    fields = parse_fields_definition(lexer)
    return ObjectTypeDefinitionNode(
        description=description,
        name=name,
        interfaces=interfaces,
        directives=directives,
        fields=fields,
        loc=loc(lexer, start),
    )


def parse_implements_interfaces(lexer: Lexer) -> List[NamedTypeNode]:
    """ImplementsInterfaces"""
    types: List[NamedTypeNode] = []
    if expect_optional_keyword(lexer, "implements"):
        # optional leading ampersand
        expect_optional_token(lexer, TokenKind.AMP)
        append = types.append
        while True:
            append(parse_named_type(lexer))
            if not expect_optional_token(lexer, TokenKind.AMP):
                break
    return types


def parse_fields_definition(lexer: Lexer) -> List[FieldDefinitionNode]:
    """FieldsDefinition: {FieldDefinition+}"""
    return (
        cast(
            List[FieldDefinitionNode],
            many_nodes(
                lexer, TokenKind.BRACE_L, parse_field_definition, TokenKind.BRACE_R
            ),
        )
        if peek(lexer, TokenKind.BRACE_L)
        else []
    )


def parse_field_definition(lexer: Lexer) -> FieldDefinitionNode:
    """FieldDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    name = parse_name(lexer)
    args = parse_argument_defs(lexer)
    expect_token(lexer, TokenKind.COLON)
    type_ = parse_type_reference(lexer)
    directives = parse_directives(lexer, True)
    return FieldDefinitionNode(
        description=description,
        name=name,
        arguments=args,
        type=type_,
        directives=directives,
        loc=loc(lexer, start),
    )


def parse_argument_defs(lexer: Lexer) -> List[InputValueDefinitionNode]:
    """ArgumentsDefinition: (InputValueDefinition+)"""
    return (
        cast(
            List[InputValueDefinitionNode],
            many_nodes(
                lexer, TokenKind.PAREN_L, parse_input_value_def, TokenKind.PAREN_R
            ),
        )
        if peek(lexer, TokenKind.PAREN_L)
        else []
    )


def parse_input_value_def(lexer: Lexer) -> InputValueDefinitionNode:
    """InputValueDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    name = parse_name(lexer)
    expect_token(lexer, TokenKind.COLON)
    type_ = parse_type_reference(lexer)
    default_value = (
        parse_const_value(lexer)
        if expect_optional_token(lexer, TokenKind.EQUALS)
        else None
    )
    directives = parse_directives(lexer, True)
    return InputValueDefinitionNode(
        description=description,
        name=name,
        type=type_,
        default_value=default_value,
        directives=directives,
        loc=loc(lexer, start),
    )


def parse_interface_type_definition(lexer: Lexer) -> InterfaceTypeDefinitionNode:
    """InterfaceTypeDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    expect_keyword(lexer, "interface")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    fields = parse_fields_definition(lexer)
    return InterfaceTypeDefinitionNode(
        description=description,
        name=name,
        directives=directives,
        fields=fields,
        loc=loc(lexer, start),
    )


def parse_union_type_definition(lexer: Lexer) -> UnionTypeDefinitionNode:
    """UnionTypeDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    expect_keyword(lexer, "union")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    types = parse_union_member_types(lexer)
    return UnionTypeDefinitionNode(
        description=description,
        name=name,
        directives=directives,
        types=types,
        loc=loc(lexer, start),
    )


def parse_union_member_types(lexer: Lexer) -> List[NamedTypeNode]:
    """UnionMemberTypes"""
    types: List[NamedTypeNode] = []
    if expect_optional_token(lexer, TokenKind.EQUALS):
        # optional leading pipe
        expect_optional_token(lexer, TokenKind.PIPE)
        append = types.append
        while True:
            append(parse_named_type(lexer))
            if not expect_optional_token(lexer, TokenKind.PIPE):
                break
    return types


def parse_enum_type_definition(lexer: Lexer) -> EnumTypeDefinitionNode:
    """UnionTypeDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    expect_keyword(lexer, "enum")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    values = parse_enum_values_definition(lexer)
    return EnumTypeDefinitionNode(
        description=description,
        name=name,
        directives=directives,
        values=values,
        loc=loc(lexer, start),
    )


def parse_enum_values_definition(lexer: Lexer) -> List[EnumValueDefinitionNode]:
    """EnumValuesDefinition: {EnumValueDefinition+}"""
    return (
        cast(
            List[EnumValueDefinitionNode],
            many_nodes(
                lexer, TokenKind.BRACE_L, parse_enum_value_definition, TokenKind.BRACE_R
            ),
        )
        if peek(lexer, TokenKind.BRACE_L)
        else []
    )


def parse_enum_value_definition(lexer: Lexer) -> EnumValueDefinitionNode:
    """EnumValueDefinition: Description? EnumValue Directives[Const]?"""
    start = lexer.token
    description = parse_description(lexer)
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    return EnumValueDefinitionNode(
        description=description, name=name, directives=directives, loc=loc(lexer, start)
    )


def parse_input_object_type_definition(lexer: Lexer) -> InputObjectTypeDefinitionNode:
    """InputObjectTypeDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    expect_keyword(lexer, "input")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    fields = parse_input_fields_definition(lexer)
    return InputObjectTypeDefinitionNode(
        description=description,
        name=name,
        directives=directives,
        fields=fields,
        loc=loc(lexer, start),
    )


def parse_input_fields_definition(lexer: Lexer) -> List[InputValueDefinitionNode]:
    """InputFieldsDefinition: {InputValueDefinition+}"""
    return (
        cast(
            List[InputValueDefinitionNode],
            many_nodes(
                lexer, TokenKind.BRACE_L, parse_input_value_def, TokenKind.BRACE_R
            ),
        )
        if peek(lexer, TokenKind.BRACE_L)
        else []
    )


def parse_schema_extension(lexer: Lexer) -> SchemaExtensionNode:
    """SchemaExtension"""
    start = lexer.token
    expect_keyword(lexer, "extend")
    expect_keyword(lexer, "schema")
    directives = parse_directives(lexer, True)
    operation_types = (
        many_nodes(
            lexer, TokenKind.BRACE_L, parse_operation_type_definition, TokenKind.BRACE_R
        )
        if peek(lexer, TokenKind.BRACE_L)
        else []
    )
    if not directives and not operation_types:
        raise unexpected(lexer)
    return SchemaExtensionNode(
        directives=directives, operation_types=operation_types, loc=loc(lexer, start)
    )


def parse_scalar_type_extension(lexer: Lexer) -> ScalarTypeExtensionNode:
    """ScalarTypeExtension"""
    start = lexer.token
    expect_keyword(lexer, "extend")
    expect_keyword(lexer, "scalar")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    if not directives:
        raise unexpected(lexer)
    return ScalarTypeExtensionNode(
        name=name, directives=directives, loc=loc(lexer, start)
    )


def parse_object_type_extension(lexer: Lexer) -> ObjectTypeExtensionNode:
    """ObjectTypeExtension"""
    start = lexer.token
    expect_keyword(lexer, "extend")
    expect_keyword(lexer, "type")
    name = parse_name(lexer)
    interfaces = parse_implements_interfaces(lexer)
    directives = parse_directives(lexer, True)
    fields = parse_fields_definition(lexer)
    if not (interfaces or directives or fields):
        raise unexpected(lexer)
    return ObjectTypeExtensionNode(
        name=name,
        interfaces=interfaces,
        directives=directives,
        fields=fields,
        loc=loc(lexer, start),
    )


def parse_interface_type_extension(lexer: Lexer) -> InterfaceTypeExtensionNode:
    """InterfaceTypeExtension"""
    start = lexer.token
    expect_keyword(lexer, "extend")
    expect_keyword(lexer, "interface")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    fields = parse_fields_definition(lexer)
    if not (directives or fields):
        raise unexpected(lexer)
    return InterfaceTypeExtensionNode(
        name=name, directives=directives, fields=fields, loc=loc(lexer, start)
    )


def parse_union_type_extension(lexer: Lexer) -> UnionTypeExtensionNode:
    """UnionTypeExtension"""
    start = lexer.token
    expect_keyword(lexer, "extend")
    expect_keyword(lexer, "union")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    types = parse_union_member_types(lexer)
    if not (directives or types):
        raise unexpected(lexer)
    return UnionTypeExtensionNode(
        name=name, directives=directives, types=types, loc=loc(lexer, start)
    )


def parse_enum_type_extension(lexer: Lexer) -> EnumTypeExtensionNode:
    """EnumTypeExtension"""
    start = lexer.token
    expect_keyword(lexer, "extend")
    expect_keyword(lexer, "enum")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    values = parse_enum_values_definition(lexer)
    if not (directives or values):
        raise unexpected(lexer)
    return EnumTypeExtensionNode(
        name=name, directives=directives, values=values, loc=loc(lexer, start)
    )


def parse_input_object_type_extension(lexer: Lexer) -> InputObjectTypeExtensionNode:
    """InputObjectTypeExtension"""
    start = lexer.token
    expect_keyword(lexer, "extend")
    expect_keyword(lexer, "input")
    name = parse_name(lexer)
    directives = parse_directives(lexer, True)
    fields = parse_input_fields_definition(lexer)
    if not (directives or fields):
        raise unexpected(lexer)
    return InputObjectTypeExtensionNode(
        name=name, directives=directives, fields=fields, loc=loc(lexer, start)
    )


_parse_type_extension_functions: Dict[
    str, Callable[[Lexer], TypeSystemExtensionNode]
] = {
    "schema": parse_schema_extension,
    "scalar": parse_scalar_type_extension,
    "type": parse_object_type_extension,
    "interface": parse_interface_type_extension,
    "union": parse_union_type_extension,
    "enum": parse_enum_type_extension,
    "input": parse_input_object_type_extension,
}


def parse_directive_definition(lexer: Lexer) -> DirectiveDefinitionNode:
    """DirectiveDefinition"""
    start = lexer.token
    description = parse_description(lexer)
    expect_keyword(lexer, "directive")
    expect_token(lexer, TokenKind.AT)
    name = parse_name(lexer)
    args = parse_argument_defs(lexer)
    repeatable = expect_optional_keyword(lexer, "repeatable")
    expect_keyword(lexer, "on")
    locations = parse_directive_locations(lexer)
    return DirectiveDefinitionNode(
        description=description,
        name=name,
        arguments=args,
        repeatable=repeatable,
        locations=locations,
        loc=loc(lexer, start),
    )


_parse_type_system_definition_functions = {
    "schema": parse_schema_definition,
    "scalar": parse_scalar_type_definition,
    "type": parse_object_type_definition,
    "interface": parse_interface_type_definition,
    "union": parse_union_type_definition,
    "enum": parse_enum_type_definition,
    "input": parse_input_object_type_definition,
    "directive": parse_directive_definition,
}


def parse_directive_locations(lexer: Lexer) -> List[NameNode]:
    """DirectiveLocations"""
    # optional leading pipe
    expect_optional_token(lexer, TokenKind.PIPE)
    locations: List[NameNode] = []
    append = locations.append
    while True:
        append(parse_directive_location(lexer))
        if not expect_optional_token(lexer, TokenKind.PIPE):
            break
    return locations


def parse_directive_location(lexer: Lexer) -> NameNode:
    """DirectiveLocation"""
    start = lexer.token
    name = parse_name(lexer)
    if name.value in DirectiveLocation.__members__:
        return name
    raise unexpected(lexer, start)


# Core parsing utility functions


def loc(lexer: Lexer, start_token: Token) -> Optional[Location]:
    """Return a location object.

    Used to identify the place in the source that created a given parsed object.
    """
    if not lexer.no_location:
        end_token = lexer.last_token
        source = lexer.source
        return Location(
            start_token.start, end_token.end, start_token, end_token, source
        )
    return None


def peek(lexer: Lexer, kind: TokenKind):
    """Determine if the next token is of a given kind"""
    return lexer.token.kind == kind


def expect_token(lexer: Lexer, kind: TokenKind) -> Token:
    """Expect the next token to be of the given kind.

    If the next token is of the given kind, return that token after advancing the lexer.
    Otherwise, do not change the parser state and throw an error.
    """
    token = lexer.token
    if token.kind == kind:
        lexer.advance()
        return token

    raise GraphQLSyntaxError(
        lexer.source, token.start, f"Expected {kind.value}, found {token.kind.value}"
    )


def expect_optional_token(lexer: Lexer, kind: TokenKind) -> Optional[Token]:
    """Expect the next token optionally to be of the given kind.

    If the next token is of the given kind, return that token after advancing the lexer.
    Otherwise, do not change the parser state and return None.
    """
    token = lexer.token
    if token.kind == kind:
        lexer.advance()
        return token

    return None


def expect_keyword(lexer: Lexer, value: str) -> None:
    """Expect the next token to be a given keyword.

    If the next token is a given keyword, advance the lexer.
    Otherwise, do not change the parser state and throw an error.
    """
    token = lexer.token
    if token.kind == TokenKind.NAME and token.value == value:
        lexer.advance()
    else:
        raise GraphQLSyntaxError(
            lexer.source, token.start, f"Expected {value!r}, found {token.desc}"
        )


def expect_optional_keyword(lexer: Lexer, value: str) -> bool:
    """Expect the next token optionally to be a given keyword.

    If the next token is a given keyword, return True after advancing the lexer.
    Otherwise, do not change the parser state and return False.
    """
    token = lexer.token
    if token.kind == TokenKind.NAME and token.value == value:
        lexer.advance()
        return True

    return False


def unexpected(lexer: Lexer, at_token: Token = None) -> GraphQLError:
    """Create an error when an unexpected lexed token is encountered."""
    token = at_token or lexer.token
    return GraphQLSyntaxError(lexer.source, token.start, f"Unexpected {token.desc}")


def any_nodes(
    lexer: Lexer,
    open_kind: TokenKind,
    parse_fn: Callable[[Lexer], Node],
    close_kind: TokenKind,
) -> List[Node]:
    """Fetch any matching nodes, possibly none.

    Returns a possibly empty list of parse nodes, determined by the `parse_fn`.
    This list begins with a lex token of `open_kind` and ends with a lex token of
    `close_kind`. Advances the parser to the next lex token after the closing token.
    """
    expect_token(lexer, open_kind)
    nodes: List[Node] = []
    append = nodes.append
    while not expect_optional_token(lexer, close_kind):
        append(parse_fn(lexer))
    return nodes


def many_nodes(
    lexer: Lexer,
    open_kind: TokenKind,
    parse_fn: Callable[[Lexer], Node],
    close_kind: TokenKind,
) -> List[Node]:
    """Fetch matching nodes, at least one.

    Returns a non-empty list of parse nodes, determined by the `parse_fn`.
    This list begins with a lex token of `open_kind` and ends with a lex token of
    `close_kind`. Advances the parser to the next lex token after the closing token.
    """
    expect_token(lexer, open_kind)
    nodes = [parse_fn(lexer)]
    append = nodes.append
    while not expect_optional_token(lexer, close_kind):
        append(parse_fn(lexer))
    return nodes
