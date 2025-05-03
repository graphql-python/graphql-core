"""GraphQL schemas"""

from __future__ import annotations

from copy import copy, deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    Collection,
    Dict,
    NamedTuple,
    cast,
)

if TYPE_CHECKING:
    from ..error import GraphQLError
    from ..language import OperationType, ast

from ..pyutils import inspect
from .definition import (
    GraphQLAbstractType,
    GraphQLCompositeType,
    GraphQLField,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLType,
    get_named_type,
    is_input_object_type,
    is_interface_type,
    is_object_type,
    is_union_type,
    is_wrapping_type,
)
from .directives import GraphQLDirective, is_directive, specified_directives
from .introspection import (
    SchemaMetaFieldDef,
    TypeMetaFieldDef,
    TypeNameMetaFieldDef,
    introspection_types,
)

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict
try:
    from typing import TypeAlias, TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias, TypeGuard

__all__ = ["GraphQLSchema", "GraphQLSchemaKwargs", "assert_schema", "is_schema"]

TypeMap: TypeAlias = Dict[str, GraphQLNamedType]


class InterfaceImplementations(NamedTuple):
    objects: list[GraphQLObjectType]
    interfaces: list[GraphQLInterfaceType]


class GraphQLSchemaKwargs(TypedDict, total=False):
    """Arguments for GraphQL schemas"""

    query: GraphQLObjectType | None
    mutation: GraphQLObjectType | None
    subscription: GraphQLObjectType | None
    types: tuple[GraphQLNamedType, ...] | None
    directives: tuple[GraphQLDirective, ...]
    description: str | None
    extensions: dict[str, Any]
    ast_node: ast.SchemaDefinitionNode | None
    extension_ast_nodes: tuple[ast.SchemaExtensionNode, ...]
    assume_valid: bool


class GraphQLSchema:
    """Schema Definition

    A Schema is created by supplying the root types of each type of operation, query
    and mutation (optional). A schema definition is then supplied to the validator
    and executor.

    Schemas should be considered immutable once they are created. If you want to modify
    a schema, modify the result of the ``to_kwargs()`` method and recreate the schema.

    Example::

        MyAppSchema = GraphQLSchema(
          query=MyAppQueryRootType,
          mutation=MyAppMutationRootType)

    Note: When the schema is constructed, by default only the types that are
    reachable by traversing the root types are included, other types must be
    explicitly referenced.

    Example::

        character_interface = GraphQLInterfaceType('Character', ...)

        human_type = GraphQLObjectType(
            'Human', interfaces=[character_interface], ...)

        droid_type = GraphQLObjectType(
            'Droid', interfaces: [character_interface], ...)

        schema = GraphQLSchema(
            query=GraphQLObjectType('Query',
                fields={'hero': GraphQLField(character_interface, ....)}),
            ...
            # Since this schema references only the `Character` interface it's
            # necessary to explicitly list the types that implement it if
            # you want them to be included in the final schema.
            types=[human_type, droid_type])

    Note: If a list of ``directives`` is provided to GraphQLSchema, that will be the
    exact list of directives represented and allowed. If ``directives`` is not provided,
    then a default set of the specified directives (e.g. @include and @skip) will be
    used. If you wish to provide *additional* directives to these specified directives,
    you must explicitly declare them. Example::

        MyAppSchema = GraphQLSchema(
          ...
          directives=specified_directives + [my_custom_directive])
    """

    query_type: GraphQLObjectType | None
    mutation_type: GraphQLObjectType | None
    subscription_type: GraphQLObjectType | None
    type_map: TypeMap
    directives: tuple[GraphQLDirective, ...]
    description: str | None
    extensions: dict[str, Any]
    ast_node: ast.SchemaDefinitionNode | None
    extension_ast_nodes: tuple[ast.SchemaExtensionNode, ...]

    _implementations_map: dict[str, InterfaceImplementations]
    _sub_type_map: dict[str, set[str]]
    _validation_errors: list[GraphQLError] | None

    def __init__(
        self,
        query: GraphQLObjectType | None = None,
        mutation: GraphQLObjectType | None = None,
        subscription: GraphQLObjectType | None = None,
        types: Collection[GraphQLNamedType] | None = None,
        directives: Collection[GraphQLDirective] | None = None,
        description: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: ast.SchemaDefinitionNode | None = None,
        extension_ast_nodes: Collection[ast.SchemaExtensionNode] | None = None,
        assume_valid: bool = False,
    ) -> None:
        """Initialize GraphQL schema.

        If this schema was built from a source known to be valid, then it may be marked
        with ``assume_valid`` to avoid an additional type system validation.
        """
        self._validation_errors = [] if assume_valid else None

        self.description = description
        self.extensions = extensions or {}
        self.ast_node = ast_node
        self.extension_ast_nodes = (
            tuple(extension_ast_nodes) if extension_ast_nodes else ()
        )
        self.query_type = query
        self.mutation_type = mutation
        self.subscription_type = subscription
        # Provide specified directives (e.g. @include and @skip) by default
        self.directives = (
            specified_directives if directives is None else tuple(directives)
        )

        # To preserve order of user-provided types, we first add them to the set
        # of "collected" types, so `collect_referenced_types` ignores them.
        if types:
            all_referenced_types = TypeSet.with_initial_types(types)
            collect_referenced_types = all_referenced_types.collect_referenced_types
            for type_ in types:
                # When we are ready to process this type, we remove it from "collected"
                # types and then add it together with all dependent types in the correct
                # position.
                del all_referenced_types[type_]
                collect_referenced_types(type_)
        else:
            all_referenced_types = TypeSet()
            collect_referenced_types = all_referenced_types.collect_referenced_types

        if query:
            collect_referenced_types(query)
        if mutation:
            collect_referenced_types(mutation)
        if subscription:
            collect_referenced_types(subscription)

        for directive in self.directives:
            # Directives are not validated until validate_schema() is called.
            if is_directive(directive):
                for arg in directive.args.values():
                    collect_referenced_types(arg.type)
        collect_referenced_types(introspection_types["__Schema"])

        # Storing the resulting map for reference by the schema.
        type_map: TypeMap = {}
        self.type_map = type_map

        self._sub_type_map = {}

        # Keep track of all implementations by interface name.
        implementations_map: dict[str, InterfaceImplementations] = {}
        self._implementations_map = implementations_map

        for named_type in all_referenced_types:
            if not named_type:
                continue

            type_name = getattr(named_type, "name", None)
            if not type_name:
                msg = (
                    "One of the provided types for building the Schema"
                    " is missing a name."
                )
                raise TypeError(msg)
            if type_name in type_map:
                msg = (
                    "Schema must contain uniquely named types"
                    f" but contains multiple types named '{type_name}'."
                )
                raise TypeError(msg)

            type_map[type_name] = named_type

            if is_interface_type(named_type):
                # Store implementations by interface.
                for iface in named_type.interfaces:
                    if is_interface_type(iface):
                        if iface.name in implementations_map:
                            implementations = implementations_map[iface.name]
                        else:
                            implementations = implementations_map[iface.name] = (
                                InterfaceImplementations(objects=[], interfaces=[])
                            )

                        implementations.interfaces.append(named_type)
            elif is_object_type(named_type):
                # Store implementations by objects.
                for iface in named_type.interfaces:
                    if is_interface_type(iface):
                        if iface.name in implementations_map:
                            implementations = implementations_map[iface.name]
                        else:
                            implementations = implementations_map[iface.name] = (
                                InterfaceImplementations(objects=[], interfaces=[])
                            )

                        implementations.objects.append(named_type)

    def to_kwargs(self) -> GraphQLSchemaKwargs:
        """Get corresponding arguments."""
        return GraphQLSchemaKwargs(
            query=self.query_type,
            mutation=self.mutation_type,
            subscription=self.subscription_type,
            types=tuple(self.type_map.values()) or None,
            directives=self.directives,
            description=self.description,
            extensions=self.extensions,
            ast_node=self.ast_node,
            extension_ast_nodes=self.extension_ast_nodes,
            assume_valid=self._validation_errors is not None,
        )

    def __copy__(self) -> GraphQLSchema:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    def __deepcopy__(self, memo_: dict) -> GraphQLSchema:
        from ..type import (
            is_introspection_type,
            is_specified_directive,
            is_specified_scalar_type,
        )

        type_map: TypeMap = {
            name: copy(type_)
            for name, type_ in self.type_map.items()
            if not is_introspection_type(type_) and not is_specified_scalar_type(type_)
        }
        types = type_map.values()
        for type_ in types:
            remap_named_type(type_, type_map)
        directives = [
            directive if is_specified_directive(directive) else copy(directive)
            for directive in self.directives
        ]
        for directive in directives:
            remap_directive(directive, type_map)
        return self.__class__(
            self.query_type
            and cast("GraphQLObjectType", type_map[self.query_type.name]),
            self.mutation_type
            and cast("GraphQLObjectType", type_map[self.mutation_type.name]),
            self.subscription_type
            and cast("GraphQLObjectType", type_map[self.subscription_type.name]),
            types,
            directives,
            self.description,
            extensions=deepcopy(self.extensions),
            ast_node=deepcopy(self.ast_node),
            extension_ast_nodes=deepcopy(self.extension_ast_nodes),
            assume_valid=True,
        )

    def get_root_type(self, operation: OperationType) -> GraphQLObjectType | None:
        """Get the root type."""
        return getattr(self, f"{operation.value}_type")

    def get_type(self, name: str) -> GraphQLNamedType | None:
        """Get the type with the given name."""
        return self.type_map.get(name)

    def get_possible_types(
        self, abstract_type: GraphQLAbstractType
    ) -> list[GraphQLObjectType]:
        """Get list of all possible concrete types for given abstract type."""
        return (
            abstract_type.types
            if is_union_type(abstract_type)
            else self.get_implementations(
                cast("GraphQLInterfaceType", abstract_type)
            ).objects
        )

    def get_implementations(
        self, interface_type: GraphQLInterfaceType
    ) -> InterfaceImplementations:
        """Get implementations for the given interface type."""
        return self._implementations_map.get(
            interface_type.name, InterfaceImplementations(objects=[], interfaces=[])
        )

    def is_sub_type(
        self,
        abstract_type: GraphQLAbstractType,
        maybe_sub_type: GraphQLNamedType,
    ) -> bool:
        """Check whether a type is a subtype of a given abstract type."""
        types = self._sub_type_map.get(abstract_type.name)
        if types is None:
            types = set()
            add = types.add
            if is_union_type(abstract_type):
                for type_ in abstract_type.types:
                    add(type_.name)
            else:
                implementations = self.get_implementations(
                    cast("GraphQLInterfaceType", abstract_type)
                )
                for type_ in implementations.objects:
                    add(type_.name)
                for type_ in implementations.interfaces:
                    add(type_.name)
            self._sub_type_map[abstract_type.name] = types
        return maybe_sub_type.name in types

    def get_directive(self, name: str) -> GraphQLDirective | None:
        """Get the directive with the given name."""
        for directive in self.directives:
            if directive.name == name:
                return directive
        return None

    def get_field(
        self, parent_type: GraphQLCompositeType, field_name: str
    ) -> GraphQLField | None:
        """Get field of a given type with the given name.

        This method looks up the field on the given type definition.
        It has special casing for the three introspection fields, `__schema`,
        `__type` and `__typename`.

        `__typename` is special because it can always be queried as a field, even
        in situations where no other fields are allowed, like on a Union.

        `__schema` and `__type` could get automatically added to the query type,
        but that would require mutating type definitions, which would cause issues.
        """
        if field_name == "__schema":
            return SchemaMetaFieldDef if self.query_type is parent_type else None
        if field_name == "__type":
            return TypeMetaFieldDef if self.query_type is parent_type else None
        if field_name == "__typename":
            return TypeNameMetaFieldDef

        # this function is part of a "hot" path inside executor and to assume presence
        # of 'fields' is faster than to use `not is_union_type`
        try:
            return parent_type.fields[field_name]  # type: ignore
        except (AttributeError, KeyError):
            return None

    @property
    def validation_errors(self) -> list[GraphQLError] | None:
        """Get validation errors."""
        return self._validation_errors


class TypeSet(Dict[GraphQLNamedType, None]):
    """An ordered set of types that can be collected starting from initial types."""

    @classmethod
    def with_initial_types(cls, types: Collection[GraphQLType]) -> TypeSet:
        return cast("TypeSet", super().fromkeys(types))

    def collect_referenced_types(self, type_: GraphQLType) -> None:
        """Recursive function supplementing the type starting from an initial type."""
        named_type = get_named_type(type_)

        if named_type in self:
            return

        self[named_type] = None

        collect_referenced_types = self.collect_referenced_types
        if is_union_type(named_type):
            for member_type in named_type.types:
                collect_referenced_types(member_type)
        elif is_object_type(named_type) or is_interface_type(named_type):
            for interface_type in named_type.interfaces:
                collect_referenced_types(interface_type)

            for field in named_type.fields.values():
                collect_referenced_types(field.type)
                for arg in field.args.values():
                    collect_referenced_types(arg.type)
        elif is_input_object_type(named_type):
            for field in named_type.fields.values():
                collect_referenced_types(field.type)


def is_schema(schema: Any) -> TypeGuard[GraphQLSchema]:
    """Check whether this is a GraphQL schema."""
    return isinstance(schema, GraphQLSchema)


def assert_schema(schema: Any) -> GraphQLSchema:
    """Assert that this is a GraphQL schema."""
    if not is_schema(schema):
        msg = f"Expected {inspect(schema)} to be a GraphQL schema."
        raise TypeError(msg)
    return schema


def remapped_type(type_: GraphQLType, type_map: TypeMap) -> GraphQLType:
    """Get a copy of the given type that uses this type map."""
    if is_wrapping_type(type_):
        return type_.__class__(remapped_type(type_.of_type, type_map))
    type_ = cast("GraphQLNamedType", type_)
    return type_map.get(type_.name, type_)


def remap_named_type(type_: GraphQLNamedType, type_map: TypeMap) -> None:
    """Change all references in the given named type to use this type map."""
    if is_object_type(type_) or is_interface_type(type_):
        type_.interfaces = [
            type_map.get(interface_type.name, interface_type)
            for interface_type in type_.interfaces
        ]
        fields = type_.fields
        for field_name, field in fields.items():
            field = copy(field)  # noqa: PLW2901
            field.type = remapped_type(field.type, type_map)
            args = field.args
            for arg_name, arg in args.items():
                arg = copy(arg)  # noqa: PLW2901
                arg.type = remapped_type(arg.type, type_map)
                args[arg_name] = arg
            fields[field_name] = field
    elif is_union_type(type_):
        type_.types = [
            type_map.get(member_type.name, member_type) for member_type in type_.types
        ]
    elif is_input_object_type(type_):
        fields = type_.fields
        for field_name, field in fields.items():
            field = copy(field)  # noqa: PLW2901
            field.type = remapped_type(field.type, type_map)
            fields[field_name] = field


def remap_directive(directive: GraphQLDirective, type_map: TypeMap) -> None:
    """Change all references in the given directive to use this type map."""
    args = directive.args
    for arg_name, arg in args.items():
        arg = copy(arg)  # noqa: PLW2901
        arg.type = cast("GraphQLInputType", remapped_type(arg.type, type_map))
        args[arg_name] = arg
