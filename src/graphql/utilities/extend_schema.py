from collections import defaultdict
from typing import Any, Dict, List, Optional, cast

from ..language import (
    DirectiveDefinitionNode,
    DocumentNode,
    OperationType,
    SchemaExtensionNode,
    SchemaDefinitionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
)
from ..pyutils import inspect, FrozenList
from ..type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
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
)
from .build_ast_schema import ASTDefinitionBuilder

__all__ = ["extend_schema"]


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
    type_extensions_map: Dict[str, Any] = defaultdict(list)

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

    ast_builder = ASTDefinitionBuilder(
        assume_valid=assume_valid, resolve_type=resolve_type
    )

    type_map = ast_builder.build_type_map(type_defs)
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
