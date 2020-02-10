from functools import reduce
from typing import (
    Any,
    Collection,
    Dict,
    List,
    NamedTuple,
    Optional,
    Set,
    Union,
    cast,
)

from ..error import GraphQLError
from ..language import ast
from ..pyutils import inspect, is_collection, FrozenList
from .definition import (
    GraphQLAbstractType,
    GraphQLInterfaceType,
    GraphQLInputObjectType,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLUnionType,
    get_named_type,
    is_input_object_type,
    is_interface_type,
    is_named_type,
    is_object_type,
    is_union_type,
)
from .directives import GraphQLDirective, specified_directives, is_directive
from .introspection import introspection_types

__all__ = ["GraphQLSchema", "is_schema", "assert_schema"]


TypeMap = Dict[str, GraphQLNamedType]


class InterfaceImplementations(NamedTuple):

    objects: List[GraphQLObjectType]
    interfaces: List[GraphQLInterfaceType]


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

    Note: If a list of `directives` is provided to GraphQLSchema, that will be the
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
    extensions: Optional[Dict[str, Any]]
    ast_node: Optional[ast.SchemaDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[ast.SchemaExtensionNode]]

    _implementations: Dict[str, InterfaceImplementations]
    _sub_type_map: Dict[str, Set[str]]

    def __init__(
        self,
        query: Optional[GraphQLObjectType] = None,
        mutation: Optional[GraphQLObjectType] = None,
        subscription: Optional[GraphQLObjectType] = None,
        types: Optional[Collection[GraphQLNamedType]] = None,
        directives: Optional[Collection[GraphQLDirective]] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[ast.SchemaDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[ast.SchemaExtensionNode]] = None,
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
                if not is_collection(types) or (
                    # if reducer has been overridden, don't check types
                    getattr(self.type_map_reducer, "__func__", None)
                    is GraphQLSchema.type_map_reducer
                    and not all(is_named_type(type_) for type_ in types)
                ):
                    raise TypeError(
                        "Schema types must be specified as a collection"
                        " of GraphQLNamedType instances."
                    )
            if directives is not None:
                # noinspection PyUnresolvedReferences
                if not is_collection(directives) or (
                    # if reducer has been overridden, don't check directive types
                    getattr(self.type_map_directive_reducer, "__func__", None)
                    is GraphQLSchema.type_map_directive_reducer
                    and not all(is_directive(directive) for directive in directives)
                ):
                    raise TypeError(
                        "Schema directives must be specified as a collection"
                        " of GraphQLDirective instances."
                    )
                if not isinstance(directives, FrozenList):
                    directives = FrozenList(directives)
            if extensions is not None and (
                not isinstance(extensions, dict)
                or not all(isinstance(key, str) for key in extensions)
            ):
                raise TypeError(
                    "Schema extensions must be a dictionary with string keys."
                )
            if ast_node and not isinstance(ast_node, ast.SchemaDefinitionNode):
                raise TypeError("Schema AST node must be a SchemaDefinitionNode.")
            if extension_ast_nodes:
                if not is_collection(extension_ast_nodes) or not all(
                    isinstance(node, ast.SchemaExtensionNode)
                    for node in extension_ast_nodes
                ):
                    raise TypeError(
                        "Schema extension AST nodes must be specified"
                        " as a collection of SchemaExtensionNode instances."
                    )
                if not isinstance(extension_ast_nodes, FrozenList):
                    extension_ast_nodes = FrozenList(extension_ast_nodes)

            self._validation_errors = None

        self.extensions = extensions
        self.ast_node = ast_node
        self.extension_ast_nodes = (
            cast(FrozenList[ast.SchemaExtensionNode], extension_ast_nodes)
            if extension_ast_nodes
            else None
        )

        self.query_type = query
        self.mutation_type = mutation
        self.subscription_type = subscription
        # Provide specified directives (e.g. @include and @skip) by default
        self.directives = (
            specified_directives
            if directives is None
            else cast(FrozenList[GraphQLDirective], directives)
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

        self._sub_type_map = {}

        # Keep track of all implementations by interface name.
        self._implementations = collect_implementations(type_map.values())

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            query=self.query_type,
            mutation=self.mutation_type,
            subscription=self.subscription_type,
            types=FrozenList(self.type_map.values()) or None,
            directives=self.directives[:],
            extensions=self.extensions,
            ast_node=self.ast_node,
            extension_ast_nodes=self.extension_ast_nodes,
            assume_valid=self._validation_errors is not None,
        )

    def get_type(self, name: str) -> Optional[GraphQLNamedType]:
        return self.type_map.get(name)

    def get_possible_types(
        self, abstract_type: GraphQLAbstractType
    ) -> List[GraphQLObjectType]:
        """Get list of all possible concrete types for given abstract type."""
        return (
            cast(GraphQLUnionType, abstract_type).types
            if is_union_type(abstract_type)
            else self.get_implementations(
                cast(GraphQLInterfaceType, abstract_type)
            ).objects
        )

    def get_implementations(
        self, interface_type: GraphQLInterfaceType
    ) -> InterfaceImplementations:
        return self._implementations[interface_type.name]

    def is_possible_type(
        self, abstract_type: GraphQLAbstractType, possible_type: GraphQLObjectType
    ) -> bool:
        """Check whether a concrete type is possible for an abstract type.

        Deprecated: Use is_sub_type() instead.
        """
        return self.is_sub_type(abstract_type, possible_type)

    def is_sub_type(
        self,
        abstract_type: GraphQLAbstractType,
        maybe_sub_type: Union[GraphQLObjectType, GraphQLInterfaceType],
    ) -> bool:
        """Check whether a type is a subtype of a given abstract type."""
        types = self._sub_type_map.get(abstract_type.name)
        if types is None:
            types = set()
            add = types.add
            if is_union_type(abstract_type):
                for type_ in cast(GraphQLUnionType, abstract_type).types:
                    add(type_.name)
            else:
                implementations = self.get_implementations(
                    cast(GraphQLInterfaceType, abstract_type)
                )
                for type_ in implementations.objects:
                    add(type_.name)
                for type_ in implementations.interfaces:
                    add(type_.name)
            self._sub_type_map[abstract_type.name] = types
        return maybe_sub_type.name in types

    def get_directive(self, name: str) -> Optional[GraphQLDirective]:
        for directive in self.directives:
            if directive.name == name:
                return directive
        return None

    @property
    def validation_errors(self):
        return self._validation_errors

    def type_map_reducer(
        self, map_: TypeMap, type_: Optional[GraphQLNamedType] = None
    ) -> TypeMap:
        """Reducer function for creating the type map from given types."""
        if not type_:
            return map_

        named_type = get_named_type(type_)
        name = named_type.name

        if name in map_:
            if map_[name] is not named_type:
                raise TypeError(
                    "Schema must contain uniquely named types but contains multiple"
                    f" types named {name!r}."
                )
            return map_
        map_[name] = named_type

        if is_union_type(named_type):
            named_type = cast(GraphQLUnionType, named_type)
            map_ = reduce(self.type_map_reducer, named_type.types, map_)

        elif is_object_type(named_type) or is_interface_type(named_type):
            named_type = cast(
                Union[GraphQLObjectType, GraphQLInterfaceType], named_type
            )
            map_ = reduce(self.type_map_reducer, named_type.interfaces, map_)
            for field in cast(GraphQLInterfaceType, named_type).fields.values():
                types = [arg.type for arg in field.args.values()]
                map_ = reduce(self.type_map_reducer, types, map_)
                map_ = self.type_map_reducer(map_, field.type)

        elif is_input_object_type(named_type):
            for field in cast(GraphQLInputObjectType, named_type).fields.values():
                map_ = self.type_map_reducer(map_, field.type)

        return map_

    def type_map_directive_reducer(
        self, map_: TypeMap, directive: Optional[GraphQLDirective] = None
    ) -> TypeMap:
        """Reducer function for creating the type map from given directives."""
        # Directives are not validated until validate_schema() is called.
        if not is_directive(directive):
            return map_  # pragma: no cover
        directive = cast(GraphQLDirective, directive)
        return reduce(
            lambda prev_map, arg: self.type_map_reducer(
                prev_map, cast(GraphQLNamedType, arg.type)
            ),
            directive.args.values(),
            map_,
        )


def collect_implementations(
    types: Collection[GraphQLNamedType],
) -> Dict[str, InterfaceImplementations]:
    implementations_map: Dict[str, InterfaceImplementations] = {}
    for type_ in types:
        if is_interface_type(type_):
            type_ = cast(GraphQLInterfaceType, type_)
            if type_.name not in implementations_map:
                implementations_map[type_.name] = InterfaceImplementations(
                    objects=[], interfaces=[]
                )
            # Store implementations by interface.
            for interface in type_.interfaces:
                if is_interface_type(interface):
                    implementations = implementations_map.get(interface.name)
                    if implementations is None:
                        implementations_map[interface.name] = InterfaceImplementations(
                            objects=[], interfaces=[type_]
                        )
                    else:
                        implementations.interfaces.append(type_)
        elif is_object_type(type_):
            type_ = cast(GraphQLObjectType, type_)
            # Store implementations by objects.
            for interface in type_.interfaces:
                if is_interface_type(interface):
                    implementations = implementations_map.get(interface.name)
                    if implementations is None:
                        implementations_map[interface.name] = InterfaceImplementations(
                            objects=[type_], interfaces=[]
                        )
                    else:
                        implementations.objects.append(type_)
    return implementations_map


def is_schema(schema: Any) -> bool:
    """Test if the given value is a GraphQL schema."""
    return isinstance(schema, GraphQLSchema)


def assert_schema(schema: Any) -> GraphQLSchema:
    if not is_schema(schema):
        raise TypeError(f"Expected {inspect(schema)} to be a GraphQL schema.")
    return cast(GraphQLSchema, schema)
