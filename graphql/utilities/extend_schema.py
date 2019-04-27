from collections import defaultdict
from itertools import chain
from typing import Any, Dict, List, Optional, Tuple, cast

from ..language import (
    DirectiveDefinitionNode,
    DocumentNode,
    OperationType,
    SchemaExtensionNode,
    SchemaDefinitionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
)
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
        "Must provide valid Document AST"

    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl_extension

        assert_valid_sdl_extension(document_ast, schema)

    # Collect the type definitions and extensions found in the document.
    type_def_map: Dict[str, Any] = {}
    type_exts_map: Dict[str, Any] = defaultdict(list)

    # New directives and types are separate because a directives and types can have the
    # same name. For example, a type named "skip".
    directive_defs: List[DirectiveDefinitionNode] = []

    schema_def: Optional[SchemaDefinitionNode] = None
    # Schema extensions are collected which may add additional operation types.
    schema_exts: List[SchemaExtensionNode] = []

    for def_ in document_ast.definitions:
        if isinstance(def_, SchemaDefinitionNode):
            schema_def = def_
        elif isinstance(def_, SchemaExtensionNode):
            schema_exts.append(def_)
        elif isinstance(def_, TypeDefinitionNode):
            type_name = def_.name.value
            type_def_map[type_name] = def_
        elif isinstance(def_, TypeExtensionNode):
            extended_type_name = def_.name.value
            type_exts_map[extended_type_name].append(def_)
        elif isinstance(def_, DirectiveDefinitionNode):
            directive_defs.append(def_)

    # If this document contains no new types, extensions, or directives then return the
    # same unmodified GraphQLSchema instance.
    if (
        not type_exts_map
        and not type_def_map
        and not directive_defs
        and not schema_exts
        and not schema_def
    ):
        return schema

    # Below are functions used for producing this schema that have closed over this
    # scope and have access to the schema, cache, and newly defined types.

    def get_merged_directives() -> List[GraphQLDirective]:
        if not schema.directives:
            raise TypeError("schema must have default directives")

        return list(
            chain(
                map(extend_directive, schema.directives),
                map(ast_builder.build_directive, directive_defs),
            )
        )

    def extend_maybe_named_type(
        type_: Optional[GraphQLNamedType]
    ) -> Optional[GraphQLNamedType]:
        return extend_named_type(type_) if type_ else None

    def extend_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        if is_introspection_type(type_) or is_specified_scalar_type(type_):
            # Builtin types are not extended.
            return type_

        name = type_.name
        if name not in extend_type_cache:
            if is_scalar_type(type_):
                type_ = cast(GraphQLScalarType, type_)
                extend_type_cache[name] = extend_scalar_type(type_)
            elif is_object_type(type_):
                type_ = cast(GraphQLObjectType, type_)
                extend_type_cache[name] = extend_object_type(type_)
            elif is_interface_type(type_):
                type_ = cast(GraphQLInterfaceType, type_)
                extend_type_cache[name] = extend_interface_type(type_)
            elif is_enum_type(type_):
                type_ = cast(GraphQLEnumType, type_)
                extend_type_cache[name] = extend_enum_type(type_)
            elif is_input_object_type(type_):
                type_ = cast(GraphQLInputObjectType, type_)
                extend_type_cache[name] = extend_input_object_type(type_)
            elif is_union_type(type_):
                type_ = cast(GraphQLUnionType, type_)
                extend_type_cache[name] = extend_union_type(type_)

        return extend_type_cache[name]

    def extend_directive(directive: GraphQLDirective) -> GraphQLDirective:
        kwargs = directive.to_kwargs()
        return GraphQLDirective(  # type: ignore
            **{
                **kwargs,
                "args": {name: extend_arg(arg) for name, arg in kwargs["args"].items()},
            }
        )

    def extend_input_object_type(
        type_: GraphQLInputObjectType
    ) -> GraphQLInputObjectType:
        kwargs = type_.to_kwargs()
        extensions = type_exts_map.get(kwargs["name"], [])
        field_nodes = chain.from_iterable(node.fields or [] for node in extensions)

        return GraphQLInputObjectType(
            **{
                **kwargs,
                "fields": lambda: {
                    **{
                        name: GraphQLInputField(  # type: ignore
                            **{**field.to_kwargs(), "type_": extend_type(field.type)}
                        )
                        for name, field in kwargs["fields"].items()
                    },
                    **{
                        field.name.value: ast_builder.build_input_field(field)
                        for field in field_nodes
                    },
                },
                "extension_ast_nodes": kwargs["extension_ast_nodes"]
                + tuple(extensions),
            }
        )

    def extend_enum_type(type_: GraphQLEnumType) -> GraphQLEnumType:
        kwargs = type_.to_kwargs()
        extensions = type_exts_map.get(kwargs["name"], [])
        value_nodes = chain.from_iterable(node.values or [] for node in extensions)

        return GraphQLEnumType(
            **{
                **kwargs,
                "values": {
                    **kwargs["values"],
                    **{
                        value.name.value: ast_builder.build_enum_value(value)
                        for value in value_nodes
                    },
                },
                "extension_ast_nodes": kwargs["extension_ast_nodes"]
                + tuple(extensions),
            }
        )

    def extend_scalar_type(type_: GraphQLScalarType) -> GraphQLScalarType:
        kwargs = type_.to_kwargs()
        extensions = type_exts_map.get(kwargs["name"], [])

        return GraphQLScalarType(
            **{
                **kwargs,
                "extension_ast_nodes": kwargs["extension_ast_nodes"]
                + tuple(extensions),
            }
        )

    def extend_object_type(type_: GraphQLObjectType) -> GraphQLObjectType:
        kwargs = type_.to_kwargs()
        extensions = type_exts_map.get(kwargs["name"], [])
        interface_nodes = chain.from_iterable(
            node.interfaces or [] for node in extensions
        )
        field_nodes = chain.from_iterable(node.fields or [] for node in extensions)

        return GraphQLObjectType(
            **{
                **kwargs,
                "interfaces": lambda: [
                    extend_named_type(interface) for interface in kwargs["interfaces"]
                ]
                # Note: While this could make early assertions to get the correctly
                # typed values, that would throw immediately while type system
                # validation with validate_schema will produce more actionable results.
                + [build_type(node) for node in interface_nodes],
                "fields": lambda: {
                    **{
                        name: extend_field(field)
                        for name, field in kwargs["fields"].items()
                    },
                    **{
                        node.name.value: ast_builder.build_field(node)
                        for node in field_nodes
                    },
                },
                "extension_ast_nodes": kwargs["extension_ast_nodes"]
                + tuple(extensions),
            }
        )

    def extend_interface_type(type_: GraphQLInterfaceType) -> GraphQLInterfaceType:
        kwargs = type_.to_kwargs()
        extensions = type_exts_map.get(kwargs["name"], [])
        field_nodes = chain.from_iterable(node.fields or [] for node in extensions)

        return GraphQLInterfaceType(
            **{
                **kwargs,
                "fields": lambda: {
                    **{
                        name: extend_field(field)
                        for name, field in kwargs["fields"].items()
                    },
                    **{
                        node.name.value: ast_builder.build_field(node)
                        for node in field_nodes
                    },
                },
                "extension_ast_nodes": kwargs["extension_ast_nodes"]
                + tuple(extensions),
            }
        )

    def extend_union_type(type_: GraphQLUnionType) -> GraphQLUnionType:
        kwargs = type_.to_kwargs()
        extensions = type_exts_map.get(kwargs["name"], [])
        type_nodes = chain.from_iterable(node.types or [] for node in extensions)

        return GraphQLUnionType(
            **{
                **kwargs,
                "types": lambda: [
                    extend_named_type(member_type) for member_type in kwargs["types"]
                ]
                # Note: While this could make early assertions to get the correctly
                # typed values, that would throw immediately while type system
                # validation with validate_schema will produce more actionable results.
                + [build_type(node) for node in type_nodes],
                "extension_ast_nodes": kwargs["extension_ast_nodes"]
                + tuple(extensions),
            }
        )

    def extend_field(field: GraphQLField) -> GraphQLField:
        return GraphQLField(  # type: ignore
            **{
                **field.to_kwargs(),
                "type_": extend_type(field.type),
                "args": {name: extend_arg(arg) for name, arg in field.args.items()},
            }
        )

    def extend_arg(arg: GraphQLArgument) -> GraphQLArgument:
        return GraphQLArgument(  # type: ignore
            **{**arg.to_kwargs(), "type_": extend_type(arg.type)}
        )

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def extend_type(type_def: GraphQLType) -> GraphQLType:
        if is_list_type(type_def):
            return GraphQLList(extend_type(type_def.of_type))  # type: ignore
        if is_non_null_type(type_def):
            return GraphQLNonNull(extend_type(type_def.of_type))  # type: ignore
        return extend_named_type(type_def)  # type: ignore

    # noinspection PyShadowingNames
    def resolve_type(type_name: str) -> GraphQLNamedType:
        existing_type = schema.get_type(type_name)
        if not existing_type:
            raise TypeError(f"Unknown type: '{type_name}'.")
        return extend_named_type(existing_type)

    ast_builder = ASTDefinitionBuilder(
        type_def_map, assume_valid=assume_valid, resolve_type=resolve_type
    )
    build_type = ast_builder.build_type

    extend_type_cache: Dict[str, GraphQLNamedType] = {}

    # Get the extended root operation types.
    operation_types = {
        OperationType.QUERY: extend_maybe_named_type(schema.query_type),
        OperationType.MUTATION: extend_maybe_named_type(schema.mutation_type),
        OperationType.SUBSCRIPTION: extend_maybe_named_type(schema.subscription_type),
    }

    if schema_def:
        for operation_type in schema_def.operation_types:
            operation = operation_type.operation
            # Note: While this could make early assertions to get the correctly typed
            # values, that would throw immediately while type system validation with
            # `validate_schema()` will produce more actionable results.
            operation_types[operation] = build_type(operation_type.type)

    # Then, incorporate schema definition and all schema extensions.
    for schema_ext in schema_exts:
        if schema_ext.operation_types:
            for operation_type in schema_ext.operation_types:
                operation = operation_type.operation
                # Note: While this could make early assertions to get the correctly
                # typed values, that would throw immediately while type system
                # validation with `validate_schema()` will produce more actionable
                # results.
                operation_types[operation] = build_type(operation_type.type)

    # Iterate through all types, getting the type definition for each, ensuring that
    # any type not directly referenced by a value will get created.
    schema_types = list(map(extend_named_type, schema.type_map.values()))
    # do the same with new types
    schema_types.extend(map(build_type, type_def_map.values()))

    # Then produce and return a Schema with these types.
    return GraphQLSchema(  # type: ignore
        query=operation_types[OperationType.QUERY],
        mutation=operation_types[OperationType.MUTATION],
        subscription=operation_types[OperationType.SUBSCRIPTION],
        types=schema_types,
        directives=get_merged_directives(),
        ast_node=schema.ast_node,
        extension_ast_nodes=(
            schema.extension_ast_nodes or cast(Tuple[SchemaExtensionNode], ())
        )
        + tuple(schema_exts),
    )
