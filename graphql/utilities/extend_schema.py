from collections import defaultdict
from functools import partial
from itertools import chain
from typing import Any, Callable, Dict, List, Optional, Union, Tuple, cast

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
    GraphQLArgumentMap,
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
    type_definition_map: Dict[str, Any] = {}
    type_extensions_map: Dict[str, Any] = defaultdict(list)

    # New directives and types are separate because a directives and types can have the
    # same name. For example, a type named "skip".
    directive_definitions: List[DirectiveDefinitionNode] = []

    schema_def: Optional[SchemaDefinitionNode] = None
    # Schema extensions are collected which may add additional operation types.
    schema_extensions: List[SchemaExtensionNode] = []

    for def_ in document_ast.definitions:
        if isinstance(def_, SchemaDefinitionNode):
            schema_def = def_
        elif isinstance(def_, SchemaExtensionNode):
            schema_extensions.append(def_)
        elif isinstance(def_, TypeDefinitionNode):
            type_name = def_.name.value
            type_definition_map[type_name] = def_
        elif isinstance(def_, TypeExtensionNode):
            extended_type_name = def_.name.value
            type_extensions_map[extended_type_name].append(def_)
        elif isinstance(def_, DirectiveDefinitionNode):
            directive_definitions.append(def_)

    # If this document contains no new types, extensions, or directives then return the
    # same unmodified GraphQLSchema instance.
    if (
        not type_extensions_map
        and not type_definition_map
        and not directive_definitions
        and not schema_extensions
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
                map(ast_builder.build_directive, directive_definitions),
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
        return GraphQLDirective(
            directive.name,
            description=directive.description,
            locations=directive.locations,
            args=extend_args(directive.args),
            ast_node=directive.ast_node,
        )

    def extend_input_object_type(
        type_: GraphQLInputObjectType
    ) -> GraphQLInputObjectType:
        name = type_.name
        extension_ast_nodes = (
            (
                list(type_.extension_ast_nodes) + type_extensions_map[name]
                if type_.extension_ast_nodes
                else type_extensions_map[name]
            )
            if name in type_extensions_map
            else type_.extension_ast_nodes
        )
        return GraphQLInputObjectType(
            name,
            description=type_.description,
            fields=lambda: extend_input_field_map(type_),
            ast_node=type_.ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )

    def extend_input_field_map(type_: GraphQLInputObjectType) -> GraphQLInputFieldMap:
        new_field_map = {
            field_name: GraphQLInputField(
                cast(GraphQLInputType, extend_type(field.type)),
                description=field.description,
                default_value=field.default_value,
                ast_node=field.ast_node,
            )
            for field_name, field in type_.fields.items()
        }

        # If there are any extensions to the fields, apply those here.
        extensions = type_extensions_map.get(type_.name)
        if extensions:
            build_input_field = ast_builder.build_input_field
            for extension in extensions:
                for field in extension.fields:
                    new_field_map[field.name.value] = build_input_field(field)

        return new_field_map

    def extend_enum_type(type_: GraphQLEnumType) -> GraphQLEnumType:
        name = type_.name
        extension_ast_nodes = (
            (
                list(type_.extension_ast_nodes) + type_extensions_map[name]
                if type_.extension_ast_nodes
                else type_extensions_map[name]
            )
            if name in type_extensions_map
            else type_.extension_ast_nodes
        )
        return GraphQLEnumType(
            name,
            description=type_.description,
            values=extend_value_map(type_),
            ast_node=type_.ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )

    def extend_value_map(type_: GraphQLEnumType) -> GraphQLEnumValueMap:
        new_value_map = {
            value_name: GraphQLEnumValue(
                value.value,
                description=value.description,
                deprecation_reason=value.deprecation_reason,
                ast_node=value.ast_node,
            )
            for value_name, value in type_.values.items()
        }

        # If there are any extensions to the values, apply those here.
        extensions = type_extensions_map.get(type_.name)
        if extensions:
            build_enum_value = ast_builder.build_enum_value
            for extension in extensions:
                for value in extension.values:
                    new_value_map[value.name.value] = build_enum_value(value)

        return new_value_map

    def extend_scalar_type(type_: GraphQLScalarType) -> GraphQLScalarType:
        name = type_.name
        extension_ast_nodes = (
            (
                list(type_.extension_ast_nodes) + type_extensions_map[name]
                if type_.extension_ast_nodes
                else type_extensions_map[name]
            )
            if name in type_extensions_map
            else type_.extension_ast_nodes
        )
        return GraphQLScalarType(
            name,
            serialize=type_.serialize,
            description=type_.description,
            parse_value=type_.parse_value,
            parse_literal=type_.parse_literal,
            ast_node=type_.ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )

    def extend_object_type(type_: GraphQLObjectType) -> GraphQLObjectType:
        name = type_.name
        extension_ast_nodes = type_.extension_ast_nodes
        try:
            extensions = type_extensions_map[name]
        except KeyError:
            pass
        else:
            if extension_ast_nodes:
                extension_ast_nodes = list(extension_ast_nodes) + extensions
            else:
                extension_ast_nodes = extensions
        return GraphQLObjectType(
            type_.name,
            description=type_.description,
            interfaces=partial(extend_implemented_interfaces, type_),
            fields=partial(extend_field_map, type_),
            ast_node=type_.ast_node,
            extension_ast_nodes=extension_ast_nodes,
            is_type_of=type_.is_type_of,
        )

    def extend_args(args: GraphQLArgumentMap) -> GraphQLArgumentMap:
        return {
            arg_name: GraphQLArgument(
                cast(GraphQLInputType, extend_type(arg.type)),
                default_value=arg.default_value,
                description=arg.description,
                ast_node=arg.ast_node,
            )
            for arg_name, arg in args.items()
        }

    def extend_interface_type(type_: GraphQLInterfaceType) -> GraphQLInterfaceType:
        name = type_.name
        extension_ast_nodes = type_.extension_ast_nodes
        try:
            extensions = type_extensions_map[name]
        except KeyError:
            pass
        else:
            if extension_ast_nodes:
                extension_ast_nodes = list(extension_ast_nodes) + extensions
            else:
                extension_ast_nodes = extensions
        return GraphQLInterfaceType(
            type_.name,
            description=type_.description,
            fields=partial(extend_field_map, type_),
            ast_node=type_.ast_node,
            extension_ast_nodes=extension_ast_nodes,
            resolve_type=type_.resolve_type,
        )

    def extend_union_type(type_: GraphQLUnionType) -> GraphQLUnionType:
        name = type_.name
        extension_ast_nodes = (
            (
                list(type_.extension_ast_nodes) + type_extensions_map[name]
                if type_.extension_ast_nodes
                else type_extensions_map[name]
            )
            if name in type_extensions_map
            else type_.extension_ast_nodes
        )
        return GraphQLUnionType(
            name,
            description=type_.description,
            types=lambda: extend_possible_types(type_),
            ast_node=type_.ast_node,
            resolve_type=type_.resolve_type,
            extension_ast_nodes=extension_ast_nodes,
        )

    def extend_possible_types(type_: GraphQLUnionType) -> List[GraphQLObjectType]:
        possible_types = list(map(extend_named_type, type_.types))

        # If there are any extensions to the union, apply those here.
        extensions = type_extensions_map.get(type_.name)
        if extensions:
            for extension in extensions:
                for named_type in extension.types:
                    # Note: While this could make early assertions to get the correctly
                    # typed values, that would throw immediately while type system
                    # validation with `validate_schema()` will produce more actionable
                    # results.
                    possible_types.append(build_type(named_type))

        return cast(List[GraphQLObjectType], possible_types)

    def extend_implemented_interfaces(
        type_: GraphQLObjectType
    ) -> List[GraphQLInterfaceType]:
        interfaces: List[GraphQLInterfaceType] = list(
            map(
                cast(
                    Callable[[GraphQLNamedType], GraphQLInterfaceType],
                    extend_named_type,
                ),
                type_.interfaces,
            )
        )

        # If there are any extensions to the interfaces, apply those here.
        for extension in type_extensions_map[type_.name]:
            for named_type in extension.interfaces:
                # Note: While this could make early assertions to get the correctly
                # typed values, that would throw immediately while type system
                # validation with `validate_schema()` will produce more actionable
                # results.
                interfaces.append(cast(GraphQLInterfaceType, build_type(named_type)))

        return interfaces

    def extend_field_map(
        type_: Union[GraphQLObjectType, GraphQLInterfaceType]
    ) -> GraphQLFieldMap:
        new_field_map = {
            field_name: GraphQLField(
                cast(GraphQLObjectType, extend_type(field.type)),
                description=field.description,
                deprecation_reason=field.deprecation_reason,
                args=extend_args(field.args),
                ast_node=field.ast_node,
                resolve=field.resolve,
            )
            for field_name, field in type_.fields.items()
        }

        # If there are any extensions to the fields, apply those here.
        build_field = ast_builder.build_field
        for extension in type_extensions_map[type_.name]:
            for field in extension.fields:
                new_field_map[field.name.value] = build_field(field)

        return new_field_map

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
        type_definition_map, assume_valid=assume_valid, resolve_type=resolve_type
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
    for schema_extension in schema_extensions:
        if schema_extension.operation_types:
            for operation_type in schema_extension.operation_types:
                operation = operation_type.operation
                # Note: While this could make early assertions to get the correctly
                # typed values, that would throw immediately while type system
                # validation with `validate_schema()` will produce more actionable
                # results.
                operation_types[operation] = build_type(operation_type.type)

    schema_extension_ast_nodes = (
        schema.extension_ast_nodes or cast(Tuple[SchemaExtensionNode], ())
    ) + tuple(schema_extensions)

    # Iterate through all types, getting the type definition for each, ensuring that
    # any type not directly referenced by a value will get created.
    types = list(map(extend_named_type, schema.type_map.values()))
    # do the same with new types
    types.extend(map(build_type, type_definition_map.values()))

    # Then produce and return a Schema with these types.
    return GraphQLSchema(  # type: ignore
        query=operation_types[OperationType.QUERY],
        mutation=operation_types[OperationType.MUTATION],
        subscription=operation_types[OperationType.SUBSCRIPTION],
        types=types,
        directives=get_merged_directives(),
        ast_node=schema.ast_node,
        extension_ast_nodes=schema_extension_ast_nodes,
    )
