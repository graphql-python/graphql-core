from collections import defaultdict
from typing import (
    Callable,
    Collection,
    DefaultDict,
    Dict,
    List,
    NoReturn,
    Optional,
    Union,
    cast,
)

from ..language import (
    DirectiveDefinitionNode,
    DirectiveLocation,
    DocumentNode,
    EnumTypeDefinitionNode,
    EnumTypeExtensionNode,
    EnumValueDefinitionNode,
    FieldDefinitionNode,
    InputObjectTypeDefinitionNode,
    InputObjectTypeExtensionNode,
    InputValueDefinitionNode,
    InterfaceTypeDefinitionNode,
    InterfaceTypeExtensionNode,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    ObjectTypeDefinitionNode,
    ObjectTypeExtensionNode,
    OperationType,
    ScalarTypeDefinitionNode,
    ScalarTypeExtensionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    Source,
    TypeDefinitionNode,
    TypeExtensionNode,
    TypeNode,
    UnionTypeDefinitionNode,
    UnionTypeExtensionNode,
    parse,
    Node,
)
from ..pyutils import inspect
from ..type import (
    GraphQLArgument,
    GraphQLArgumentMap,
    GraphQLDeprecatedDirective,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLEnumValueMap,
    GraphQLField,
    GraphQLFieldMap,
    GraphQLIncludeDirective,
    GraphQLInputType,
    GraphQLInputField,
    GraphQLInputFieldMap,
    GraphQLInputObjectType,
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
    GraphQLUnionType,
    introspection_types,
    specified_scalar_types,
)
from .value_from_ast import value_from_ast

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
        raise TypeError("Must provide valid Document AST.")

    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl

        assert_valid_sdl(document_ast)

    # Collect the definitions and extensions found in the document.
    schema_def: Optional[SchemaDefinitionNode] = None
    schema_extensions: List[SchemaExtensionNode] = []
    type_defs: List[TypeDefinitionNode] = []
    type_extensions_map: DefaultDict[str, List[TypeExtensionNode]] = defaultdict(list)
    directive_defs: List[DirectiveDefinitionNode] = []
    append_directive_def = directive_defs.append
    for def_ in document_ast.definitions:
        if isinstance(def_, SchemaDefinitionNode):
            schema_def = def_
        elif isinstance(def_, SchemaExtensionNode):
            schema_extensions.append(def_)
        elif isinstance(def_, TypeDefinitionNode):
            type_defs.append(def_)
        elif isinstance(def_, TypeExtensionNode):
            extended_type_name = def_.name.value
            type_extensions_map[extended_type_name].append(def_)
        elif isinstance(def_, DirectiveDefinitionNode):
            append_directive_def(def_)

    def resolve_type(type_name: str) -> GraphQLNamedType:
        type_ = type_map.get(type_name)
        if not type_:
            raise TypeError(f"Type '{type_name}' not found in document.")
        return type_

    ast_builder = ASTDefinitionBuilder(
        assume_valid=assume_valid, resolve_type=resolve_type
    )

    type_map = ast_builder.build_type_map(type_defs, type_extensions_map)

    operation_types: Dict[OperationType, GraphQLObjectType] = (
        ast_builder.get_operation_types([schema_def, *schema_extensions])
        if schema_def
        else {
            # Note: While this could make early assertions to get the correctly
            # typed values below, that would throw immediately while type system
            # validation with validate_schema() will produce more actionable results.
            OperationType.QUERY: cast(GraphQLObjectType, type_map.get("Query")),
            OperationType.MUTATION: cast(GraphQLObjectType, type_map.get("Mutation")),
            OperationType.SUBSCRIPTION: cast(
                GraphQLObjectType, type_map.get("Subscription")
            ),
        }
    )

    directives = ast_builder.build_directives(directive_defs)

    # If specified directives were not explicitly declared, add them.
    if not any(directive.name == "skip" for directive in directives):
        directives.append(GraphQLSkipDirective)
    if not any(directive.name == "include" for directive in directives):
        directives.append(GraphQLIncludeDirective)
    if not any(directive.name == "deprecated" for directive in directives):
        directives.append(GraphQLDeprecatedDirective)

    get_operation = operation_types.get
    return GraphQLSchema(
        query=get_operation(OperationType.QUERY),
        mutation=get_operation(OperationType.MUTATION),
        subscription=get_operation(OperationType.SUBSCRIPTION),
        types=type_map.values(),
        directives=directives,
        ast_node=schema_def,
        extension_ast_nodes=schema_extensions,
        assume_valid=assume_valid,
    )


def default_type_resolver(type_name: str, *_args) -> NoReturn:
    """Type resolver that always throws an error."""
    raise TypeError(f"Type '{type_name}' not found in document.")


std_type_map: Dict[str, Union[GraphQLNamedType, GraphQLObjectType]] = {
    **specified_scalar_types,
    **introspection_types,
}


class ASTDefinitionBuilder:
    def __init__(
        self,
        assume_valid: bool = False,
        resolve_type: TypeResolver = default_type_resolver,
    ) -> None:
        self._assume_valid = assume_valid
        self._resolve_type = resolve_type

    def get_operation_types(
        self, nodes: Collection[Union[SchemaDefinitionNode, SchemaExtensionNode]]
    ) -> Dict[OperationType, GraphQLObjectType]:
        # Note: While this could make early assertions to get the correctly
        # typed values below, that would throw immediately while type system
        # validation with validate_schema() will produce more actionable results.
        op_types: Dict[OperationType, GraphQLObjectType] = {}
        for node in nodes:
            if node.operation_types:
                for operation_type in node.operation_types:
                    type_name = operation_type.type.name.value
                    op_types[operation_type.operation] = cast(
                        GraphQLObjectType, self._resolve_type(type_name)
                    )
        return op_types

    def get_named_type(self, node: NamedTypeNode) -> GraphQLNamedType:
        name = node.name.value
        return std_type_map.get(name) or self._resolve_type(name)

    def get_wrapped_type(self, node: TypeNode) -> GraphQLType:
        if isinstance(node, ListTypeNode):
            return GraphQLList(self.get_wrapped_type(node.type))
        if isinstance(node, NonNullTypeNode):
            return GraphQLNonNull(
                cast(GraphQLNullableType, self.get_wrapped_type(node.type))
            )
        return self.get_named_type(cast(NamedTypeNode, node))

    def build_directive(self, directive: DirectiveDefinitionNode) -> GraphQLDirective:
        locations = [DirectiveLocation[node.value] for node in directive.locations]

        return GraphQLDirective(
            name=directive.name.value,
            description=directive.description.value if directive.description else None,
            locations=locations,
            is_repeatable=directive.repeatable,
            args=self.build_argument_map(directive.arguments),
            ast_node=directive,
        )

    def build_directives(
        self, nodes: Collection[DirectiveDefinitionNode]
    ) -> List[GraphQLDirective]:
        return [self.build_directive(node) for node in nodes]

    def build_field_map(
        self,
        nodes: Collection[
            Union[
                InterfaceTypeDefinitionNode,
                InterfaceTypeExtensionNode,
                ObjectTypeDefinitionNode,
                ObjectTypeExtensionNode,
            ]
        ],
    ) -> GraphQLFieldMap:
        field_map: GraphQLFieldMap = {}
        for node in nodes:
            if node.fields:
                for field in node.fields:
                    # Note: While this could make assertions to get the correctly typed
                    # value, that would throw immediately while type system validation
                    # with validate_schema() will produce more actionable results.
                    field_map[field.name.value] = GraphQLField(
                        type_=cast(
                            GraphQLOutputType, self.get_wrapped_type(field.type)
                        ),
                        description=field.description.value
                        if field.description
                        else None,
                        args=self.build_argument_map(field.arguments),
                        deprecation_reason=get_deprecation_reason(field),
                        ast_node=field,
                    )
        return field_map

    def build_argument_map(
        self, args: Optional[Collection[InputValueDefinitionNode]]
    ) -> GraphQLArgumentMap:
        arg_map: GraphQLArgumentMap = {}
        if args:
            for arg in args:
                # Note: While this could make assertions to get the correctly typed
                # value, that would throw immediately while type system validation
                # with validate_schema() will produce more actionable results.
                type_ = cast(GraphQLInputType, self.get_wrapped_type(arg.type))
                arg_map[arg.name.value] = GraphQLArgument(
                    type_=type_,
                    description=arg.description.value if arg.description else None,
                    default_value=value_from_ast(arg.default_value, type_),
                    ast_node=arg,
                )
        return arg_map

    def build_input_field_map(
        self,
        nodes: Collection[
            Union[InputObjectTypeDefinitionNode, InputObjectTypeExtensionNode]
        ],
    ) -> GraphQLInputFieldMap:
        input_field_map: GraphQLInputFieldMap = {}
        for node in nodes:
            if node.fields:
                for field in node.fields:
                    # Note: While this could make assertions to get the correctly typed
                    # value, that would throw immediately while type system validation
                    # with validate_schema() will produce more actionable results.
                    type_ = cast(GraphQLInputType, self.get_wrapped_type(field.type))
                    input_field_map[field.name.value] = GraphQLInputField(
                        type_=type_,
                        description=field.description.value
                        if field.description
                        else None,
                        default_value=value_from_ast(field.default_value, type_),
                        ast_node=field,
                    )
        return input_field_map

    @staticmethod
    def build_enum_value_map(
        nodes: Collection[Union[EnumTypeDefinitionNode, EnumTypeExtensionNode]]
    ) -> GraphQLEnumValueMap:
        enum_value_map: GraphQLEnumValueMap = {}
        for node in nodes:
            if node.values:
                for value in node.values:
                    # Note: While this could make assertions to get the correctly typed
                    # value, that would throw immediately while type system validation
                    # with validate_schema() will produce more actionable results.
                    enum_value_map[value.name.value] = GraphQLEnumValue(
                        description=value.description.value
                        if value.description
                        else None,
                        deprecation_reason=get_deprecation_reason(value),
                        ast_node=value,
                    )
        return enum_value_map

    def build_interfaces(
        self,
        nodes: Collection[
            Union[
                InterfaceTypeDefinitionNode,
                InterfaceTypeExtensionNode,
                ObjectTypeDefinitionNode,
                ObjectTypeExtensionNode,
            ]
        ],
    ) -> List[GraphQLInterfaceType]:
        interfaces: List[GraphQLInterfaceType] = []
        for node in nodes:
            if node.interfaces:
                for type_ in node.interfaces:
                    # Note: While this could make assertions to get the correctly typed
                    # value, that would throw immediately while type system validation
                    # with validate_schema() will produce more actionable results.
                    interfaces.append(
                        cast(GraphQLInterfaceType, self.get_named_type(type_))
                    )
        return interfaces

    def build_union_types(
        self, nodes: Collection[Union[UnionTypeDefinitionNode, UnionTypeExtensionNode]],
    ) -> List[GraphQLObjectType]:
        types: List[GraphQLObjectType] = []
        for node in nodes:
            if node.types:
                for type_ in node.types:
                    # Note: While this could make assertions to get the correctly typed
                    # value, that would throw immediately while type system validation
                    # with validate_schema() will produce more actionable results.
                    types.append(cast(GraphQLObjectType, self.get_named_type(type_)))
        return types

    def build_type_map(
        self,
        nodes: Collection[TypeDefinitionNode],
        extensions_map: DefaultDict[str, List[TypeExtensionNode]],
    ) -> Dict[str, GraphQLNamedType]:
        type_map: Dict[str, GraphQLNamedType] = {}
        for node in nodes:
            name = node.name.value
            type_map[name] = std_type_map.get(name) or self._build_type(
                node, extensions_map[name]
            )
        return type_map

    def _build_type(
        self,
        ast_node: TypeDefinitionNode,
        extension_nodes: Collection[TypeExtensionNode],
    ) -> GraphQLNamedType:
        try:
            # object_type_definition_node is built with _build_object_type etc.
            method = getattr(self, "_build_" + ast_node.kind[:-11])
        except AttributeError:
            # Not reachable. All possible type definition nodes have been considered.
            raise TypeError(  # pragma: no cover
                f"Unexpected type definition node: {inspect(ast_node)}."
            )
        else:
            return method(ast_node, extension_nodes)

    def _build_object_type(
        self,
        ast_node: ObjectTypeDefinitionNode,
        extension_nodes: Collection[ObjectTypeExtensionNode],
    ) -> GraphQLObjectType:
        all_nodes: List[Union[ObjectTypeDefinitionNode, ObjectTypeExtensionNode]] = [
            ast_node,
            *extension_nodes,
        ]
        return GraphQLObjectType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            interfaces=lambda: self.build_interfaces(all_nodes),
            fields=lambda: self.build_field_map(all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def _build_interface_type(
        self,
        ast_node: InterfaceTypeDefinitionNode,
        extension_nodes: Collection[InterfaceTypeExtensionNode],
    ) -> GraphQLInterfaceType:
        all_nodes: List[
            Union[InterfaceTypeDefinitionNode, InterfaceTypeExtensionNode]
        ] = [ast_node, *extension_nodes]
        return GraphQLInterfaceType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            interfaces=lambda: self.build_interfaces(all_nodes),
            fields=lambda: self.build_field_map(all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def _build_enum_type(
        self,
        ast_node: EnumTypeDefinitionNode,
        extension_nodes: Collection[EnumTypeExtensionNode],
    ) -> GraphQLEnumType:
        all_nodes: List[Union[EnumTypeDefinitionNode, EnumTypeExtensionNode]] = [
            ast_node,
            *extension_nodes,
        ]
        return GraphQLEnumType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            values=self.build_enum_value_map(all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def _build_union_type(
        self,
        ast_node: UnionTypeDefinitionNode,
        extension_nodes: Collection[UnionTypeExtensionNode],
    ) -> GraphQLUnionType:
        all_nodes: List[Union[UnionTypeDefinitionNode, UnionTypeExtensionNode]] = [
            ast_node,
            *extension_nodes,
        ]
        return GraphQLUnionType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            types=lambda: self.build_union_types(all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    @staticmethod
    def _build_scalar_type(
        ast_node: ScalarTypeDefinitionNode,
        extension_nodes: Collection[ScalarTypeExtensionNode],
    ) -> GraphQLScalarType:
        return GraphQLScalarType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def _build_input_object_type(
        self,
        ast_node: InputObjectTypeDefinitionNode,
        extension_nodes: Collection[InputObjectTypeExtensionNode],
    ) -> GraphQLInputObjectType:
        all_nodes: List[
            Union[InputObjectTypeDefinitionNode, InputObjectTypeExtensionNode]
        ] = [ast_node, *extension_nodes]
        return GraphQLInputObjectType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            fields=lambda: self.build_input_field_map(all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
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
