from copy import copy, deepcopy
from typing import (
    Any,
    Collection,
    Dict,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from ..error import GraphQLError
from ..language import OperationType, ast
from ..pyutils import inspect, is_collection, is_description
from .definition import (
    GraphQLAbstractType,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLType,
    GraphQLUnionType,
    GraphQLWrappingType,
    get_named_type,
    is_input_object_type,
    is_interface_type,
    is_object_type,
    is_union_type,
    is_wrapping_type,
)
from .directives import GraphQLDirective, is_directive, specified_directives
from .introspection import introspection_types

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict

__all__ = ["GraphQLSchema", "GraphQLSchemaKwargs", "is_schema", "assert_schema"]


TypeMap = Dict[str, GraphQLNamedType]


class InterfaceImplementations(NamedTuple):
    """Objects and interfaces that implement an interface type."""

    objects: List[GraphQLObjectType]
    """Object types that implement the interface."""
    interfaces: List[GraphQLInterfaceType]
    """Interface types that implement the interface."""


class GraphQLSchemaKwargs(TypedDict, total=False):
    """Arguments used to construct a GraphQLSchema."""

    query: Optional[GraphQLObjectType]
    """Root object type for query operations."""
    mutation: Optional[GraphQLObjectType]
    """Root object type for mutation operations."""
    subscription: Optional[GraphQLObjectType]
    """Root object type for subscription operations."""
    types: Optional[Tuple[GraphQLNamedType, ...]]
    """Named types that belong to this schema."""
    directives: Tuple[GraphQLDirective, ...]
    """Directives available in this schema."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    extensions: Dict[str, Any]
    """Extension fields to include in the formatted result."""
    ast_node: Optional[ast.SchemaDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[ast.SchemaExtensionNode, ...]
    """AST extension nodes applied to this schema element."""
    assume_valid: bool
    """Whether the schema is assumed to be valid and will not be validated."""


class GraphQLSchema:
    """Schema Definition

    A Schema is created by supplying the root types of each type of operation, query
    and mutation (optional). A schema definition is then supplied to the validator
    and executor.

    Schemas should be considered immutable once they are created. If you want to modify
    a schema, modify the result of the ``to_kwargs()`` method and recreate the schema.

    Example::

        MyAppQueryRootType = GraphQLObjectType(
            'Query', {'greeting': GraphQLField(GraphQLString)})

        MyAppMutationRootType = GraphQLObjectType(
            'Mutation', {'setGreeting': GraphQLField(GraphQLString)})

        MyAppSchema = GraphQLSchema(
          query=MyAppQueryRootType,
          mutation=MyAppMutationRootType)

    Note: When the schema is constructed, by default only the types that are
    reachable by traversing the root types are included, other types must be
    explicitly referenced.

    Example::

        character_interface = GraphQLInterfaceType(
            'Character', {'name': GraphQLField(GraphQLString)})

        human_type = GraphQLObjectType(
            'Human', {'name': GraphQLField(GraphQLString)},
            interfaces=[character_interface])

        droid_type = GraphQLObjectType(
            'Droid', {'name': GraphQLField(GraphQLString)},
            interfaces=[character_interface])

        schema = GraphQLSchema(
            query=GraphQLObjectType('Query',
                fields={'hero': GraphQLField(character_interface)}),
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
          query=MyAppQueryRootType,
          directives=(*specified_directives, my_custom_directive))

    :param query: the root object type for query operations
    :param mutation: the root object type for mutation operations
    :param subscription: the root object type for subscription operations
    :param types: additional named types that shall be included in the schema
    :param directives: the directives available in this schema; if not provided,
        the specified directives will be used
    :param description: a human-readable description for this schema, if any
    :param extensions: extension fields to include in the formatted result
    :param ast_node: the AST node from which this schema was built, if available
    :param extension_ast_nodes: the AST extension nodes applied to this schema
    :param assume_valid: if this schema was built from a source known to be valid,
        then it may be marked with ``assume_valid`` to avoid an additional type
        system validation

    Create a schema with the required query root:

    >>> from graphql import (
    ...     GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString
    ... )
    >>> Query = GraphQLObjectType(
    ...     'Query',
    ...     {'greeting': GraphQLField(GraphQLString, resolve=lambda *_: 'Hello')},
    ... )
    >>> schema = GraphQLSchema(
    ...     description='The application schema.',
    ...     query=Query,
    ... )
    >>> schema.query_type is Query
    True
    >>> schema.description
    'The application schema.'

    This variant configures every schema option, including directives and
    extensions:

    >>> from graphql import (
    ...     DirectiveLocation,
    ...     GraphQLArgument,
    ...     GraphQLBoolean,
    ...     GraphQLDirective,
    ...     GraphQLField,
    ...     GraphQLObjectType,
    ...     GraphQLSchema,
    ...     GraphQLString,
    ...     parse,
    ... )
    >>> Query = GraphQLObjectType(
    ...     'Query', {'greeting': GraphQLField(GraphQLString)}
    ... )
    >>> Mutation = GraphQLObjectType(
    ...     'Mutation', {'setGreeting': GraphQLField(GraphQLString)}
    ... )
    >>> Subscription = GraphQLObjectType(
    ...     'Subscription', {'greetingChanged': GraphQLField(GraphQLString)}
    ... )
    >>> AuditEvent = GraphQLObjectType(
    ...     'AuditEvent', {'message': GraphQLField(GraphQLString)}
    ... )
    >>> auth_directive = GraphQLDirective(
    ...     'auth',
    ...     [DirectiveLocation.FIELD_DEFINITION],
    ...     {'required': GraphQLArgument(GraphQLBoolean)},
    ... )
    >>> schema_document = parse('''
    ...     schema {
    ...       query: Query
    ...       mutation: Mutation
    ...       subscription: Subscription
    ...     }
    ...
    ...     extend schema @auth
    ... ''')
    >>> schema = GraphQLSchema(
    ...     description='Operations exposed by the application.',
    ...     query=Query,
    ...     mutation=Mutation,
    ...     subscription=Subscription,
    ...     types=[AuditEvent],
    ...     directives=[auth_directive],
    ...     extensions={'owner': 'platform'},
    ...     ast_node=schema_document.definitions[0],
    ...     extension_ast_nodes=[schema_document.definitions[1]],
    ...     assume_valid=True,
    ... )
    >>> schema.mutation_type is Mutation
    True
    >>> schema.subscription_type is Subscription
    True
    >>> schema.get_type('AuditEvent') is AuditEvent
    True
    >>> schema.get_directive('auth') is auth_directive
    True
    >>> schema.extensions
    {'owner': 'platform'}
    >>> schema.validation_errors
    []
    """

    query_type: Optional[GraphQLObjectType]
    """The root object type for query operations, if this schema defines one."""
    mutation_type: Optional[GraphQLObjectType]
    """The root object type for mutation operations, if this schema defines one."""
    subscription_type: Optional[GraphQLObjectType]
    """The root object type for subscription operations, if defined."""
    type_map: TypeMap
    """All named types known to this schema, keyed by type name."""
    directives: Tuple[GraphQLDirective, ...]
    """Directives available in this schema."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    extensions: Dict[str, Any]
    """Extension fields to include in the formatted result."""
    ast_node: Optional[ast.SchemaDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[ast.SchemaExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    _implementations_map: Dict[str, InterfaceImplementations]
    _sub_type_map: Dict[str, Set[str]]
    _validation_errors: Optional[List[GraphQLError]]

    def __init__(
        self,
        query: Optional[GraphQLObjectType] = None,
        mutation: Optional[GraphQLObjectType] = None,
        subscription: Optional[GraphQLObjectType] = None,
        types: Optional[Collection[GraphQLNamedType]] = None,
        directives: Optional[Collection[GraphQLDirective]] = None,
        description: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[ast.SchemaDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[ast.SchemaExtensionNode]] = None,
        assume_valid: bool = False,
    ) -> None:
        # If this schema was built from a source known to be valid, then it may be
        # marked with assume_valid to avoid an additional type system validation.
        self._validation_errors = [] if assume_valid else None

        # Check for common mistakes during construction to produce clear and early
        # error messages, but we leave the specific tests for the validation.
        if query and not isinstance(query, GraphQLType):
            raise TypeError("Expected query to be a GraphQL type.")
        if mutation and not isinstance(mutation, GraphQLType):
            raise TypeError("Expected mutation to be a GraphQL type.")
        if subscription and not isinstance(subscription, GraphQLType):
            raise TypeError("Expected subscription to be a GraphQL type.")
        if types is None:
            types = []
        else:
            if not is_collection(types) or not all(
                isinstance(type_, GraphQLType) for type_ in types
            ):
                raise TypeError(
                    "Schema types must be specified as a collection of GraphQL types."
                )
        if directives is not None:
            # noinspection PyUnresolvedReferences
            if not is_collection(directives):
                raise TypeError("Schema directives must be a collection.")
            if not isinstance(directives, tuple):
                directives = tuple(directives)
        if description is not None and not is_description(description):
            raise TypeError("Schema description must be a string.")
        if extensions is None:
            extensions = {}
        elif not isinstance(extensions, dict) or not all(
            isinstance(key, str) for key in extensions
        ):
            raise TypeError("Schema extensions must be a dictionary with string keys.")
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
            if not isinstance(extension_ast_nodes, tuple):
                extension_ast_nodes = tuple(extension_ast_nodes)
        else:
            extension_ast_nodes = ()

        self.description = description
        self.extensions = extensions
        self.ast_node = ast_node
        self.extension_ast_nodes = extension_ast_nodes
        self.query_type = query
        self.mutation_type = mutation
        self.subscription_type = subscription
        # Provide specified directives (e.g. @include and @skip) by default
        self.directives = specified_directives if directives is None else directives

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
        implementations_map: Dict[str, InterfaceImplementations] = {}
        self._implementations_map = implementations_map

        for named_type in all_referenced_types:
            if not named_type:
                continue

            type_name = getattr(named_type, "name", None)
            if not type_name:
                raise TypeError(
                    "One of the provided types for building the Schema"
                    " is missing a name.",
                )
            if type_name in type_map:
                raise TypeError(
                    "Schema must contain uniquely named types"
                    f" but contains multiple types named '{type_name}'."
                )

            type_map[type_name] = named_type

            if is_interface_type(named_type):
                named_type = cast(GraphQLInterfaceType, named_type)
                # Store implementations by interface.
                for iface in named_type.interfaces:
                    if is_interface_type(iface):
                        iface = cast(GraphQLInterfaceType, iface)
                        if iface.name in implementations_map:
                            implementations = implementations_map[iface.name]
                        else:
                            implementations = implementations_map[iface.name] = (
                                InterfaceImplementations(objects=[], interfaces=[])
                            )

                        implementations.interfaces.append(named_type)
            elif is_object_type(named_type):
                named_type = cast(GraphQLObjectType, named_type)
                # Store implementations by objects.
                for iface in named_type.interfaces:
                    if is_interface_type(iface):
                        iface = cast(GraphQLInterfaceType, iface)
                        if iface.name in implementations_map:
                            implementations = implementations_map[iface.name]
                        else:
                            implementations = implementations_map[iface.name] = (
                                InterfaceImplementations(objects=[], interfaces=[])
                            )

                        implementations.objects.append(named_type)

    def to_kwargs(self) -> GraphQLSchemaKwargs:
        """Get a normalized dictionary of keyword arguments for this schema.

        The returned keyword arguments preserve the original ``assume_valid`` flag so
        the schema can be recreated with the same validation behavior.

        :returns: keyword arguments that can be used to recreate this schema

        >>> from graphql import GraphQLSchema, build_schema
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ... ''')
        >>> kwargs = schema.to_kwargs()
        >>> schema_copy = GraphQLSchema(**kwargs)
        >>> kwargs['query'].name
        'Query'
        >>> schema_copy.query_type.name
        'Query'
        """
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

    def __copy__(self) -> "GraphQLSchema":  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    def __deepcopy__(self, memo_: Dict) -> "GraphQLSchema":
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
            self.query_type and cast(GraphQLObjectType, type_map[self.query_type.name]),
            self.mutation_type
            and cast(GraphQLObjectType, type_map[self.mutation_type.name]),
            self.subscription_type
            and cast(GraphQLObjectType, type_map[self.subscription_type.name]),
            types,
            directives,
            self.description,
            extensions=deepcopy(self.extensions),
            ast_node=deepcopy(self.ast_node),
            extension_ast_nodes=deepcopy(self.extension_ast_nodes),
            assume_valid=True,
        )

    def get_root_type(self, operation: OperationType) -> Optional[GraphQLObjectType]:
        """Get the root object type for the requested operation kind.

        :param operation: the operation kind to resolve
        :returns: the root object type for the operation kind, if this schema
            defines one

        >>> from graphql import OperationType, build_schema
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ...
        ...     type Mutation {
        ...       setGreeting(value: String!): String
        ...     }
        ... ''')
        >>> schema.get_root_type(OperationType.QUERY).name
        'Query'
        >>> schema.get_root_type(OperationType.MUTATION).name
        'Mutation'
        >>> schema.get_root_type(OperationType.SUBSCRIPTION) is None
        True
        """
        return getattr(self, f"{operation.value}_type")

    def get_type(self, name: str) -> Optional[GraphQLNamedType]:
        """Get the named type with the provided name.

        :param name: the GraphQL name to look up
        :returns: the named schema type, if one exists

        >>> from graphql import build_schema
        >>> schema = build_schema('''
        ...     type User {
        ...       name: String
        ...     }
        ...
        ...     type Query {
        ...       viewer: User
        ...     }
        ... ''')
        >>> str(schema.get_type('User'))
        'User'
        >>> schema.get_type('Missing') is None
        True
        """
        return self.type_map.get(name)

    def get_possible_types(
        self, abstract_type: GraphQLAbstractType
    ) -> List[GraphQLObjectType]:
        """Get list of all possible concrete types for given abstract type.

        :param abstract_type: the interface or union type to inspect
        :returns: the object types that may satisfy the abstract type

        >>> from graphql import (
        ...     assert_interface_type, assert_union_type, build_schema
        ... )
        >>> schema = build_schema('''
        ...     interface Node {
        ...       id: ID!
        ...     }
        ...
        ...     type User implements Node {
        ...       id: ID!
        ...     }
        ...
        ...     type Organization implements Node {
        ...       id: ID!
        ...     }
        ...
        ...     union SearchResult = User | Organization
        ...
        ...     type Query {
        ...       node: Node
        ...       search: [SearchResult]
        ...     }
        ... ''')
        >>> Node = assert_interface_type(schema.get_type('Node'))
        >>> SearchResult = assert_union_type(schema.get_type('SearchResult'))
        >>> [type_.name for type_ in schema.get_possible_types(Node)]
        ['User', 'Organization']
        >>> [type_.name for type_ in schema.get_possible_types(SearchResult)]
        ['User', 'Organization']
        """
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
        """Get the objects and interfaces that implement an interface type.

        :param interface_type: the interface type to inspect
        :returns: the object and interface implementations of the interface

        >>> from graphql import assert_interface_type, build_schema
        >>> schema = build_schema('''
        ...     interface Resource {
        ...       url: String!
        ...     }
        ...
        ...     interface Image implements Resource {
        ...       url: String!
        ...       width: Int
        ...     }
        ...
        ...     type Photo implements Resource & Image {
        ...       url: String!
        ...       width: Int
        ...     }
        ...
        ...     type Query {
        ...       resource: Resource
        ...     }
        ... ''')
        >>> Resource = assert_interface_type(schema.get_type('Resource'))
        >>> implementations = schema.get_implementations(Resource)
        >>> [type_.name for type_ in implementations.interfaces]
        ['Image']
        >>> [type_.name for type_ in implementations.objects]
        ['Photo']
        """
        return self._implementations_map.get(
            interface_type.name, InterfaceImplementations(objects=[], interfaces=[])
        )

    def is_sub_type(
        self,
        abstract_type: GraphQLAbstractType,
        maybe_sub_type: GraphQLNamedType,
    ) -> bool:
        """Check whether a type is a subtype of a given abstract type.

        :param abstract_type: the interface or union type to inspect
        :param maybe_sub_type: the object or interface type to test as a possible
            subtype
        :returns: whether the subtype may satisfy the abstract type

        >>> from graphql import (
        ...     assert_interface_type, assert_object_type, build_schema
        ... )
        >>> schema = build_schema('''
        ...     interface Node {
        ...       id: ID!
        ...     }
        ...
        ...     type User implements Node {
        ...       id: ID!
        ...     }
        ...
        ...     type Review {
        ...       body: String
        ...     }
        ...
        ...     type Query {
        ...       node: Node
        ...       review: Review
        ...     }
        ... ''')
        >>> Node = assert_interface_type(schema.get_type('Node'))
        >>> User = assert_object_type(schema.get_type('User'))
        >>> Review = assert_object_type(schema.get_type('Review'))
        >>> schema.is_sub_type(Node, User)
        True
        >>> schema.is_sub_type(Node, Review)
        False
        """
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
        """Get the directive with the provided name.

        :param name: the GraphQL name to look up
        :returns: the directive definition, if known

        >>> from graphql import build_schema
        >>> schema = build_schema('''
        ...     directive @upper on FIELD_DEFINITION
        ...
        ...     type Query {
        ...       greeting: String @upper
        ...     }
        ... ''')
        >>> schema.get_directive('upper').name
        'upper'
        >>> schema.get_directive('missing') is None
        True
        >>> [directive.name for directive in schema.directives]
        ['upper', 'include', 'skip', 'deprecated', 'specifiedBy', 'oneOf']
        """
        for directive in self.directives:
            if directive.name == name:
                return directive
        return None

    @property
    def validation_errors(self) -> Optional[List[GraphQLError]]:
        """Cached schema validation errors, if validation has already run."""
        return self._validation_errors


class TypeSet(Dict[GraphQLNamedType, None]):
    """An ordered set of types that can be collected starting from initial types."""

    @classmethod
    def with_initial_types(cls, types: Collection[GraphQLType]) -> "TypeSet":
        return cast(TypeSet, super().fromkeys(types))

    def collect_referenced_types(self, type_: GraphQLType) -> None:
        """Recursive function supplementing the type starting from an initial type."""
        named_type = get_named_type(type_)

        if named_type in self:
            return

        self[named_type] = None

        collect_referenced_types = self.collect_referenced_types
        if is_union_type(named_type):
            named_type = cast(GraphQLUnionType, named_type)
            for member_type in named_type.types:
                collect_referenced_types(member_type)
        elif is_object_type(named_type) or is_interface_type(named_type):
            named_type = cast(
                Union[GraphQLObjectType, GraphQLInterfaceType], named_type
            )
            for interface_type in named_type.interfaces:
                collect_referenced_types(interface_type)

            for field in named_type.fields.values():
                collect_referenced_types(field.type)
                for arg in field.args.values():
                    collect_referenced_types(arg.type)
        elif is_input_object_type(named_type):
            named_type = cast(GraphQLInputObjectType, named_type)
            for field in named_type.fields.values():
                collect_referenced_types(field.type)


def is_schema(schema: Any) -> bool:
    """Test if the given value is a GraphQL schema.

    :param schema: the value to inspect
    :returns: whether the value is a :class:`GraphQLSchema`

    >>> from graphql import GraphQLString, build_schema, is_schema
    >>> schema = build_schema('''
    ...     type Query {
    ...       greeting: String
    ...     }
    ... ''')
    >>> is_schema(schema)
    True
    >>> is_schema(GraphQLString)
    False
    """
    return isinstance(schema, GraphQLSchema)


def assert_schema(schema: Any) -> GraphQLSchema:
    """Return the value as a GraphQL schema, or raise if it is not a schema.

    :param schema: the value to inspect
    :returns: the value typed as a :class:`GraphQLSchema`

    >>> from graphql import GraphQLString, assert_schema, build_schema
    >>> schema = build_schema('''
    ...     type Query {
    ...       greeting: String
    ...     }
    ... ''')
    >>> assert_schema(schema) is schema
    True
    >>> assert_schema(GraphQLString)
    Traceback (most recent call last):
    ...
    TypeError: Expected String to be a GraphQL schema.
    """
    if not is_schema(schema):
        raise TypeError(f"Expected {inspect(schema)} to be a GraphQL schema.")
    return cast(GraphQLSchema, schema)


def remapped_type(type_: GraphQLType, type_map: TypeMap) -> GraphQLType:
    """Get a copy of the given type that uses this type map."""
    if is_wrapping_type(type_):
        type_ = cast(GraphQLWrappingType, type_)
        return type_.__class__(remapped_type(type_.of_type, type_map))
    type_ = cast(GraphQLNamedType, type_)
    return type_map.get(type_.name, type_)


def remap_named_type(type_: GraphQLNamedType, type_map: TypeMap) -> None:
    """Change all references in the given named type to use this type map."""
    if is_object_type(type_) or is_interface_type(type_):
        type_ = cast(Union[GraphQLObjectType, GraphQLInterfaceType], type_)
        type_.interfaces = [
            type_map.get(interface_type.name, interface_type)
            for interface_type in type_.interfaces
        ]
        fields = type_.fields
        for field_name, field in fields.items():
            field = copy(field)
            field.type = remapped_type(field.type, type_map)
            args = field.args
            for arg_name, arg in args.items():
                arg = copy(arg)
                arg.type = remapped_type(arg.type, type_map)
                args[arg_name] = arg
            fields[field_name] = field
    elif is_union_type(type_):
        type_ = cast(GraphQLUnionType, type_)
        type_.types = [
            type_map.get(member_type.name, member_type) for member_type in type_.types
        ]
    elif is_input_object_type(type_):
        type_ = cast(GraphQLInputObjectType, type_)
        fields = type_.fields
        for field_name, field in fields.items():
            field = copy(field)
            field.type = remapped_type(field.type, type_map)
            fields[field_name] = field


def remap_directive(directive: GraphQLDirective, type_map: TypeMap) -> None:
    """Change all references in the given directive to use this type map."""
    args = directive.args
    for arg_name, arg in args.items():
        arg = copy(arg)  # noqa: PLW2901
        arg.type = cast(GraphQLInputType, remapped_type(arg.type, type_map))
        args[arg_name] = arg
