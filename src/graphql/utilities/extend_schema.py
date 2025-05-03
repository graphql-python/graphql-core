"""GraphQL schema extension"""

from __future__ import annotations

from collections import defaultdict
from functools import partial
from typing import (
    Any,
    Collection,
    Mapping,
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
    OperationType,
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
    GraphQLInputObjectTypeKwargs,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLInterfaceTypeKwargs,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLNullableType,
    GraphQLObjectType,
    GraphQLObjectTypeKwargs,
    GraphQLOneOfDirective,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLSchemaKwargs,
    GraphQLSpecifiedByDirective,
    GraphQLType,
    GraphQLUnionType,
    GraphQLUnionTypeKwargs,
    assert_schema,
    introspection_types,
    is_enum_type,
    is_input_object_type,
    is_interface_type,
    is_introspection_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
    is_scalar_type,
    is_specified_directive,
    is_specified_scalar_type,
    is_union_type,
    specified_scalar_types,
)
from .value_from_ast import value_from_ast

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
        kind = node.kind
        try:
            kind = kind.removesuffix("_type_extension")
        except AttributeError:  # pragma: no cover (Python < 3.9)
            if kind.endswith("_type_extension"):
                kind = kind[:-15]
        return getattr(self, kind)


class ExtendSchemaImpl:
    """Helper class implementing the methods to extend a schema.

    Note: We use a class instead of an implementation with local functions
    and lambda functions so that the extended schema can be pickled.

    For internal use only.
    """

    type_map: dict[str, GraphQLNamedType]
    type_extensions: TypeExtensionsMap

    def __init__(self, type_extensions: TypeExtensionsMap) -> None:
        self.type_map = {}
        self.type_extensions = type_extensions

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

        self = cls(type_extensions)

        self.type_map = {
            type_.name: self.extend_named_type(type_)
            for type_ in schema_kwargs["types"] or ()
        }

        for type_node in type_defs:
            name = type_node.name.value
            self.type_map[name] = std_type_map.get(name) or self.build_type(type_node)

        # Get the extended root operation types.
        operation_types: dict[OperationType, GraphQLNamedType] = {}
        for operation_type in OperationType:
            original_type = schema_kwargs[operation_type.value]
            if original_type:
                operation_types[operation_type] = self.replace_named_type(original_type)
        # Then, incorporate schema definition and all schema extensions.
        if schema_def:
            operation_types.update(self.get_operation_types([schema_def]))
        if schema_extensions:
            operation_types.update(self.get_operation_types(schema_extensions))

        # Then produce and return the kwargs for a Schema with these types.
        get_operation = operation_types.get
        description = (
            schema_def.description.value
            if schema_def and schema_def.description
            else None
        )
        if description is None:
            description = schema_kwargs["description"]
        return GraphQLSchemaKwargs(
            query=get_operation(OperationType.QUERY),  # type: ignore
            mutation=get_operation(OperationType.MUTATION),  # type: ignore
            subscription=get_operation(OperationType.SUBSCRIPTION),  # type: ignore
            types=tuple(self.type_map.values()),
            directives=tuple(
                self.replace_directive(directive)
                for directive in schema_kwargs["directives"]
            )
            + tuple(self.build_directive(directive) for directive in directive_defs),
            description=description,
            extensions=schema_kwargs["extensions"],
            ast_node=schema_def or schema_kwargs["ast_node"],
            extension_ast_nodes=schema_kwargs["extension_ast_nodes"]
            + tuple(schema_extensions),
            assume_valid=assume_valid,
        )

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def replace_type(self, type_: GraphQLType) -> GraphQLType:
        """Replace a GraphQL type."""
        if is_list_type(type_):
            return GraphQLList(self.replace_type(type_.of_type))
        if is_non_null_type(type_):
            return GraphQLNonNull(self.replace_type(type_.of_type))  # type: ignore
        return self.replace_named_type(type_)  # type: ignore

    def replace_named_type(self, type_: GraphQLNamedType) -> GraphQLNamedType:
        """Replace a named GraphQL type."""
        # Note: While this could make early assertions to get the correctly
        # typed values below, that would throw immediately while type system
        # validation with validate_schema() will produce more actionable results.
        return self.type_map[type_.name]

    # noinspection PyShadowingNames
    def replace_directive(self, directive: GraphQLDirective) -> GraphQLDirective:
        """Replace a GraphQL directive."""
        if is_specified_directive(directive):
            # Builtin directives are not extended.
            return directive

        kwargs = directive.to_kwargs()
        return GraphQLDirective(
            **merge_kwargs(
                kwargs,
                args={
                    name: self.extend_arg(arg) for name, arg in kwargs["args"].items()
                },
            )
        )

    def extend_named_type(self, type_: GraphQLNamedType) -> GraphQLNamedType:
        """Extend a named GraphQL type."""
        if is_introspection_type(type_) or is_specified_scalar_type(type_):
            # Builtin types are not extended.
            return type_
        if is_scalar_type(type_):
            return self.extend_scalar_type(type_)
        if is_object_type(type_):
            return self.extend_object_type(type_)
        if is_interface_type(type_):
            return self.extend_interface_type(type_)
        if is_union_type(type_):
            return self.extend_union_type(type_)
        if is_enum_type(type_):
            return self.extend_enum_type(type_)
        if is_input_object_type(type_):
            return self.extend_input_object_type(type_)

        # Not reachable. All possible types have been considered.
        msg = f"Unexpected type: {inspect(type_)}."  # pragma: no cover
        raise TypeError(msg)  # pragma: no cover

    def extend_input_object_type_fields(
        self, kwargs: GraphQLInputObjectTypeKwargs, extensions: tuple[Any, ...]
    ) -> GraphQLInputFieldMap:
        """Extend GraphQL input object type fields."""
        return {
            **{
                name: GraphQLInputField(
                    **merge_kwargs(
                        field.to_kwargs(),
                        type_=self.replace_type(field.type),
                    )
                )
                for name, field in kwargs["fields"].items()
            },
            **self.build_input_field_map(extensions),
        }

    # noinspection PyShadowingNames
    def extend_input_object_type(
        self,
        type_: GraphQLInputObjectType,
    ) -> GraphQLInputObjectType:
        """Extend a GraphQL input object type."""
        kwargs = type_.to_kwargs()
        extensions = tuple(self.type_extensions.input_object[kwargs["name"]])

        return GraphQLInputObjectType(
            **merge_kwargs(
                kwargs,
                fields=partial(
                    self.extend_input_object_type_fields, kwargs, extensions
                ),
                extension_ast_nodes=kwargs["extension_ast_nodes"] + extensions,
            )
        )

    def extend_enum_type(self, type_: GraphQLEnumType) -> GraphQLEnumType:
        """Extend a GraphQL enum type."""
        kwargs = type_.to_kwargs()
        extensions = tuple(self.type_extensions.enum[kwargs["name"]])

        return GraphQLEnumType(
            **merge_kwargs(
                kwargs,
                values={**kwargs["values"], **self.build_enum_value_map(extensions)},
                extension_ast_nodes=kwargs["extension_ast_nodes"] + extensions,
            )
        )

    def extend_scalar_type(self, type_: GraphQLScalarType) -> GraphQLScalarType:
        """Extend a GraphQL scalar type."""
        kwargs = type_.to_kwargs()
        extensions = tuple(self.type_extensions.scalar[kwargs["name"]])

        specified_by_url = kwargs["specified_by_url"]
        for extension_node in extensions:
            specified_by_url = get_specified_by_url(extension_node) or specified_by_url

        return GraphQLScalarType(
            **merge_kwargs(
                kwargs,
                specified_by_url=specified_by_url,
                extension_ast_nodes=kwargs["extension_ast_nodes"] + extensions,
            )
        )

    def extend_object_type_interfaces(
        self, kwargs: GraphQLObjectTypeKwargs, extensions: tuple[Any, ...]
    ) -> list[GraphQLInterfaceType]:
        """Extend a GraphQL object type interface."""
        return [
            cast("GraphQLInterfaceType", self.replace_named_type(interface))
            for interface in kwargs["interfaces"]
        ] + self.build_interfaces(extensions)

    def extend_object_type_fields(
        self, kwargs: GraphQLObjectTypeKwargs, extensions: tuple[Any, ...]
    ) -> GraphQLFieldMap:
        """Extend GraphQL object type fields."""
        return {
            **{
                name: self.extend_field(field)
                for name, field in kwargs["fields"].items()
            },
            **self.build_field_map(extensions),
        }

    # noinspection PyShadowingNames
    def extend_object_type(self, type_: GraphQLObjectType) -> GraphQLObjectType:
        """Extend a GraphQL object type."""
        kwargs = type_.to_kwargs()
        extensions = tuple(self.type_extensions.object[kwargs["name"]])

        return GraphQLObjectType(
            **merge_kwargs(
                kwargs,
                interfaces=partial(
                    self.extend_object_type_interfaces, kwargs, extensions
                ),
                fields=partial(self.extend_object_type_fields, kwargs, extensions),
                extension_ast_nodes=kwargs["extension_ast_nodes"] + extensions,
            )
        )

    def extend_interface_type_interfaces(
        self, kwargs: GraphQLInterfaceTypeKwargs, extensions: tuple[Any, ...]
    ) -> list[GraphQLInterfaceType]:
        """Extend GraphQL interface type interfaces."""
        return [
            cast("GraphQLInterfaceType", self.replace_named_type(interface))
            for interface in kwargs["interfaces"]
        ] + self.build_interfaces(extensions)

    def extend_interface_type_fields(
        self, kwargs: GraphQLInterfaceTypeKwargs, extensions: tuple[Any, ...]
    ) -> GraphQLFieldMap:
        """Extend GraphQL interface type fields."""
        return {
            **{
                name: self.extend_field(field)
                for name, field in kwargs["fields"].items()
            },
            **self.build_field_map(extensions),
        }

    # noinspection PyShadowingNames
    def extend_interface_type(
        self, type_: GraphQLInterfaceType
    ) -> GraphQLInterfaceType:
        """Extend a GraphQL interface type."""
        kwargs = type_.to_kwargs()
        extensions = tuple(self.type_extensions.interface[kwargs["name"]])

        return GraphQLInterfaceType(
            **merge_kwargs(
                kwargs,
                interfaces=partial(
                    self.extend_interface_type_interfaces, kwargs, extensions
                ),
                fields=partial(self.extend_interface_type_fields, kwargs, extensions),
                extension_ast_nodes=kwargs["extension_ast_nodes"] + extensions,
            )
        )

    def extend_union_type_types(
        self, kwargs: GraphQLUnionTypeKwargs, extensions: tuple[Any, ...]
    ) -> list[GraphQLObjectType]:
        """Extend types of a GraphQL union type."""
        return [
            cast("GraphQLObjectType", self.replace_named_type(member_type))
            for member_type in kwargs["types"]
        ] + self.build_union_types(extensions)

    def extend_union_type(self, type_: GraphQLUnionType) -> GraphQLUnionType:
        """Extend a GraphQL union type."""
        kwargs = type_.to_kwargs()
        extensions = tuple(self.type_extensions.union[kwargs["name"]])

        return GraphQLUnionType(
            **merge_kwargs(
                kwargs,
                types=partial(self.extend_union_type_types, kwargs, extensions),
                extension_ast_nodes=kwargs["extension_ast_nodes"] + extensions,
            ),
        )

    # noinspection PyShadowingNames
    def extend_field(self, field: GraphQLField) -> GraphQLField:
        """Extend a GraphQL field."""
        return GraphQLField(
            **merge_kwargs(
                field.to_kwargs(),
                type_=self.replace_type(field.type),
                args={name: self.extend_arg(arg) for name, arg in field.args.items()},
            )
        )

    def extend_arg(self, arg: GraphQLArgument) -> GraphQLArgument:
        """Extend a GraphQL argument."""
        return GraphQLArgument(
            **merge_kwargs(
                arg.to_kwargs(),
                type_=self.replace_type(arg.type),
            )
        )

    # noinspection PyShadowingNames
    def get_operation_types(
        self, nodes: Collection[SchemaDefinitionNode | SchemaExtensionNode]
    ) -> dict[OperationType, GraphQLNamedType]:
        """Extend GraphQL operation types."""
        # Note: While this could make early assertions to get the correctly
        # typed values below, that would throw immediately while type system
        # validation with validate_schema() will produce more actionable results.
        return {
            operation_type.operation: self.get_named_type(operation_type.type)
            for node in nodes
            for operation_type in node.operation_types or []
        }

    # noinspection PyShadowingNames
    def get_named_type(self, node: NamedTypeNode) -> GraphQLNamedType:
        """Get name GraphQL type for a given named type node."""
        name = node.name.value
        type_ = std_type_map.get(name) or self.type_map.get(name)

        if not type_:
            msg = f"Unknown type: '{name}'."
            raise TypeError(msg)
        return type_

    def get_wrapped_type(self, node: TypeNode) -> GraphQLType:
        """Get wrapped GraphQL type for a given type node."""
        if isinstance(node, ListTypeNode):
            return GraphQLList(self.get_wrapped_type(node.type))
        if isinstance(node, NonNullTypeNode):
            return GraphQLNonNull(
                cast("GraphQLNullableType", self.get_wrapped_type(node.type))
            )
        return self.get_named_type(cast("NamedTypeNode", node))

    def build_directive(self, node: DirectiveDefinitionNode) -> GraphQLDirective:
        """Build a GraphQL directive for a given directive definition node."""
        locations = [DirectiveLocation[node.value] for node in node.locations]

        return GraphQLDirective(
            name=node.name.value,
            description=node.description.value if node.description else None,
            locations=locations,
            is_repeatable=node.repeatable,
            args=self.build_argument_map(node.arguments),
            ast_node=node,
        )

    def build_field_map(
        self,
        nodes: Collection[
            InterfaceTypeDefinitionNode
            | InterfaceTypeExtensionNode
            | ObjectTypeDefinitionNode
            | ObjectTypeExtensionNode
        ],
    ) -> GraphQLFieldMap:
        """Build a GraphQL field map."""
        field_map: GraphQLFieldMap = {}
        for node in nodes:
            for field in node.fields or []:
                # Note: While this could make assertions to get the correctly typed
                # value, that would throw immediately while type system validation
                # with validate_schema() will produce more actionable results.
                field_map[field.name.value] = GraphQLField(
                    type_=cast("GraphQLOutputType", self.get_wrapped_type(field.type)),
                    description=field.description.value if field.description else None,
                    args=self.build_argument_map(field.arguments),
                    deprecation_reason=get_deprecation_reason(field),
                    ast_node=field,
                )
        return field_map

    def build_argument_map(
        self,
        args: Collection[InputValueDefinitionNode] | None,
    ) -> GraphQLArgumentMap:
        """Build a GraphQL argument map."""
        arg_map: GraphQLArgumentMap = {}
        for arg in args or []:
            # Note: While this could make assertions to get the correctly typed
            # value, that would throw immediately while type system validation
            # with validate_schema() will produce more actionable results.
            type_ = cast("GraphQLInputType", self.get_wrapped_type(arg.type))
            arg_map[arg.name.value] = GraphQLArgument(
                type_=type_,
                description=arg.description.value if arg.description else None,
                default_value=value_from_ast(arg.default_value, type_),
                deprecation_reason=get_deprecation_reason(arg),
                ast_node=arg,
            )
        return arg_map

    def build_input_field_map(
        self,
        nodes: Collection[InputObjectTypeDefinitionNode | InputObjectTypeExtensionNode],
    ) -> GraphQLInputFieldMap:
        """Build a GraphQL input field map."""
        input_field_map: GraphQLInputFieldMap = {}
        for node in nodes:
            for field in node.fields or []:
                # Note: While this could make assertions to get the correctly typed
                # value, that would throw immediately while type system validation
                # with validate_schema() will produce more actionable results.
                type_ = cast("GraphQLInputType", self.get_wrapped_type(field.type))
                input_field_map[field.name.value] = GraphQLInputField(
                    type_=type_,
                    description=field.description.value if field.description else None,
                    default_value=value_from_ast(field.default_value, type_),
                    deprecation_reason=get_deprecation_reason(field),
                    ast_node=field,
                )
        return input_field_map

    @staticmethod
    def build_enum_value_map(
        nodes: Collection[EnumTypeDefinitionNode | EnumTypeExtensionNode],
    ) -> GraphQLEnumValueMap:
        """Build a GraphQL enum value map."""
        enum_value_map: GraphQLEnumValueMap = {}
        for node in nodes:
            for value in node.values or []:
                # Note: While this could make assertions to get the correctly typed
                # value, that would throw immediately while type system validation
                # with validate_schema() will produce more actionable results.
                value_name = value.name.value
                enum_value_map[value_name] = GraphQLEnumValue(
                    value=value_name,
                    description=value.description.value if value.description else None,
                    deprecation_reason=get_deprecation_reason(value),
                    ast_node=value,
                )
        return enum_value_map

    def build_interfaces(
        self,
        nodes: Collection[
            InterfaceTypeDefinitionNode
            | InterfaceTypeExtensionNode
            | ObjectTypeDefinitionNode
            | ObjectTypeExtensionNode
        ],
    ) -> list[GraphQLInterfaceType]:
        """Build GraphQL interface types for the given nodes."""
        # Note: While this could make assertions to get the correctly typed
        # value, that would throw immediately while type system validation
        # with validate_schema() will produce more actionable results.
        return [
            cast("GraphQLInterfaceType", self.get_named_type(type_))
            for node in nodes
            for type_ in node.interfaces or []
        ]

    def build_union_types(
        self,
        nodes: Collection[UnionTypeDefinitionNode | UnionTypeExtensionNode],
    ) -> list[GraphQLObjectType]:
        """Build GraphQL object types for the given union type nodes."""
        # Note: While this could make assertions to get the correctly typed
        # value, that would throw immediately while type system validation
        # with validate_schema() will produce more actionable results.
        return [
            cast("GraphQLObjectType", self.get_named_type(type_))
            for node in nodes
            for type_ in node.types or []
        ]

    def build_object_type(
        self, ast_node: ObjectTypeDefinitionNode
    ) -> GraphQLObjectType:
        """Build a GraphQL object type for the given object type definition node."""
        extension_nodes = self.type_extensions.object[ast_node.name.value]
        all_nodes: list[ObjectTypeDefinitionNode | ObjectTypeExtensionNode] = [
            ast_node,
            *extension_nodes,
        ]
        return GraphQLObjectType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            interfaces=partial(self.build_interfaces, all_nodes),
            fields=partial(self.build_field_map, all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def build_interface_type(
        self,
        ast_node: InterfaceTypeDefinitionNode,
    ) -> GraphQLInterfaceType:
        """Build a GraphQL interface type for the given type definition nodes."""
        extension_nodes = self.type_extensions.interface[ast_node.name.value]
        all_nodes: list[InterfaceTypeDefinitionNode | InterfaceTypeExtensionNode] = [
            ast_node,
            *extension_nodes,
        ]
        return GraphQLInterfaceType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            interfaces=partial(self.build_interfaces, all_nodes),
            fields=partial(self.build_field_map, all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def build_enum_type(self, ast_node: EnumTypeDefinitionNode) -> GraphQLEnumType:
        """Build a GraphQL enum type for the given enum type definition nodes."""
        extension_nodes = self.type_extensions.enum[ast_node.name.value]
        all_nodes: list[EnumTypeDefinitionNode | EnumTypeExtensionNode] = [
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

    def build_union_type(self, ast_node: UnionTypeDefinitionNode) -> GraphQLUnionType:
        """Build a GraphQL union type for the given union type definition nodes."""
        extension_nodes = self.type_extensions.union[ast_node.name.value]
        all_nodes: list[UnionTypeDefinitionNode | UnionTypeExtensionNode] = [
            ast_node,
            *extension_nodes,
        ]
        return GraphQLUnionType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            types=partial(self.build_union_types, all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def build_scalar_type(
        self, ast_node: ScalarTypeDefinitionNode
    ) -> GraphQLScalarType:
        """Build a GraphQL scalar type for the given scalar type definition node."""
        extension_nodes = self.type_extensions.scalar[ast_node.name.value]
        return GraphQLScalarType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            specified_by_url=get_specified_by_url(ast_node),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
        )

    def build_input_object_type(
        self,
        ast_node: InputObjectTypeDefinitionNode,
    ) -> GraphQLInputObjectType:
        """Build a GraphQL input object type for the given node."""
        extension_nodes = self.type_extensions.input_object[ast_node.name.value]
        all_nodes: list[
            InputObjectTypeDefinitionNode | InputObjectTypeExtensionNode
        ] = [ast_node, *extension_nodes]
        return GraphQLInputObjectType(
            name=ast_node.name.value,
            description=ast_node.description.value if ast_node.description else None,
            fields=partial(self.build_input_field_map, all_nodes),
            ast_node=ast_node,
            extension_ast_nodes=extension_nodes,
            is_one_of=is_one_of(ast_node),
        )

    def build_type(self, ast_node: TypeDefinitionNode) -> GraphQLNamedType:
        """Build a named GraphQL type for the given type definition node."""
        kind = ast_node.kind
        try:
            kind = kind.removesuffix("_definition")
        except AttributeError:  # pragma: no cover (Python < 3.9)
            if kind.endswith("_definition"):
                kind = kind[:-11]
        try:
            build = getattr(self, f"build_{kind}")
        except AttributeError as error:  # pragma: no cover
            # Not reachable. All possible type definition nodes have been considered.
            msg = (  # pragma: no cover
                f"Unexpected type definition node: {inspect(ast_node)}."
            )
            raise TypeError(msg) from error  # pragma: no cover
        return build(ast_node)


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
