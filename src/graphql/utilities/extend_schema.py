"""GraphQL schema extension"""

from __future__ import annotations

from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
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
    ScalarTypeDefinitionNode,
    ScalarTypeExtensionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    TypeNode,
    UnionTypeDefinitionNode,
    UnionTypeExtensionNode,
)
from ..pyutils import inspect, merge_kwargs
from ..type import (
    GraphQLArgument,
    GraphQLArgumentMap,
    GraphQLDefaultInput,
    GraphQLDeprecatedDirective,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLEnumValueMap,
    GraphQLField,
    GraphQLFieldMap,
    GraphQLInputField,
    GraphQLInputFieldMap,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLNullableType,
    GraphQLObjectType,
    GraphQLOneOfDirective,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLSchemaKwargs,
    GraphQLSpecifiedByDirective,
    GraphQLType,
    GraphQLUnionType,
    assert_schema,
    introspection_types,
    specified_scalar_types,
)
from .map_schema_config import SchemaElementKind, map_schema_config

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from .map_schema_config import ConfigMapperMap, MappedSchemaContext

__all__ = [
    "ExtendSchemaImpl",
    "extend_schema",
]


def extend_schema(
    schema: GraphQLSchema,
    document_ast: DocumentNode,
    assume_valid: bool = False,
    assume_valid_sdl: bool = False,
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
    schema is valid. Set ``assume_valid`` to ``True`` to assume the produced schema is
    valid. Set ``assume_valid_sdl`` to ``True`` to assume it is already a valid SDL
    document.
    """
    assert_schema(schema)

    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl_extension

        assert_valid_sdl_extension(document_ast, schema)

    schema_kwargs = schema.to_kwargs()
    extended_kwargs = ExtendSchemaImpl.extend_schema_args(
        schema_kwargs, document_ast, assume_valid
    )
    return (
        schema if schema_kwargs is extended_kwargs else GraphQLSchema(**extended_kwargs)
    )


TEN = TypeVar("TEN", bound=TypeExtensionNode)


class TypeExtensionsMap:
    """Mappings from types to their extensions."""

    scalar: defaultdict[str, list[ScalarTypeExtensionNode]]
    object: defaultdict[str, list[ObjectTypeExtensionNode]]
    interface: defaultdict[str, list[InterfaceTypeExtensionNode]]
    union: defaultdict[str, list[UnionTypeExtensionNode]]
    enum: defaultdict[str, list[EnumTypeExtensionNode]]
    input_object: defaultdict[str, list[InputObjectTypeExtensionNode]]

    def __init__(self) -> None:
        self.scalar = defaultdict(list)
        self.object = defaultdict(list)
        self.interface = defaultdict(list)
        self.union = defaultdict(list)
        self.enum = defaultdict(list)
        self.input_object = defaultdict(list)

    def for_node(self, node: TEN) -> defaultdict[str, list[TEN]]:
        """Get type extensions map for the given node kind."""
        kind = node.kind.removesuffix("_type_extension")
        return getattr(self, kind)


class ExtendSchemaImpl:
    """Helper class implementing the methods to extend a schema.

    For internal use only.
    """

    @classmethod
    def extend_schema_args(
        cls,
        schema_kwargs: GraphQLSchemaKwargs,
        document_ast: DocumentNode,
        assume_valid: bool = False,
    ) -> GraphQLSchemaKwargs:
        """Extend the given schema arguments with extensions from a given document.

        For internal use only.
        """
        # Collect the type definitions and extensions found in the document.
        type_defs: list[TypeDefinitionNode] = []

        type_extensions = TypeExtensionsMap()

        # New directives and types are separate because a directives and types can have
        # the same name. For example, a type named "skip".
        directive_defs: list[DirectiveDefinitionNode] = []

        schema_def: SchemaDefinitionNode | None = None
        # Schema extensions are collected which may add additional operation types.
        schema_extensions: list[SchemaExtensionNode] = []

        is_schema_changed = False
        for def_ in document_ast.definitions:
            if isinstance(def_, SchemaDefinitionNode):
                schema_def = def_
            elif isinstance(def_, SchemaExtensionNode):
                schema_extensions.append(def_)
            elif isinstance(def_, DirectiveDefinitionNode):
                directive_defs.append(def_)
            elif isinstance(def_, TypeDefinitionNode):
                type_defs.append(def_)
            elif isinstance(def_, TypeExtensionNode):
                type_extensions.for_node(def_)[def_.name.value].append(def_)
            else:
                continue
            is_schema_changed = True

        # If this document contains no new types, extensions, or directives then return
        # the same unmodified GraphQLSchema instance.
        if not is_schema_changed:
            return schema_kwargs

        def config_mapper_map_fn(context: MappedSchemaContext) -> ConfigMapperMap:
            get_named_type = context.get_named_type
            set_named_type = context.set_named_type
            get_named_types = context.get_named_types

            def get_operation_types(
                nodes: Collection[SchemaDefinitionNode | SchemaExtensionNode],
            ) -> dict[str, GraphQLObjectType]:
                # Note: While this could make early assertions to get the correctly
                # typed values below, that would throw immediately while type system
                # validation with validate_schema() will produce more actionable
                # results.
                return {
                    operation_type.operation.value: cast(
                        "GraphQLObjectType", named_type_from_ast(operation_type.type)
                    )
                    for node in nodes
                    for operation_type in node.operation_types or []
                }

            def named_type_from_ast(node: NamedTypeNode) -> GraphQLNamedType:
                return get_named_type(node.name.value)

            def type_from_ast(node: TypeNode) -> GraphQLType:
                if isinstance(node, ListTypeNode):
                    return GraphQLList(type_from_ast(node.type))
                if isinstance(node, NonNullTypeNode):
                    return GraphQLNonNull(
                        cast("GraphQLNullableType", type_from_ast(node.type))
                    )
                return named_type_from_ast(cast("NamedTypeNode", node))

            def build_directive(node: DirectiveDefinitionNode) -> GraphQLDirective:
                locations = [DirectiveLocation[node.value] for node in node.locations]
                return GraphQLDirective(
                    name=node.name.value,
                    description=node.description.value if node.description else None,
                    locations=locations,
                    is_repeatable=node.repeatable,
                    args=build_argument_map(node.arguments),
                    ast_node=node,
                )

            def build_field_map(
                nodes: Collection[
                    InterfaceTypeDefinitionNode
                    | InterfaceTypeExtensionNode
                    | ObjectTypeDefinitionNode
                    | ObjectTypeExtensionNode
                ],
            ) -> GraphQLFieldMap:
                field_map: GraphQLFieldMap = {}
                for node in nodes:
                    for field in node.fields or []:
                        # Note: While this could make assertions to get the correctly
                        # typed value, that would throw immediately while type system
                        # validation with validate_schema() will produce more
                        # actionable results.
                        field_map[field.name.value] = GraphQLField(
                            type_=cast("GraphQLOutputType", type_from_ast(field.type)),
                            description=field.description.value
                            if field.description
                            else None,
                            args=build_argument_map(field.arguments),
                            deprecation_reason=get_deprecation_reason(field),
                            ast_node=field,
                        )
                return field_map

            def build_argument_map(
                args: Collection[InputValueDefinitionNode] | None,
            ) -> GraphQLArgumentMap:
                arg_map: GraphQLArgumentMap = {}
                for arg in args or []:
                    # Note: While this could make assertions to get the correctly
                    # typed value, that would throw immediately while type system
                    # validation with validate_schema() will produce more actionable
                    # results.
                    type_ = cast("GraphQLInputType", type_from_ast(arg.type))
                    arg_map[arg.name.value] = GraphQLArgument(
                        type_=type_,
                        description=arg.description.value if arg.description else None,
                        default=GraphQLDefaultInput(literal=arg.default_value)
                        if arg.default_value
                        else None,
                        deprecation_reason=get_deprecation_reason(arg),
                        ast_node=arg,
                    )
                return arg_map

            def build_input_field_map(
                nodes: Collection[
                    InputObjectTypeDefinitionNode | InputObjectTypeExtensionNode
                ],
            ) -> GraphQLInputFieldMap:
                input_field_map: GraphQLInputFieldMap = {}
                for node in nodes:
                    for field in node.fields or []:
                        # Note: While this could make assertions to get the correctly
                        # typed value, that would throw immediately while type system
                        # validation with validate_schema() will produce more
                        # actionable results.
                        type_ = cast("GraphQLInputType", type_from_ast(field.type))
                        input_field_map[field.name.value] = GraphQLInputField(
                            type_=type_,
                            description=field.description.value
                            if field.description
                            else None,
                            default=GraphQLDefaultInput(literal=field.default_value)
                            if field.default_value
                            else None,
                            deprecation_reason=get_deprecation_reason(field),
                            ast_node=field,
                        )
                return input_field_map

            def build_enum_value_map(
                nodes: Collection[EnumTypeDefinitionNode | EnumTypeExtensionNode],
            ) -> GraphQLEnumValueMap:
                enum_value_map: GraphQLEnumValueMap = {}
                for node in nodes:
                    for value in node.values or []:
                        # Note: While this could make assertions to get the correctly
                        # typed value, that would throw immediately while type system
                        # validation with validate_schema() will produce more
                        # actionable results.
                        value_name = value.name.value
                        enum_value_map[value_name] = GraphQLEnumValue(
                            value=value_name,
                            description=value.description.value
                            if value.description
                            else None,
                            deprecation_reason=get_deprecation_reason(value),
                            ast_node=value,
                        )
                return enum_value_map

            def build_interfaces(
                nodes: Collection[
                    InterfaceTypeDefinitionNode
                    | InterfaceTypeExtensionNode
                    | ObjectTypeDefinitionNode
                    | ObjectTypeExtensionNode
                ],
            ) -> list[GraphQLInterfaceType]:
                # Note: While this could make assertions to get the correctly typed
                # values below, that would throw immediately while type system
                # validation with validate_schema() will produce more actionable
                # results.
                return [
                    cast("GraphQLInterfaceType", named_type_from_ast(type_))
                    for node in nodes
                    for type_ in node.interfaces or []
                ]

            def build_union_types(
                nodes: Collection[UnionTypeDefinitionNode | UnionTypeExtensionNode],
            ) -> list[GraphQLObjectType]:
                # Note: While this could make assertions to get the correctly typed
                # values below, that would throw immediately while type system
                # validation with validate_schema() will produce more actionable
                # results.
                return [
                    cast("GraphQLObjectType", named_type_from_ast(type_))
                    for node in nodes
                    for type_ in node.types or []
                ]

            def build_named_type(ast_node: TypeDefinitionNode) -> GraphQLNamedType:
                name = ast_node.name.value
                description = (
                    ast_node.description.value if ast_node.description else None
                )
                match ast_node:
                    case ObjectTypeDefinitionNode():
                        object_extensions = type_extensions.object[name]
                        object_nodes: list[
                            ObjectTypeDefinitionNode | ObjectTypeExtensionNode
                        ] = [ast_node, *object_extensions]
                        return GraphQLObjectType(
                            name=name,
                            description=description,
                            interfaces=lambda: build_interfaces(object_nodes),
                            fields=lambda: build_field_map(object_nodes),
                            ast_node=ast_node,
                            extension_ast_nodes=object_extensions,
                        )
                    case InterfaceTypeDefinitionNode():
                        interface_extensions = type_extensions.interface[name]
                        interface_nodes: list[
                            InterfaceTypeDefinitionNode | InterfaceTypeExtensionNode
                        ] = [ast_node, *interface_extensions]
                        return GraphQLInterfaceType(
                            name=name,
                            description=description,
                            interfaces=lambda: build_interfaces(interface_nodes),
                            fields=lambda: build_field_map(interface_nodes),
                            ast_node=ast_node,
                            extension_ast_nodes=interface_extensions,
                        )
                    case EnumTypeDefinitionNode():
                        enum_extensions = type_extensions.enum[name]
                        enum_nodes: list[
                            EnumTypeDefinitionNode | EnumTypeExtensionNode
                        ] = [ast_node, *enum_extensions]
                        return GraphQLEnumType(
                            name=name,
                            description=description,
                            values=lambda: build_enum_value_map(enum_nodes),
                            ast_node=ast_node,
                            extension_ast_nodes=enum_extensions,
                        )
                    case UnionTypeDefinitionNode():
                        union_extensions = type_extensions.union[name]
                        union_nodes: list[
                            UnionTypeDefinitionNode | UnionTypeExtensionNode
                        ] = [ast_node, *union_extensions]
                        return GraphQLUnionType(
                            name=name,
                            description=description,
                            types=lambda: build_union_types(union_nodes),
                            ast_node=ast_node,
                            extension_ast_nodes=union_extensions,
                        )
                    case ScalarTypeDefinitionNode():
                        scalar_extensions = type_extensions.scalar[name]
                        return GraphQLScalarType(
                            name=name,
                            description=description,
                            specified_by_url=get_specified_by_url(ast_node),
                            ast_node=ast_node,
                            extension_ast_nodes=scalar_extensions,
                        )
                    case InputObjectTypeDefinitionNode():
                        input_extensions = type_extensions.input_object[name]
                        input_nodes: list[
                            InputObjectTypeDefinitionNode | InputObjectTypeExtensionNode
                        ] = [ast_node, *input_extensions]
                        return GraphQLInputObjectType(
                            name=name,
                            description=description,
                            fields=lambda: build_input_field_map(input_nodes),
                            ast_node=ast_node,
                            extension_ast_nodes=input_extensions,
                            is_one_of=is_one_of(ast_node),
                        )
                    case _:  # pragma: no cover
                        # Not reachable. All possible type nodes have been considered.
                        msg = f"Unexpected type definition node: {inspect(ast_node)}."
                        raise TypeError(msg)

            def schema_mapper(config: Any) -> Any:
                for type_node in type_defs:
                    type_ = std_type_map.get(type_node.name.value) or build_named_type(
                        type_node
                    )
                    set_named_type(type_)

                # Get the extended root operation types.
                operation_types: dict[str, GraphQLObjectType | None] = {
                    "query": cast(
                        "GraphQLObjectType", get_named_type(config["query"].name)
                    )
                    if config["query"]
                    else None,
                    "mutation": cast(
                        "GraphQLObjectType", get_named_type(config["mutation"].name)
                    )
                    if config["mutation"]
                    else None,
                    "subscription": cast(
                        "GraphQLObjectType",
                        get_named_type(config["subscription"].name),
                    )
                    if config["subscription"]
                    else None,
                }
                # Then, incorporate schema definition and all schema extensions.
                if schema_def:
                    operation_types.update(get_operation_types([schema_def]))
                operation_types.update(get_operation_types(schema_extensions))

                # Then produce and return the kwargs for a Schema with these types.
                description = (
                    schema_def.description.value
                    if schema_def and schema_def.description
                    else None
                )
                if description is None:
                    description = config["description"]
                return merge_kwargs(
                    config,
                    description=description,
                    query=operation_types["query"],
                    mutation=operation_types["mutation"],
                    subscription=operation_types["subscription"],
                    types=get_named_types(),
                    directives=tuple(config["directives"])
                    + tuple(build_directive(directive) for directive in directive_defs),
                    ast_node=schema_def or config["ast_node"],
                    extension_ast_nodes=config["extension_ast_nodes"]
                    + tuple(schema_extensions),
                    assume_valid=assume_valid,
                )

            def input_object_mapper(config: Any) -> Any:
                extensions = tuple(type_extensions.input_object[config["name"]])
                return merge_kwargs(
                    config,
                    fields=lambda: {
                        **config["fields"](),
                        **build_input_field_map(extensions),
                    },
                    extension_ast_nodes=config["extension_ast_nodes"] + extensions,
                )

            def enum_mapper(config: Any) -> Any:
                extensions = tuple(type_extensions.enum[config["name"]])
                return merge_kwargs(
                    config,
                    values=lambda: {
                        **config["values"](),
                        **build_enum_value_map(extensions),
                    },
                    extension_ast_nodes=config["extension_ast_nodes"] + extensions,
                )

            def scalar_mapper(config: Any) -> Any:
                extensions = tuple(type_extensions.scalar[config["name"]])
                specified_by_url = config["specified_by_url"]
                for extension_node in extensions:
                    specified_by_url = (
                        get_specified_by_url(extension_node) or specified_by_url
                    )
                return merge_kwargs(
                    config,
                    specified_by_url=specified_by_url,
                    extension_ast_nodes=config["extension_ast_nodes"] + extensions,
                )

            def object_mapper(config: Any) -> Any:
                extensions = tuple(type_extensions.object[config["name"]])
                return merge_kwargs(
                    config,
                    interfaces=lambda: [
                        *config["interfaces"](),
                        *build_interfaces(extensions),
                    ],
                    fields=lambda: {
                        **config["fields"](),
                        **build_field_map(extensions),
                    },
                    extension_ast_nodes=config["extension_ast_nodes"] + extensions,
                )

            def interface_mapper(config: Any) -> Any:
                extensions = tuple(type_extensions.interface[config["name"]])
                return merge_kwargs(
                    config,
                    interfaces=lambda: [
                        *config["interfaces"](),
                        *build_interfaces(extensions),
                    ],
                    fields=lambda: {
                        **config["fields"](),
                        **build_field_map(extensions),
                    },
                    extension_ast_nodes=config["extension_ast_nodes"] + extensions,
                )

            def union_mapper(config: Any) -> Any:
                extensions = tuple(type_extensions.union[config["name"]])
                return merge_kwargs(
                    config,
                    types=lambda: [
                        *config["types"](),
                        *build_union_types(extensions),
                    ],
                    extension_ast_nodes=config["extension_ast_nodes"] + extensions,
                )

            return cast(
                "ConfigMapperMap",
                {
                    SchemaElementKind.SCHEMA: schema_mapper,
                    SchemaElementKind.INPUT_OBJECT: input_object_mapper,
                    SchemaElementKind.ENUM: enum_mapper,
                    SchemaElementKind.SCALAR: scalar_mapper,
                    SchemaElementKind.OBJECT: object_mapper,
                    SchemaElementKind.INTERFACE: interface_mapper,
                    SchemaElementKind.UNION: union_mapper,
                },
            )

        return map_schema_config(schema_kwargs, config_mapper_map_fn)


std_type_map: Mapping[str, GraphQLNamedType | GraphQLObjectType] = {
    **specified_scalar_types,
    **introspection_types,
}


def get_deprecation_reason(
    node: EnumValueDefinitionNode | FieldDefinitionNode | InputValueDefinitionNode,
) -> str | None:
    """Given a field or enum value node, get deprecation reason as string."""
    from ..execution import get_directive_values

    deprecated = get_directive_values(GraphQLDeprecatedDirective, node)
    return deprecated["reason"] if deprecated else None


def get_specified_by_url(
    node: ScalarTypeDefinitionNode | ScalarTypeExtensionNode,
) -> str | None:
    """Given a scalar node, return the string value for the specifiedByURL."""
    from ..execution import get_directive_values

    specified_by_url = get_directive_values(GraphQLSpecifiedByDirective, node)
    return specified_by_url["url"] if specified_by_url else None


def is_one_of(node: InputObjectTypeDefinitionNode) -> bool:
    """Given an input object node, returns if the node should be OneOf."""
    from ..execution import get_directive_values

    return get_directive_values(GraphQLOneOfDirective, node) is not None
