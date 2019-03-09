from typing import Any, Callable, Dict, List, NoReturn, Optional, Union, cast

from ..language import (
    DirectiveDefinitionNode,
    DirectiveLocation,
    DocumentNode,
    EnumTypeDefinitionNode,
    EnumValueDefinitionNode,
    FieldDefinitionNode,
    InputObjectTypeDefinitionNode,
    InputValueDefinitionNode,
    InterfaceTypeDefinitionNode,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    ObjectTypeDefinitionNode,
    OperationType,
    ScalarTypeDefinitionNode,
    SchemaDefinitionNode,
    Source,
    TypeDefinitionNode,
    TypeNode,
    UnionTypeDefinitionNode,
    parse,
    Node,
)
from ..type import (
    GraphQLArgument,
    GraphQLDeprecatedDirective,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFieldMap,
    GraphQLIncludeDirective,
    GraphQLInputType,
    GraphQLInputField,
    GraphQLInputFieldMap,
    GraphQLInputObjectType,
    GraphQLInterfaceList,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLNullableType,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLSkipDirective,
    GraphQLType,
    GraphQLTypeList,
    GraphQLUnionType,
    Thunk,
    introspection_types,
    specified_scalar_types,
)
from .value_from_ast import value_from_ast

TypeDefinitionsMap = Dict[str, TypeDefinitionNode]
TypeResolver = Callable[[str], GraphQLNamedType]

__all__ = [
    "build_ast_schema",
    "build_schema",
    "get_description",
    "ASTDefinitionBuilder",
]


def build_ast_schema(
    document_ast: DocumentNode,
    assume_valid: bool = False,
    assume_valid_sdl: bool = False,
) -> GraphQLSchema:
    """Build a GraphQL Schema from a given AST.

    This takes the ast of a schema document produced by the parse function in
    src/language/parser.py.

    If no schema definition is provided, then it will look for types named Query
    and Mutation.

    Given that AST it constructs a GraphQLSchema. The resulting schema has no
    resolve methods, so execution will use default resolvers.

    When building a schema from a GraphQL service's introspection result, it might
    be safe to assume the schema is valid. Set `assume_valid` to True to assume the
    produced schema is valid. Set `assume_valid_sdl` to True to assume it is already
    a valid SDL document.
    """
    if not isinstance(document_ast, DocumentNode):
        raise TypeError("Must provide a Document AST.")

    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl

        assert_valid_sdl(document_ast)

    schema_def: Optional[SchemaDefinitionNode] = None
    node_map: TypeDefinitionsMap = {}
    directive_defs: List[DirectiveDefinitionNode] = []
    append_directive_def = directive_defs.append
    for def_ in document_ast.definitions:
        if isinstance(def_, SchemaDefinitionNode):
            schema_def = def_
        elif isinstance(def_, TypeDefinitionNode):
            def_ = cast(TypeDefinitionNode, def_)
            node_map[def_.name.value] = def_
        elif isinstance(def_, DirectiveDefinitionNode):
            append_directive_def(def_)

    if schema_def:
        operation_types: Dict[OperationType, Any] = get_operation_types(schema_def)
    else:
        operation_types = {
            OperationType.QUERY: node_map.get("Query"),
            OperationType.MUTATION: node_map.get("Mutation"),
            OperationType.SUBSCRIPTION: node_map.get("Subscription"),
        }

    def resolve_type(type_name: str):
        raise TypeError(f"Type '{type_name}' not found in document.")

    definition_builder = ASTDefinitionBuilder(
        node_map, assume_valid=assume_valid, resolve_type=resolve_type
    )

    directives = [
        definition_builder.build_directive(directive_def)
        for directive_def in directive_defs
    ]

    # If specified directives were not explicitly declared, add them.
    if not any(directive.name == "skip" for directive in directives):
        directives.append(GraphQLSkipDirective)
    if not any(directive.name == "include" for directive in directives):
        directives.append(GraphQLIncludeDirective)
    if not any(directive.name == "deprecated" for directive in directives):
        directives.append(GraphQLDeprecatedDirective)

    # Note: While this could make early assertions to get the correctly typed values
    # below, that would throw immediately while type system validation with
    # `validate_schema()` will produce more actionable results.
    query_type = operation_types.get(OperationType.QUERY)
    mutation_type = operation_types.get(OperationType.MUTATION)
    subscription_type = operation_types.get(OperationType.SUBSCRIPTION)
    return GraphQLSchema(
        query=cast(GraphQLObjectType, definition_builder.build_type(query_type))
        if query_type
        else None,
        mutation=cast(GraphQLObjectType, definition_builder.build_type(mutation_type))
        if mutation_type
        else None,
        subscription=cast(
            GraphQLObjectType, definition_builder.build_type(subscription_type)
        )
        if subscription_type
        else None,
        types=[definition_builder.build_type(node) for node in node_map.values()],
        directives=directives,
        ast_node=schema_def,
        assume_valid=assume_valid,
    )


def get_operation_types(
    schema: SchemaDefinitionNode
) -> Dict[OperationType, NamedTypeNode]:
    op_types: Dict[OperationType, NamedTypeNode] = {}
    for operation_type in schema.operation_types:
        op_types[operation_type.operation] = operation_type.type
    return op_types


def default_type_resolver(type_name: str) -> NoReturn:
    """Type resolver that always throws an error."""
    raise TypeError(f"Type '{type_name}' not found in document.")


class ASTDefinitionBuilder:
    def __init__(
        self,
        type_definitions_map: TypeDefinitionsMap,
        assume_valid: bool = False,
        resolve_type: TypeResolver = default_type_resolver,
    ) -> None:
        self._type_definitions_map = type_definitions_map
        self._assume_valid = assume_valid
        self._resolve_type = resolve_type
        # Initialize to the GraphQL built in scalars and introspection types.
        self._cache: Dict[str, GraphQLNamedType] = {
            **specified_scalar_types,
            **introspection_types,
        }

    def build_type(
        self, node: Union[NamedTypeNode, TypeDefinitionNode]
    ) -> GraphQLNamedType:
        type_name = node.name.value
        cache = self._cache
        if type_name not in cache:
            if isinstance(node, NamedTypeNode):
                def_node = self._type_definitions_map.get(type_name)
                cache[type_name] = (
                    self._make_schema_def(def_node)
                    if def_node
                    else self._resolve_type(node.name.value)
                )
            else:
                cache[type_name] = self._make_schema_def(node)
        return cache[type_name]

    def _build_wrapped_type(self, type_node: TypeNode) -> GraphQLType:
        if isinstance(type_node, ListTypeNode):
            return GraphQLList(self._build_wrapped_type(type_node.type))
        if isinstance(type_node, NonNullTypeNode):
            return GraphQLNonNull(
                # Note: GraphQLNonNull constructor validates this type
                cast(GraphQLNullableType, self._build_wrapped_type(type_node.type))
            )
        return self.build_type(cast(NamedTypeNode, type_node))

    def build_directive(self, directive: DirectiveDefinitionNode) -> GraphQLDirective:
        locations = [DirectiveLocation[node.value] for node in directive.locations]

        return GraphQLDirective(
            name=directive.name.value,
            description=directive.description.value if directive.description else None,
            locations=locations,
            args={
                arg.name.value: self.build_arg(arg) for arg in directive.arguments or []
            },
            ast_node=directive,
        )

    def build_field(self, field: FieldDefinitionNode) -> GraphQLField:
        # Note: While this could make assertions to get the correctly typed value, that
        # would throw immediately while type system validation with `validate_schema()`
        # will produce more actionable results.
        type_ = self._build_wrapped_type(field.type)
        type_ = cast(GraphQLOutputType, type_)
        return GraphQLField(
            type_=type_,
            description=field.description.value if field.description else None,
            args={arg.name.value: self.build_arg(arg) for arg in field.arguments or []},
            deprecation_reason=get_deprecation_reason(field),
            ast_node=field,
        )

    def build_arg(self, value: InputValueDefinitionNode) -> GraphQLArgument:
        # Note: While this could make assertions to get the correctly typed value, that
        # would throw immediately while type system validation with `validate_schema()`
        # will produce more actionable results.
        type_ = self._build_wrapped_type(value.type)
        type_ = cast(GraphQLInputType, type_)
        return GraphQLArgument(
            type_=type_,
            description=value.description.value if value.description else None,
            default_value=value_from_ast(value.default_value, type_),
            ast_node=value,
        )

    def build_input_field(self, value: InputValueDefinitionNode) -> GraphQLInputField:
        # Note: While this could make assertions to get the correctly typed value, that
        # would throw immediately while type system validation with `validate_schema()`
        # will produce more actionable results.
        type_ = self._build_wrapped_type(value.type)
        type_ = cast(GraphQLInputType, type_)
        return GraphQLInputField(
            type_=type_,
            description=value.description.value if value.description else None,
            default_value=value_from_ast(value.default_value, type_),
            ast_node=value,
        )

    @staticmethod
    def build_enum_value(value: EnumValueDefinitionNode) -> GraphQLEnumValue:
        return GraphQLEnumValue(
            description=value.description.value if value.description else None,
            deprecation_reason=get_deprecation_reason(value),
            ast_node=value,
        )

    def _make_schema_def(self, ast_node: TypeDefinitionNode) -> GraphQLNamedType:
        method = {
            "object_type_definition": self._make_type_def,
            "interface_type_definition": self._make_interface_def,
            "enum_type_definition": self._make_enum_def,
            "union_type_definition": self._make_union_def,
            "scalar_type_definition": self._make_scalar_def,
            "input_object_type_definition": self._make_input_object_def,
        }.get(ast_node.kind)
        if not method:
            raise TypeError(f"Type kind '{ast_node.kind}' not supported.")
        return method(ast_node)  # type: ignore

    def _make_type_def(self, ast_node: ObjectTypeDefinitionNode) -> GraphQLObjectType:
        interface_nodes = ast_node.interfaces
        field_nodes = ast_node.fields

        # Note: While this could make early assertions to get the correctly typed
        # values, that would throw immediately while type system validation with
        # `validate_schema()` will produce more actionable results.
        interfaces = cast(
            Thunk[GraphQLInterfaceList],
            (
                (lambda: [self.build_type(ref) for ref in interface_nodes])
                if interface_nodes
                else []
            ),
        )

        fields = cast(
            Thunk[GraphQLFieldMap],
            (
                (
                    lambda: {
                        field.name.value: self.build_field(field)
                        for field in field_nodes
                    }
                )
                if field_nodes
                else {}
            ),
        )

        return GraphQLObjectType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            fields=fields,
            interfaces=interfaces,
            ast_node=ast_node,
        )

    def _make_interface_def(
        self, ast_node: InterfaceTypeDefinitionNode
    ) -> GraphQLInterfaceType:
        field_nodes = ast_node.fields

        fields = cast(
            Thunk[GraphQLFieldMap],
            (
                lambda: {
                    field.name.value: self.build_field(field) for field in field_nodes
                }
            )
            if field_nodes
            else {},
        )

        return GraphQLInterfaceType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            fields=fields,
            ast_node=ast_node,
        )

    def _make_enum_def(self, ast_node: EnumTypeDefinitionNode) -> GraphQLEnumType:
        value_nodes = ast_node.values or []

        return GraphQLEnumType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            values={
                value.name.value: self.build_enum_value(value) for value in value_nodes
            },
            ast_node=ast_node,
        )

    def _make_union_def(self, type_def: UnionTypeDefinitionNode) -> GraphQLUnionType:
        type_nodes = type_def.types

        # Note: While this could make assertions to get the correctly typed values
        # below, that would throw immediately while type system validation with
        # `validate_schema()` will get more actionable results.
        types = cast(
            Thunk[GraphQLTypeList],
            (lambda: [self.build_type(ref) for ref in type_nodes])
            if type_nodes
            else [],
        )

        return GraphQLUnionType(
            name=type_def.name.value,
            description=type_def.description.value if type_def.description else None,
            types=types,
            ast_node=type_def,
        )

    @staticmethod
    def _make_scalar_def(ast_node: ScalarTypeDefinitionNode) -> GraphQLScalarType:
        return GraphQLScalarType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            ast_node=ast_node,
            serialize=lambda value: value,
        )

    def _make_input_object_def(
        self, type_def: InputObjectTypeDefinitionNode
    ) -> GraphQLInputObjectType:
        field_nodes = type_def.fields

        fields = cast(
            Thunk[GraphQLInputFieldMap],
            (
                lambda: {
                    field.name.value: self.build_input_field(field)
                    for field in field_nodes
                }
            )
            if field_nodes
            else {},
        )

        return GraphQLInputObjectType(
            name=type_def.name.value,
            description=type_def.description.value if type_def.description else None,
            fields=fields,
            ast_node=type_def,
        )


def get_deprecation_reason(
    node: Union[EnumValueDefinitionNode, FieldDefinitionNode]
) -> Optional[str]:
    """Given a field or enum value node, get deprecation reason as string."""
    from ..execution import get_directive_values

    deprecated = get_directive_values(GraphQLDeprecatedDirective, node)
    return deprecated["reason"] if deprecated else None


def get_description(node: Node) -> Optional[str]:
    """@deprecated: Given an ast node, returns its string description."""
    try:
        # noinspection PyUnresolvedReferences
        return node.description.value  # type: ignore
    except AttributeError:
        return None


def build_schema(
    source: Union[str, Source],
    assume_valid=False,
    assume_valid_sdl=False,
    no_location=False,
    experimental_fragment_variables=False,
) -> GraphQLSchema:
    """Build a GraphQLSchema directly from a source document."""
    return build_ast_schema(
        parse(
            source,
            no_location=no_location,
            experimental_fragment_variables=experimental_fragment_variables,
        ),
        assume_valid=assume_valid,
        assume_valid_sdl=assume_valid_sdl,
    )
