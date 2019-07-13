from operator import attrgetter, itemgetter
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)


from ..error import GraphQLError
from ..pyutils import inspect
from ..language import NamedTypeNode, Node, OperationType, OperationTypeDefinitionNode
from .definition import (
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLUnionType,
    is_enum_type,
    is_input_object_type,
    is_input_type,
    is_interface_type,
    is_named_type,
    is_non_null_type,
    is_object_type,
    is_output_type,
    is_union_type,
    is_required_argument,
)
from ..utilities.assert_valid_name import is_valid_name_error
from ..utilities.type_comparators import is_equal_type, is_type_sub_type_of
from .directives import is_directive, GraphQLDirective
from .introspection import is_introspection_type
from .schema import GraphQLSchema, assert_schema

__all__ = ["validate_schema", "assert_valid_schema"]


def validate_schema(schema: GraphQLSchema) -> List[GraphQLError]:
    """Validate a GraphQL schema.

    Implements the "Type Validation" sub-sections of the specification's "Type System"
    section.

    Validation runs synchronously, returning a list of encountered errors, or an empty
    list if no errors were encountered and the Schema is valid.
    """
    # First check to ensure the provided value is in fact a GraphQLSchema.
    assert_schema(schema)

    # If this Schema has already been validated, return the previous results.
    # noinspection PyProtectedMember
    errors = schema._validation_errors
    if errors is None:

        # Validate the schema, producing a list of errors.
        context = SchemaValidationContext(schema)
        context.validate_root_types()
        context.validate_directives()
        context.validate_types()

        # Persist the results of validation before returning to ensure validation does
        # not run multiple times for this schema.
        errors = context.errors
        schema._validation_errors = errors

    return errors


def assert_valid_schema(schema: GraphQLSchema) -> None:
    """Utility function which asserts a schema is valid.

    Throws a TypeError if the schema is invalid.
    """
    errors = validate_schema(schema)
    if errors:
        raise TypeError("\n\n".join(error.message for error in errors))


class SchemaValidationContext:
    """Utility class providing a context for schema validation."""

    errors: List[GraphQLError]
    schema: GraphQLSchema

    def __init__(self, schema: GraphQLSchema) -> None:
        self.errors = []
        self.schema = schema

    def report_error(
        self,
        message: str,
        nodes: Union[Optional[Node], Sequence[Optional[Node]]] = None,
    ):
        if nodes and not isinstance(nodes, Node):
            nodes = [node for node in nodes if node]
        nodes = cast(Optional[Sequence[Node]], nodes)
        self.add_error(GraphQLError(message, nodes))

    def add_error(self, error: GraphQLError):
        self.errors.append(error)

    def validate_root_types(self):
        schema = self.schema

        query_type = schema.query_type
        if not query_type:
            self.report_error("Query root type must be provided.", schema.ast_node)
        elif not is_object_type(query_type):
            self.report_error(
                f"Query root type must be Object type, it cannot be {query_type}.",
                get_operation_type_node(schema, query_type, OperationType.QUERY),
            )

        mutation_type = schema.mutation_type
        if mutation_type and not is_object_type(mutation_type):
            self.report_error(
                "Mutation root type must be Object type if provided,"
                f" it cannot be {mutation_type}.",
                get_operation_type_node(schema, mutation_type, OperationType.MUTATION),
            )

        subscription_type = schema.subscription_type
        if subscription_type and not is_object_type(subscription_type):
            self.report_error(
                "Subscription root type must be Object type if provided,"
                f" it cannot be {subscription_type}.",
                get_operation_type_node(
                    schema, subscription_type, OperationType.SUBSCRIPTION
                ),
            )

    def validate_directives(self):
        directives = self.schema.directives
        for directive in directives:
            # Ensure all directives are in fact GraphQL directives.
            if not is_directive(directive):
                self.report_error(
                    f"Expected directive but got: {inspect(directive)}.",
                    getattr(directive, "ast_node", None),
                )
                continue

            # Ensure they are named correctly.
            self.validate_name(directive)

            # Ensure the arguments are valid.
            arg_names = set()
            for arg_name, arg in directive.args.items():
                # Ensure they are named correctly.
                self.validate_name(arg_name, arg)

                # Ensure they are unique per directive.
                if arg_name in arg_names:
                    self.report_error(
                        f"Argument @{directive.name}({arg_name}:)"
                        " can only be defined once.",
                        directive.ast_node
                        and [
                            arg.ast_node
                            for name, arg in directive.args.items()
                            if name == arg_name
                        ],
                    )
                    continue
                arg_names.add(arg_name)

                # Ensure the type is an input type.
                if not is_input_type(arg.type):
                    self.report_error(
                        f"The type of @{directive.name}({arg_name}:)"
                        f" must be Input Type but got: {inspect(arg.type)}.",
                        arg.ast_node,
                    )

    def validate_name(self, node: Any, name: str = None):
        # Ensure names are valid, however introspection types opt out.
        try:
            if not name:
                name = node.name
            name = cast(str, name)
            ast_node = node.ast_node
        except AttributeError:
            pass
        else:
            error = is_valid_name_error(name, ast_node)
            if error:
                self.add_error(error)

    def validate_types(self):
        validate_input_object_circular_refs = InputObjectCircularRefsValidator(self)
        for type_ in self.schema.type_map.values():

            # Ensure all provided types are in fact GraphQL type.
            if not is_named_type(type_):
                self.report_error(
                    f"Expected GraphQL named type but got: {inspect(type)}.",
                    type_.ast_node if type_ else None,
                )
                continue

            # Ensure it is named correctly (excluding introspection types).
            if not is_introspection_type(type_):
                self.validate_name(type_)

            if is_object_type(type_):
                type_ = cast(GraphQLObjectType, type_)
                # Ensure fields are valid
                self.validate_fields(type_)

                # Ensure objects implement the interfaces they claim to.
                self.validate_object_interfaces(type_)
            elif is_interface_type(type_):
                type_ = cast(GraphQLInterfaceType, type_)
                # Ensure fields are valid.
                self.validate_fields(type_)
            elif is_union_type(type_):
                type_ = cast(GraphQLUnionType, type_)
                # Ensure Unions include valid member types.
                self.validate_union_members(type_)
            elif is_enum_type(type_):
                type_ = cast(GraphQLEnumType, type_)
                # Ensure Enums have valid values.
                self.validate_enum_values(type_)
            elif is_input_object_type(type_):
                type_ = cast(GraphQLInputObjectType, type_)
                # Ensure Input Object fields are valid.
                self.validate_input_fields(type_)

                # Ensure Input Objects do not contain non-nullable circular references
                validate_input_object_circular_refs(type_)

    def validate_fields(self, type_: Union[GraphQLObjectType, GraphQLInterfaceType]):
        fields = type_.fields

        # Objects and Interfaces both must define one or more fields.
        if not fields:
            self.report_error(
                f"Type {type_.name} must define one or more fields.",
                get_all_nodes(type_),
            )

        for field_name, field in fields.items():

            # Ensure they are named correctly.
            self.validate_name(field, field_name)

            # Ensure the type is an output type
            if not is_output_type(field.type):
                self.report_error(
                    f"The type of {type_.name}.{field_name}"
                    " must be Output Type but got: {inspect(field.type)}.",
                    field.ast_node and field.ast_node.type,
                )

            # Ensure the arguments are valid.
            arg_names: Set[str] = set()
            for arg_name, arg in field.args.items():
                # Ensure they are named correctly.
                self.validate_name(arg, arg_name)

                # Ensure they are unique per field.
                if arg_name in arg_names:
                    self.report_error(
                        "Field argument"
                        f" {type_.name}.{field_name}({arg_name}:)"
                        " can only be defined once.",
                        [
                            arg.ast_node
                            for name, arg in field.args.items()
                            if name == arg_name
                        ],
                    )
                    break
                arg_names.add(arg_name)

                # Ensure the type is an input type.
                if not is_input_type(arg.type):
                    self.report_error(
                        "Field argument"
                        f" {type_.name}.{field_name}({arg_name}:)"
                        f" must be Input Type but got: {inspect(arg.type)}.",
                        arg.ast_node and arg.ast_node.type,
                    )

    def validate_object_interfaces(self, obj: GraphQLObjectType):
        implemented_type_names: Set[str] = set()
        for iface in obj.interfaces:
            if not is_interface_type(iface):
                self.report_error(
                    f"Type {obj.name} must only implement Interface"
                    f" types, it cannot implement {inspect(iface)}.",
                    get_all_implements_interface_nodes(obj, iface),
                )
                continue
            if iface.name in implemented_type_names:
                self.report_error(
                    f"Type {obj.name} can only implement {iface.name} once.",
                    get_all_implements_interface_nodes(obj, iface),
                )
                continue
            implemented_type_names.add(iface.name)
            self.validate_object_implements_interface(obj, iface)

    def validate_object_implements_interface(
        self, obj: GraphQLObjectType, iface: GraphQLInterfaceType
    ):
        obj_fields, iface_fields = obj.fields, iface.fields

        # Assert each interface field is implemented.
        for field_name, iface_field in iface_fields.items():
            obj_field = obj_fields.get(field_name)

            # Assert interface field exists on object.
            if not obj_field:
                self.report_error(
                    f"Interface field {iface.name}.{field_name}"
                    f" expected but {obj.name} does not provide it.",
                    [iface_field.ast_node, *get_all_nodes(obj)],
                )
                continue

            # Assert interface field type is satisfied by object field type, by being
            # a valid subtype (covariant).
            if not is_type_sub_type_of(self.schema, obj_field.type, iface_field.type):
                self.report_error(
                    f"Interface field {iface.name}.{field_name}"
                    f" expects type {iface_field.type}"
                    f" but {obj.name}.{field_name}"
                    f" is type {obj_field.type}.",
                    [
                        iface_field.ast_node and iface_field.ast_node.type,
                        obj_field.ast_node and obj_field.ast_node.type,
                    ],
                )

            # Assert each interface field arg is implemented.
            for arg_name, iface_arg in iface_field.args.items():
                obj_arg = obj_field.args.get(arg_name)

                # Assert interface field arg exists on object field.
                if not obj_arg:
                    self.report_error(
                        "Interface field argument"
                        f" {iface.name}.{field_name}({arg_name}:)"
                        f" expected but {obj.name}.{field_name}"
                        " does not provide it.",
                        [iface_arg.ast_node, obj_field.ast_node],
                    )
                    continue

                # Assert interface field arg type matches object field arg type
                # (invariant).
                if not is_equal_type(iface_arg.type, obj_arg.type):
                    self.report_error(
                        "Interface field argument"
                        f" {iface.name}.{field_name}({arg_name}:)"
                        f" expects type {iface_arg.type}"
                        f" but {obj.name}.{field_name}({arg_name}:)"
                        f" is type {obj_arg.type}.",
                        [
                            iface_arg.ast_node and iface_arg.ast_node.type,
                            obj_arg.ast_node and obj_arg.ast_node.type,
                        ],
                    )

            # Assert additional arguments must not be required.
            for arg_name, obj_arg in obj_field.args.items():
                iface_arg = iface_field.args.get(arg_name)
                if not iface_arg and is_required_argument(obj_arg):
                    self.report_error(
                        f"Object field {obj.name}.{field_name} includes"
                        f" required argument {arg_name} that is missing from"
                        f" the Interface field {iface.name}.{field_name}.",
                        [obj_arg.ast_node, iface_field.ast_node],
                    )

    def validate_union_members(self, union: GraphQLUnionType):
        member_types = union.types

        if not member_types:
            self.report_error(
                f"Union type {union.name} must define one or more member types.",
                get_all_nodes(union),
            )

        included_type_names: Set[str] = set()
        for member_type in member_types:
            if member_type.name in included_type_names:
                self.report_error(
                    f"Union type {union.name} can only include type"
                    f" {member_type.name} once.",
                    get_union_member_type_nodes(union, member_type.name),
                )
                continue
            included_type_names.add(member_type.name)

    def validate_enum_values(self, enum_type: GraphQLEnumType):
        enum_values = enum_type.values

        if not enum_values:
            self.report_error(
                f"Enum type {enum_type.name} must define one or more values.",
                get_all_nodes(enum_type),
            )

        for value_name, enum_value in enum_values.items():
            # Ensure valid name.
            self.validate_name(enum_value, value_name)
            if value_name in ("true", "false", "null"):
                self.report_error(
                    f"Enum type {enum_type.name} cannot include value:"
                    f" {value_name}.",
                    enum_value.ast_node,
                )

    def validate_input_fields(self, input_obj: GraphQLInputObjectType):
        fields = input_obj.fields

        if not fields:
            self.report_error(
                f"Input Object type {input_obj.name}"
                " must define one or more fields.",
                get_all_nodes(input_obj),
            )

        # Ensure the arguments are valid
        for field_name, field in fields.items():

            # Ensure they are named correctly.
            self.validate_name(field, field_name)

            # Ensure the type is an input type.
            if not is_input_type(field.type):
                self.report_error(
                    f"The type of {input_obj.name}.{field_name}"
                    f" must be Input Type but got: {inspect(field.type)}.",
                    field.ast_node.type if field.ast_node else None,
                )


def get_operation_type_node(
    schema: GraphQLSchema, type_: GraphQLObjectType, operation: OperationType
) -> Optional[Node]:
    operation_nodes = cast(
        List[OperationTypeDefinitionNode],
        get_all_sub_nodes(schema, attrgetter("operation_types")),
    )
    for node in operation_nodes:
        if node.operation == operation:
            return node.type
    return type_.ast_node


class InputObjectCircularRefsValidator:
    """Modified copy of algorithm from validation.rules.NoFragmentCycles"""

    def __init__(self, context: SchemaValidationContext):
        self.context = context
        # Tracks already visited types to maintain O(N) and to ensure that cycles
        # are not redundantly reported.
        self.visited_types: Set[str] = set()
        # Array of input fields used to produce meaningful errors
        self.field_path: List[Tuple[str, GraphQLInputField]] = []
        # Position in the type path
        self.field_path_index_by_type_name: Dict[str, int] = {}

    def __call__(self, input_obj: GraphQLInputObjectType):
        """Detect cycles recursively."""
        # This does a straight-forward DFS to find cycles.
        # It does not terminate when a cycle was found but continues to explore
        # the graph to find all possible cycles.
        name = input_obj.name
        if name in self.visited_types:
            return

        self.visited_types.add(name)
        self.field_path_index_by_type_name[name] = len(self.field_path)

        for field_name, field in input_obj.fields.items():
            if is_non_null_type(field.type) and is_input_object_type(
                field.type.of_type
            ):
                field_type = cast(GraphQLInputObjectType, field.type.of_type)
                cycle_index = self.field_path_index_by_type_name.get(field_type.name)

                self.field_path.append((field_name, field))
                if cycle_index is None:
                    self(field_type)
                else:
                    cycle_path = self.field_path[cycle_index:]
                    field_names = map(itemgetter(0), cycle_path)
                    self.context.report_error(
                        f"Cannot reference Input Object '{field_type.name}'"
                        " within itself through a series of non-null fields:"
                        f" '{'.'.join(field_names)}'.",
                        cast(
                            Sequence[Node],
                            map(attrgetter("ast_node"), map(itemgetter(1), cycle_path)),
                        ),
                    )
                self.field_path.pop()

        del self.field_path_index_by_type_name[name]


SDLDefinedObject = Union[
    GraphQLSchema,
    GraphQLDirective,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLInputObjectType,
    GraphQLUnionType,
    GraphQLEnumType,
]


def get_all_nodes(obj: SDLDefinedObject) -> List[Node]:
    node = obj.ast_node
    nodes: List[Node] = [node] if node else []
    extension_nodes = getattr(obj, "extension_ast_nodes", None)
    if extension_nodes:
        nodes.extend(extension_nodes)
    return nodes


def get_all_sub_nodes(
    obj: SDLDefinedObject, getter: Callable[[Node], List[Node]]
) -> List[Node]:
    result: List[Node] = []
    for ast_node in get_all_nodes(obj):
        sub_nodes = getter(ast_node)
        if sub_nodes:
            result.extend(sub_nodes)
    return result


def get_all_implements_interface_nodes(
    type_: GraphQLObjectType, iface: GraphQLInterfaceType
) -> List[NamedTypeNode]:
    implements_nodes = cast(
        List[NamedTypeNode], get_all_sub_nodes(type_, attrgetter("interfaces"))
    )
    return [
        iface_node
        for iface_node in implements_nodes
        if iface_node.name.value == iface.name
    ]


def get_union_member_type_nodes(
    union: GraphQLUnionType, type_name: str
) -> Optional[List[NamedTypeNode]]:
    union_nodes = cast(
        List[NamedTypeNode], get_all_sub_nodes(union, attrgetter("types"))
    )
    return [
        union_node for union_node in union_nodes if union_node.name.value == type_name
    ]
