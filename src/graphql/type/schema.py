from collections.abc import Sequence as AbstractSequence
from functools import reduce
from typing import Any, Dict, List, Optional, Sequence, Set, cast

from ..error import GraphQLError
from ..language import ast
from ..pyutils import inspect, FrozenList
from .definition import (
    GraphQLAbstractType,
    GraphQLInterfaceType,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLUnionType,
    GraphQLInputObjectType,
    GraphQLWrappingType,
    is_abstract_type,
    is_input_object_type,
    is_interface_type,
    is_named_type,
    is_object_type,
    is_union_type,
    is_wrapping_type,
)
from .directives import GraphQLDirective, specified_directives, is_directive
from .introspection import introspection_types

__all__ = ["GraphQLSchema", "is_schema", "assert_schema"]


TypeMap = Dict[str, GraphQLNamedType]


class GraphQLSchema:
    """Schema Definition

    A Schema is created by supplying the root types of each type of operation, query
    and mutation (optional). A schema definition is then supplied to the validator
    and executor.

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

    Note: If a list of `directives` are provided to GraphQLSchema, that will be the
    exact list of directives represented and allowed. If `directives` is not provided,
    then a default set of the specified directives (e.g. @include and @skip) will be
    used. If you wish to provide *additional* directives to these specified directives,
    you must explicitly declare them. Example::

        MyAppSchema = GraphQLSchema(
          ...
          directives=specified_directives + [my_custom_directive])
    """

    query_type: Optional[GraphQLObjectType]
    mutation_type: Optional[GraphQLObjectType]
    subscription_type: Optional[GraphQLObjectType]
    type_map: TypeMap
    directives: FrozenList[GraphQLDirective]
    ast_node: Optional[ast.SchemaDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[ast.SchemaExtensionNode]]

    def __init__(
        self,
        query: GraphQLObjectType = None,
        mutation: GraphQLObjectType = None,
        subscription: GraphQLObjectType = None,
        types: Sequence[GraphQLNamedType] = None,
        directives: Sequence[GraphQLDirective] = None,
        ast_node: ast.SchemaDefinitionNode = None,
        extension_ast_nodes: Sequence[ast.SchemaExtensionNode] = None,
        assume_valid: bool = False,
    ) -> None:
        """Initialize GraphQL schema.

        If this schema was built from a source known to be valid, then it may be marked
        with `assume_valid` to avoid an additional type system validation. Otherwise
        check for common mistakes during construction to produce clear and early error
        messages.
        """
        if assume_valid:
            # If this schema was built from a source known to be valid, then it may be
            # marked with assume_valid to avoid an additional type system validation.
            self._validation_errors: Optional[List[GraphQLError]] = []
        else:
            # Otherwise check for common mistakes during construction to produce clear
            # and early error messages.
            if types is None:
                types = []
            else:
                if not isinstance(types, AbstractSequence) or (
                    # if reducer has been overridden, don't check types
                    getattr(self.type_map_reducer, "__func__", None)
                    is GraphQLSchema.type_map_reducer
                    and not all(is_named_type(type_) for type_ in types)
                ):
                    raise TypeError(
                        "Schema types must be specified as a sequence"
                        " of GraphQLNamedType instances."
                    )
            if directives is not None:
                # noinspection PyUnresolvedReferences
                if not isinstance(directives, AbstractSequence) or (
                    # if reducer has been overridden, don't check directive types
                    getattr(self.type_map_directive_reducer, "__func__", None)
                    is GraphQLSchema.type_map_directive_reducer
                    and not all(is_directive(directive) for directive in directives)
                ):
                    raise TypeError(
                        "Schema directives must be specified as a sequence"
                        " of GraphQLDirective instances."
                    )
                if not isinstance(directives, FrozenList):
                    directives = FrozenList(directives)
            if ast_node and not isinstance(ast_node, ast.SchemaDefinitionNode):
                raise TypeError("Schema AST node must be a SchemaDefinitionNode.")
            if extension_ast_nodes:
                if not isinstance(extension_ast_nodes, AbstractSequence) or not all(
                    isinstance(node, ast.SchemaExtensionNode)
                    for node in extension_ast_nodes
                ):
                    raise TypeError(
                        "Schema extension AST nodes must be specified"
                        " as a sequence of SchemaExtensionNode instances."
                    )
                if not isinstance(extension_ast_nodes, FrozenList):
                    extension_ast_nodes = FrozenList(extension_ast_nodes)

            self._validation_errors = None

        self.query_type = query
        self.mutation_type = mutation
        self.subscription_type = subscription
        # Provide specified directives (e.g. @include and @skip) by default
        self.directives = (
            specified_directives
            if directives is None
            else cast(FrozenList[GraphQLDirective], directives)
        )
        self.ast_node = ast_node
        self.extension_ast_nodes = (
            cast(FrozenList[ast.SchemaExtensionNode], extension_ast_nodes)
            if extension_ast_nodes
            else None
        )

        # Build type map now to detect any errors within this schema.
        initial_types: List[Optional[GraphQLNamedType]] = [
            query,
            mutation,
            subscription,
            introspection_types["__Schema"],
        ]
        if types:
            initial_types.extend(types)

        # Keep track of all types referenced within the schema.
        type_map: TypeMap = {}
        # First by deeply visiting all initial types.
        type_map = reduce(self.type_map_reducer, initial_types, type_map)
        # Then by deeply visiting all directive types.
        type_map = reduce(self.type_map_directive_reducer, self.directives, type_map)
        # Storing the resulting map for reference by the schema
        self.type_map = type_map

        self._possible_type_map: Dict[str, Set[str]] = {}

        # Keep track of all implementations by interface name.
        self._implementations: Dict[str, List[GraphQLObjectType]] = {}
        setdefault = self._implementations.setdefault
        for type_ in self.type_map.values():
            if is_object_type(type_):
                type_ = cast(GraphQLObjectType, type_)
                for interface in type_.interfaces:
                    if is_interface_type(interface):
                        setdefault(interface.name, []).append(type_)
            elif is_abstract_type(type_):
                setdefault(type_.name, [])

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            query=self.query_type,
            mutation=self.mutation_type,
            subscription=self.subscription_type,
            types=FrozenList(self.type_map.values()) or None,
            directives=None
            if self.directives is specified_directives
            else self.directives,
            ast_node=self.ast_node,
            extension_ast_nodes=self.extension_ast_nodes or None,
            assume_valid=self._validation_errors is not None,
        )

    def get_type(self, name: str) -> Optional[GraphQLNamedType]:
        return self.type_map.get(name)

    def get_possible_types(
        self, abstract_type: GraphQLAbstractType
    ) -> Sequence[GraphQLObjectType]:
        """Get list of all possible concrete types for given abstract type."""
        if is_union_type(abstract_type):
            abstract_type = cast(GraphQLUnionType, abstract_type)
            return abstract_type.types
        return self._implementations[abstract_type.name]

    def is_possible_type(
        self, abstract_type: GraphQLAbstractType, possible_type: GraphQLObjectType
    ) -> bool:
        """Check whether a concrete type is possible for an abstract type."""
        possible_type_map = self._possible_type_map
        try:
            possible_type_names = possible_type_map[abstract_type.name]
        except KeyError:
            possible_types = self.get_possible_types(abstract_type)
            possible_type_names = {type_.name for type_ in possible_types}
            possible_type_map[abstract_type.name] = possible_type_names
        return possible_type.name in possible_type_names

    def get_directive(self, name: str) -> Optional[GraphQLDirective]:
        for directive in self.directives:
            if directive.name == name:
                return directive
        return None

    @property
    def validation_errors(self):
        return self._validation_errors

    def type_map_reducer(
        self, map_: TypeMap, type_: GraphQLNamedType = None
    ) -> TypeMap:
        """Reducer function for creating the type map from given types."""
        if not type_:
            return map_
        if is_wrapping_type(type_):
            return self.type_map_reducer(
                map_, cast(GraphQLWrappingType[GraphQLNamedType], type_).of_type
            )
        name = type_.name
        if name in map_:
            if map_[name] is not type_:
                raise TypeError(
                    "Schema must contain uniquely named types but contains multiple"
                    f" types named {name!r}."
                )
            return map_
        map_[name] = type_

        if is_union_type(type_):
            type_ = cast(GraphQLUnionType, type_)
            map_ = reduce(self.type_map_reducer, type_.types, map_)

        if is_object_type(type_):
            type_ = cast(GraphQLObjectType, type_)
            map_ = reduce(self.type_map_reducer, type_.interfaces, map_)

        if is_object_type(type_) or is_interface_type(type_):
            for field in cast(GraphQLInterfaceType, type_).fields.values():
                args = field.args
                if args:
                    types = [arg.type for arg in args.values()]
                    map_ = reduce(self.type_map_reducer, types, map_)
                map_ = self.type_map_reducer(map_, field.type)

        if is_input_object_type(type_):
            for field in cast(GraphQLInputObjectType, type_).fields.values():
                map_ = self.type_map_reducer(map_, field.type)

        return map_

    def type_map_directive_reducer(
        self, map_: TypeMap, directive: GraphQLDirective = None
    ) -> TypeMap:
        """Reducer function for creating the type map from given directives."""
        # Directives are not validated until validate_schema() is called.
        if not is_directive(directive):
            return map_
        directive = cast(GraphQLDirective, directive)
        return reduce(
            lambda prev_map, arg: self.type_map_reducer(
                prev_map, cast(GraphQLNamedType, arg.type)
            ),
            directive.args.values(),
            map_,
        )


def is_schema(schema: Any) -> bool:
    """Test if the given value is a GraphQL schema."""
    return isinstance(schema, GraphQLSchema)


def assert_schema(schema: Any) -> GraphQLSchema:
    if not is_schema(schema):
        raise TypeError(f"Expected {inspect(schema)} to be a GraphQL schema.")
    return cast(GraphQLSchema, schema)
