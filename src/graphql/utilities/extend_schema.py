from collections import defaultdict
from typing import (
    Any,
    Callable,
    Collection,
    DefaultDict,
    Dict,
    List,
    Optional,
    NoReturn,
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
    Node,
    NonNullTypeNode,
    ObjectTypeDefinitionNode,
    ObjectTypeExtensionNode,
    OperationType,
    ScalarTypeDefinitionNode,
    ScalarTypeExtensionNode,
    SchemaExtensionNode,
    SchemaDefinitionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    TypeNode,
    UnionTypeDefinitionNode,
    UnionTypeExtensionNode,
)
from ..pyutils import inspect, FrozenList
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
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInputFieldMap,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLNullableType,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLType,
    GraphQLUnionType,
    assert_schema,
    is_enum_type,
    is_input_object_type,
    is_interface_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
    is_scalar_type,
    is_union_type,
    is_introspection_type,
    is_specified_scalar_type,
    introspection_types,
    specified_scalar_types,
)
from .value_from_ast import value_from_ast

__all__ = [
    "extend_schema",
    "get_description",
    "ASTDefinitionBuilder",
]

TypeResolver = Callable[[str], GraphQLNamedType]


def extend_schema(
    schema: GraphQLSchema,
    document_ast: DocumentNode,
    assume_valid=False,
    assume_valid_sdl=False,
) -> GraphQLSchema:
    """Extend the schema with extensions from a given document.

    Produces a new schema given an existing schema and a document which may contain
    GraphQL type extensions and definitions. The original schema will remain unaltered.

    Because a schema represents a graph of references, a schema cannot be extended
    without effectively making an entire copy. We do not know until it's too late if
    subgraphs remain unchanged.

    This algorithm copies the provided schema, applying extensions while producing the
    copy. The original schema remains unaltered.

    When extending a schema with a known valid extension, it might be safe to assume the
    schema is valid. Set `assume_valid` to true to assume the produced schema is valid.
    Set `assume_valid_sdl` to True to assume it is already a valid SDL document.
    """
    assert_schema(schema)

    if not isinstance(document_ast, DocumentNode):
        raise TypeError("Must provide valid Document AST.")

    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl_extension

        assert_valid_sdl_extension(document_ast, schema)

    # Collect the type definitions and extensions found in the document.
    type_defs: List[TypeDefinitionNode] = []
    type_extensions_map: DefaultDict[str, Any] = defaultdict(list)

    # New directives and types are separate because a directives and types can have the
    # same name. For example, a type named "skip".
    directive_defs: List[DirectiveDefinitionNode] = []

    schema_def: Optional[SchemaDefinitionNode] = None
    # Schema extensions are collected which may add additional operation types.
    schema_extensions: List[SchemaExtensionNode] = []

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
            directive_defs.append(def_)

    # If this document contains no new types, extensions, or directives then return the
    # same unmodified GraphQLSchema instance.
    if (
        not type_extensions_map
        and not type_defs
        and not directive_defs
        and not schema_extensions
        and not schema_def
    ):
        return schema

    # Below are functions used for producing this schema that have closed over this
    # scope and have access to the schema, cache, and newly defined types.

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def replace_type(type_: GraphQLType) -> GraphQLType:
        if is_list_type(type_):
            return GraphQLList(replace_type(type_.of_type))  # type: ignore
        if is_non_null_type(type_):
            return GraphQLNonNull(replace_type(type_.of_type))  # type: ignore
        return replace_named_type(type_)  # type: ignore

    def replace_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        # Note: While this could make early assertions to get the correctly
        # typed values below, that would throw immediately while type system
        # validation with validate_schema() will produce more actionable results.
        return type_map[type_.name]

    def replace_directive(directive: GraphQLDirective) -> GraphQLDirective:
        kwargs = directive.to_kwargs()
        return GraphQLDirective(
            **{  # type: ignore
                **kwargs,
                "args": {name: extend_arg(arg) for name, arg in kwargs["args"].items()},
            }
        )

    def extend_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        if is_introspection_type(type_) or is_specified_scalar_type(type_):
            # Builtin types are not extended.
            return type_
        if is_scalar_type(type_):
            type_ = cast(GraphQLScalarType, type_)
            return extend_scalar_type(type_)
        if is_object_type(type_):
            type_ = cast(GraphQLObjectType, type_)
            return extend_object_type(type_)
        if is_interface_type(type_):
            type_ = cast(GraphQLInterfaceType, type_)
            return extend_interface_type(type_)
        if is_union_type(type_):
            type_ = cast(GraphQLUnionType, type_)
            return extend_union_type(type_)
        if is_enum_type(type_):
            type_ = cast(GraphQLEnumType, type_)
            return extend_enum_type(type_)
        if is_input_object_type(type_):
            type_ = cast(GraphQLInputObjectType, type_)
            return extend_input_object_type(type_)

        # Not reachable. All possible types have been considered.
        raise TypeError(f"Unexpected type: {inspect(type_)}.")  # pragma: no cover

    def extend_input_object_type(
        type_: GraphQLInputObjectType,
    ) -> GraphQLInputObjectType:
        kwargs = type_.to_kwargs()
        extensions = type_extensions_map.get(kwargs["name"], [])

        return GraphQLInputObjectType(
            **{
                **kwargs,
                "fields": lambda: {
                    **{
                        name: GraphQLInputField(
                            **{  # type: ignore
                                **field.to_kwargs(),
                                "type_": replace_type(field.type),
                            }
                        )
                        for name, field in kwargs["fields"].items()
                    },
                    **ast_builder.build_input_field_map(extensions),
                },
                "extension_ast_nodes": (kwargs["extension_ast_nodes"] or [])
                + extensions,
            }
        )

    def extend_enum_type(type_: GraphQLEnumType) -> GraphQLEnumType:
        kwargs = type_.to_kwargs()
        extensions = type_extensions_map.get(kwargs["name"], [])

        return GraphQLEnumType(
            **{
                **kwargs,
                "values": {
                    **kwargs["values"],
                    **ast_builder.build_enum_value_map(extensions),
                },
                "extension_ast_nodes": (kwargs["extension_ast_nodes"] or [])
                + extensions,
            }
        )

    def extend_scalar_type(type_: GraphQLScalarType) -> GraphQLScalarType:
        kwargs = type_.to_kwargs()
        extensions = type_extensions_map.get(kwargs["name"], [])

        return GraphQLScalarType(
            **{
                **kwargs,
                "extension_ast_nodes": (kwargs["extension_ast_nodes"] or [])
                + extensions,
            }
        )

    def extend_object_type(type_: GraphQLObjectType) -> GraphQLObjectType:
        kwargs = type_.to_kwargs()
        extensions = type_extensions_map.get(kwargs["name"], [])

        return GraphQLObjectType(
            **{
                **kwargs,
                "interfaces": lambda: [
                    cast(GraphQLInterfaceType, replace_named_type(interface))
                    for interface in kwargs["interfaces"]
                ]
                + ast_builder.build_interfaces(extensions),
                "fields": lambda: {
                    **{
                        name: extend_field(field)
                        for name, field in kwargs["fields"].items()
                    },
                    **ast_builder.build_field_map(extensions),
                },
                "extension_ast_nodes": (kwargs["extension_ast_nodes"] or [])
                + extensions,
            }
        )

    def extend_interface_type(type_: GraphQLInterfaceType) -> GraphQLInterfaceType:
        kwargs = type_.to_kwargs()
        extensions = type_extensions_map.get(kwargs["name"], [])

        return GraphQLInterfaceType(
            **{
                **kwargs,
                "interfaces": lambda: [
                    cast(GraphQLInterfaceType, replace_named_type(interface))
                    for interface in kwargs["interfaces"]
                ]
                + ast_builder.build_interfaces(extensions),
                "fields": lambda: {
                    **{
                        name: extend_field(field)
                        for name, field in kwargs["fields"].items()
                    },
                    **ast_builder.build_field_map(extensions),
                },
                "extension_ast_nodes": (kwargs["extension_ast_nodes"] or [])
                + extensions,
            }
        )

    def extend_union_type(type_: GraphQLUnionType) -> GraphQLUnionType:
        kwargs = type_.to_kwargs()
        extensions = type_extensions_map.get(kwargs["name"], [])

        return GraphQLUnionType(
            **{
                **kwargs,
                "types": lambda: [
                    cast(GraphQLObjectType, replace_named_type(member_type))
                    for member_type in kwargs["types"]
                ]
                + ast_builder.build_union_types(extensions),
                "extension_ast_nodes": (kwargs["extension_ast_nodes"] or [])
                + extensions,
            }
        )

    def extend_field(field: GraphQLField) -> GraphQLField:
        return GraphQLField(
            **{  # type: ignore
                **field.to_kwargs(),
                "type_": replace_type(field.type),
                "args": {name: extend_arg(arg) for name, arg in field.args.items()},
            }
        )

    def extend_arg(arg: GraphQLArgument) -> GraphQLArgument:
        return GraphQLArgument(
            **{  # type: ignore
                **arg.to_kwargs(),
                "type_": replace_type(arg.type),
            }
        )

    # noinspection PyShadowingNames
    def resolve_type(type_name: str) -> GraphQLNamedType:
        type_ = type_map.get(type_name)
        if not type_:
            raise TypeError(f"Unknown type: '{type_name}'.")
        return type_

    ast_builder = ASTDefinitionBuilder(resolve_type)

    type_map = ast_builder.build_type_map(type_defs, type_extensions_map)
    for existing_type_name, existing_type in schema.type_map.items():
        type_map[existing_type_name] = extend_named_type(existing_type)

    # Get the extended root operation types.
    operation_types: Dict[OperationType, GraphQLObjectType] = {}
    if schema.query_type:
        operation_types[OperationType.QUERY] = cast(
            GraphQLObjectType, replace_named_type(schema.query_type)
        )
    if schema.mutation_type:
        operation_types[OperationType.MUTATION] = cast(
            GraphQLObjectType, replace_named_type(schema.mutation_type)
        )
    if schema.subscription_type:
        operation_types[OperationType.SUBSCRIPTION] = cast(
            GraphQLObjectType, replace_named_type(schema.subscription_type)
        )
    # Then, incorporate schema definition and all schema extensions.
    if schema_def:
        operation_types.update(ast_builder.get_operation_types([schema_def]))
    if schema_extensions:
        operation_types.update(ast_builder.get_operation_types(schema_extensions))

    # Then produce and return a Schema with these types.
    get_operation = operation_types.get
    return GraphQLSchema(
        # Note: While this could make early assertions to get the correctly
        # typed values, that would throw immediately while type system
        # validation with validateSchema() will produce more actionable results.
        query=get_operation(OperationType.QUERY),
        mutation=get_operation(OperationType.MUTATION),
        subscription=get_operation(OperationType.SUBSCRIPTION),
        types=type_map.values(),
        directives=[replace_directive(directive) for directive in schema.directives]
        + ast_builder.build_directives(directive_defs),
        ast_node=schema_def or schema.ast_node,
        extension_ast_nodes=(
            (
                schema.extension_ast_nodes
                or cast(FrozenList[SchemaExtensionNode], FrozenList())
            )
            + schema_extensions
        )
        or None,
    )


def default_type_resolver(type_name: str, *_args) -> NoReturn:
    """Type resolver that always throws an error."""
    raise TypeError(f"Type '{type_name}' not found in document.")


std_type_map: Dict[str, Union[GraphQLNamedType, GraphQLObjectType]] = {
    **specified_scalar_types,
    **introspection_types,
}


class ASTDefinitionBuilder:
    def __init__(self, resolve_type: TypeResolver = default_type_resolver,) -> None:
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
