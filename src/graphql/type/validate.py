"""Schema validation"""

from __future__ import annotations

from collections import defaultdict
from operator import attrgetter, itemgetter
from typing import Any, Collection, Optional, cast

from ..error import GraphQLError
from ..language import (
    DirectiveNode,
    InputValueDefinitionNode,
    NamedTypeNode,
    Node,
    OperationType,
    SchemaDefinitionNode,
    SchemaExtensionNode,
)
from ..pyutils import Undefined, and_list, inspect
from ..utilities.type_comparators import is_equal_type, is_type_sub_type_of
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
    is_required_argument,
    is_required_input_field,
    is_union_type,
)
from .directives import GraphQLDeprecatedDirective, is_directive
from .introspection import is_introspection_type
from .schema import GraphQLSchema, assert_schema

__all__ = ["assert_valid_schema", "validate_schema"]


def validate_schema(schema: GraphQLSchema) -> list[GraphQLError]:
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
    errors = schema._validation_errors  # noqa: SLF001
    if errors is None:
        # Validate the schema, producing a list of errors.
        context = SchemaValidationContext(schema)
        context.validate_root_types()
        context.validate_directives()
        context.validate_types()

        # Persist the results of validation before returning to ensure validation does
        # not run multiple times for this schema.
        errors = context.errors
        schema._validation_errors = errors  # noqa: SLF001

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

    errors: list[GraphQLError]
    schema: GraphQLSchema

    def __init__(self, schema: GraphQLSchema) -> None:
        self.errors = []
        self.schema = schema

    def report_error(
        self,
        message: str,
        nodes: Node | None | Collection[Node | None] = None,
    ) -> None:
        if nodes and not isinstance(nodes, Node):
            nodes = [node for node in nodes if node]
        nodes = cast("Optional[Collection[Node]]", nodes)
        self.errors.append(GraphQLError(message, nodes))

    def validate_root_types(self) -> None:
        schema = self.schema
        if not schema.query_type:
            self.report_error("Query root type must be provided.", schema.ast_node)
        root_types_map: dict[GraphQLObjectType, list[OperationType]] = defaultdict(list)

        for operation_type in OperationType:
            root_type = schema.get_root_type(operation_type)
            if root_type:
                if is_object_type(root_type):
                    root_types_map[root_type].append(operation_type)
                else:
                    operation_type_str = operation_type.value.capitalize()
                    root_type_str = inspect(root_type)
                    if_provided_str = (
                        "" if operation_type == operation_type.QUERY else " if provided"
                    )
                    self.report_error(
                        f"{operation_type_str} root type must be Object type"
                        f"{if_provided_str}, it cannot be {root_type_str}.",
                        get_operation_type_node(schema, operation_type)
                        or root_type.ast_node,
                    )
        for root_type, operation_types in root_types_map.items():
            if len(operation_types) > 1:
                operation_list = and_list(
                    [operation_type.value for operation_type in operation_types]
                )
                self.report_error(
                    "All root types must be different,"
                    f" '{root_type.name}' type is used as {operation_list} root types.",
                    [
                        get_operation_type_node(schema, operation_type)
                        for operation_type in operation_types
                    ],
                )

    def validate_directives(self) -> None:
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
            for arg_name, arg in directive.args.items():
                # Ensure they are named correctly.
                self.validate_name(arg, arg_name)

                # Ensure the type is an input type.
                if not is_input_type(arg.type):
                    self.report_error(
                        f"The type of @{directive.name}({arg_name}:)"
                        f" must be Input Type but got: {inspect(arg.type)}.",
                        arg.ast_node,
                    )

                if is_required_argument(arg) and arg.deprecation_reason is not None:
                    self.report_error(
                        f"Required argument @{directive.name}({arg_name}:)"
                        " cannot be deprecated.",
                        [
                            get_deprecated_directive_node(arg.ast_node),
                            arg.ast_node and arg.ast_node.type,
                        ],
                    )

    def validate_name(self, node: Any, name: str | None = None) -> None:
        # Ensure names are valid, however introspection types opt out.
        try:
            if not name:
                name = node.name
            name = cast("str", name)
            ast_node = node.ast_node
        except AttributeError:  # pragma: no cover
            pass
        else:
            if name.startswith("__"):
                self.report_error(
                    f"Name {name!r} must not begin with '__',"
                    " which is reserved by GraphQL introspection.",
                    ast_node,
                )

    def validate_types(self) -> None:
        validate_input_object_circular_refs = InputObjectCircularRefsValidator(self)
        for type_ in self.schema.type_map.values():
            # Ensure all provided types are in fact GraphQL type.
            if not is_named_type(type_):
                self.report_error(
                    f"Expected GraphQL named type but got: {inspect(type_)}.",
                    type_.ast_node if is_named_type(type_) else None,
                )
                continue

            # Ensure it is named correctly (excluding introspection types).
            if not is_introspection_type(type_):
                self.validate_name(type_)

            if is_object_type(type_):
                # Ensure fields are valid
                self.validate_fields(type_)

                # Ensure objects implement the interfaces they claim to.
                self.validate_interfaces(type_)
            elif is_interface_type(type_):
                # Ensure fields are valid.
                self.validate_fields(type_)

                # Ensure interfaces implement the interfaces they claim to.
                self.validate_interfaces(type_)
            elif is_union_type(type_):
                # Ensure Unions include valid member types.
                self.validate_union_members(type_)
            elif is_enum_type(type_):
                # Ensure Enums have valid values.
                self.validate_enum_values(type_)
            elif is_input_object_type(type_):
                # Ensure Input Object fields are valid.
                self.validate_input_fields(type_)

                # Ensure Input Objects do not contain non-nullable circular references
                validate_input_object_circular_refs(type_)

    def validate_fields(self, type_: GraphQLObjectType | GraphQLInterfaceType) -> None:
        fields = type_.fields

        # Objects and Interfaces both must define one or more fields.
        if not fields:
            self.report_error(
                f"Type {type_.name} must define one or more fields.",
                [type_.ast_node, *type_.extension_ast_nodes],
            )

        for field_name, field in fields.items():
            # Ensure they are named correctly.
            self.validate_name(field, field_name)

            # Ensure the type is an output type
            if not is_output_type(field.type):
                self.report_error(
                    f"The type of {type_.name}.{field_name}"
                    f" must be Output Type but got: {inspect(field.type)}.",
                    field.ast_node and field.ast_node.type,
                )

            # Ensure the arguments are valid.
            for arg_name, arg in field.args.items():
                # Ensure they are named correctly.
                self.validate_name(arg, arg_name)

                # Ensure the type is an input type.
                if not is_input_type(arg.type):
                    self.report_error(
                        f"The type of {type_.name}.{field_name}({arg_name}:)"
                        f" must be Input Type but got: {inspect(arg.type)}.",
                        arg.ast_node and arg.ast_node.type,
                    )

                if is_required_argument(arg) and arg.deprecation_reason is not None:
                    self.report_error(
                        f"Required argument {type_.name}.{field_name}({arg_name}:)"
                        " cannot be deprecated.",
                        [
                            get_deprecated_directive_node(arg.ast_node),
                            arg.ast_node and arg.ast_node.type,
                        ],
                    )

    def validate_interfaces(
        self, type_: GraphQLObjectType | GraphQLInterfaceType
    ) -> None:
        iface_type_names: set[str] = set()
        for iface in type_.interfaces:
            if not is_interface_type(iface):
                self.report_error(
                    f"Type {type_.name} must only implement Interface"
                    f" types, it cannot implement {inspect(iface)}.",
                    get_all_implements_interface_nodes(type_, iface),
                )
                continue

            if type_ is iface:
                self.report_error(
                    f"Type {type_.name} cannot implement itself"
                    " because it would create a circular reference.",
                    get_all_implements_interface_nodes(type_, iface),
                )

            if iface.name in iface_type_names:
                self.report_error(
                    f"Type {type_.name} can only implement {iface.name} once.",
                    get_all_implements_interface_nodes(type_, iface),
                )
                continue

            iface_type_names.add(iface.name)

            self.validate_type_implements_ancestors(type_, iface)
            self.validate_type_implements_interface(type_, iface)

    def validate_type_implements_interface(
        self,
        type_: GraphQLObjectType | GraphQLInterfaceType,
        iface: GraphQLInterfaceType,
    ) -> None:
        type_fields, iface_fields = type_.fields, iface.fields

        # Assert each interface field is implemented.
        for field_name, iface_field in iface_fields.items():
            type_field = type_fields.get(field_name)

            # Assert interface field exists on object.
            if not type_field:
                self.report_error(
                    f"Interface field {iface.name}.{field_name}"
                    f" expected but {type_.name} does not provide it.",
                    [
                        iface_field.ast_node,
                        type_.ast_node,
                        *type_.extension_ast_nodes,
                    ],
                )
                continue

            # Assert interface field type is satisfied by type field type, by being
            # a valid subtype (covariant).
            if not is_type_sub_type_of(self.schema, type_field.type, iface_field.type):
                self.report_error(
                    f"Interface field {iface.name}.{field_name}"
                    f" expects type {iface_field.type}"
                    f" but {type_.name}.{field_name}"
                    f" is type {type_field.type}.",
                    [
                        iface_field.ast_node and iface_field.ast_node.type,
                        type_field.ast_node and type_field.ast_node.type,
                    ],
                )

            # Assert each interface field arg is implemented.
            for arg_name, iface_arg in iface_field.args.items():
                type_arg = type_field.args.get(arg_name)

                # Assert interface field arg exists on object field.
                if not type_arg:
                    self.report_error(
                        "Interface field argument"
                        f" {iface.name}.{field_name}({arg_name}:)"
                        f" expected but {type_.name}.{field_name}"
                        " does not provide it.",
                        [iface_arg.ast_node, type_field.ast_node],
                    )
                    continue

                # Assert interface field arg type matches object field arg type
                # (invariant).
                if not is_equal_type(iface_arg.type, type_arg.type):
                    self.report_error(
                        "Interface field argument"
                        f" {iface.name}.{field_name}({arg_name}:)"
                        f" expects type {iface_arg.type}"
                        f" but {type_.name}.{field_name}({arg_name}:)"
                        f" is type {type_arg.type}.",
                        [
                            iface_arg.ast_node and iface_arg.ast_node.type,
                            type_arg.ast_node and type_arg.ast_node.type,
                        ],
                    )

            # Assert additional arguments must not be required.
            for arg_name, type_arg in type_field.args.items():
                iface_arg = iface_field.args.get(arg_name)
                if not iface_arg and is_required_argument(type_arg):
                    self.report_error(
                        f"Object field {type_.name}.{field_name} includes"
                        f" required argument {arg_name} that is missing from"
                        f" the Interface field {iface.name}.{field_name}.",
                        [type_arg.ast_node, iface_field.ast_node],
                    )

    def validate_type_implements_ancestors(
        self,
        type_: GraphQLObjectType | GraphQLInterfaceType,
        iface: GraphQLInterfaceType,
    ) -> None:
        type_interfaces, iface_interfaces = type_.interfaces, iface.interfaces
        for transitive in iface_interfaces:
            if transitive not in type_interfaces:
                self.report_error(
                    f"Type {type_.name} cannot implement {iface.name}"
                    " because it would create a circular reference."
                    if transitive is type_
                    else f"Type {type_.name} must implement {transitive.name}"
                    f" because it is implemented by {iface.name}.",
                    get_all_implements_interface_nodes(iface, transitive)
                    + get_all_implements_interface_nodes(type_, iface),
                )

    def validate_union_members(self, union: GraphQLUnionType) -> None:
        member_types = union.types

        if not member_types:
            self.report_error(
                f"Union type {union.name} must define one or more member types.",
                [union.ast_node, *union.extension_ast_nodes],
            )

        included_type_names: set[str] = set()
        for member_type in member_types:
            if is_object_type(member_type):
                if member_type.name in included_type_names:
                    self.report_error(
                        f"Union type {union.name} can only include type"
                        f" {member_type.name} once.",
                        get_union_member_type_nodes(union, member_type.name),
                    )
                else:
                    included_type_names.add(member_type.name)
            else:
                self.report_error(
                    f"Union type {union.name} can only include Object types,"
                    f" it cannot include {inspect(member_type)}.",
                    get_union_member_type_nodes(union, str(member_type)),
                )

    def validate_enum_values(self, enum_type: GraphQLEnumType) -> None:
        enum_values = enum_type.values

        if not enum_values:
            self.report_error(
                f"Enum type {enum_type.name} must define one or more values.",
                [enum_type.ast_node, *enum_type.extension_ast_nodes],
            )

        for value_name, enum_value in enum_values.items():
            # Ensure valid name.
            self.validate_name(enum_value, value_name)

    def validate_input_fields(self, input_obj: GraphQLInputObjectType) -> None:
        fields = input_obj.fields

        if not fields:
            self.report_error(
                f"Input Object type {input_obj.name} must define one or more fields.",
                [input_obj.ast_node, *input_obj.extension_ast_nodes],
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

            if is_required_input_field(field) and field.deprecation_reason is not None:
                self.report_error(
                    f"Required input field {input_obj.name}.{field_name}"
                    " cannot be deprecated.",
                    [
                        get_deprecated_directive_node(field.ast_node),
                        field.ast_node and field.ast_node.type,
                    ],
                )

            if input_obj.is_one_of:
                self.validate_one_of_input_object_field(input_obj, field_name, field)

    def validate_one_of_input_object_field(
        self,
        type_: GraphQLInputObjectType,
        field_name: str,
        field: GraphQLInputField,
    ) -> None:
        if is_non_null_type(field.type):
            self.report_error(
                f"OneOf input field {type_.name}.{field_name} must be nullable.",
                field.ast_node and field.ast_node.type,
            )

        if field.default_value is not Undefined:
            self.report_error(
                f"OneOf input field {type_.name}.{field_name}"
                " cannot have a default value.",
                field.ast_node,
            )


def get_operation_type_node(
    schema: GraphQLSchema, operation: OperationType
) -> Node | None:
    ast_node: SchemaDefinitionNode | SchemaExtensionNode | None
    for ast_node in [schema.ast_node, *(schema.extension_ast_nodes or ())]:
        if ast_node:
            operation_types = ast_node.operation_types
            if operation_types:  # pragma: no cover else
                for operation_type in operation_types:
                    if operation_type.operation == operation:
                        return operation_type.type
    return None


class InputObjectCircularRefsValidator:
    """Modified copy of algorithm from validation.rules.NoFragmentCycles"""

    def __init__(self, context: SchemaValidationContext) -> None:
        self.context = context
        # Tracks already visited types to maintain O(N) and to ensure that cycles
        # are not redundantly reported.
        self.visited_types: set[str] = set()
        # Array of input fields used to produce meaningful errors
        self.field_path: list[tuple[str, GraphQLInputField]] = []
        # Position in the type path
        self.field_path_index_by_type_name: dict[str, int] = {}

    def __call__(self, input_obj: GraphQLInputObjectType) -> None:
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
                field_type = field.type.of_type
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
                            "Collection[Node]",
                            map(attrgetter("ast_node"), map(itemgetter(1), cycle_path)),
                        ),
                    )
                self.field_path.pop()

        del self.field_path_index_by_type_name[name]


def get_all_implements_interface_nodes(
    type_: GraphQLObjectType | GraphQLInterfaceType, iface: GraphQLInterfaceType
) -> list[NamedTypeNode]:
    ast_node = type_.ast_node
    nodes = type_.extension_ast_nodes
    if ast_node is not None:
        nodes = [ast_node, *nodes]  # type: ignore
    implements_nodes: list[NamedTypeNode] = []
    for node in nodes:
        iface_nodes = node.interfaces
        if iface_nodes:  # pragma: no cover else
            implements_nodes.extend(
                iface_node
                for iface_node in iface_nodes
                if iface_node.name.value == iface.name
            )
    return implements_nodes


def get_union_member_type_nodes(
    union: GraphQLUnionType, type_name: str
) -> list[NamedTypeNode]:
    ast_node = union.ast_node
    nodes = union.extension_ast_nodes
    if ast_node is not None:
        nodes = [ast_node, *nodes]  # type: ignore
    member_type_nodes: list[NamedTypeNode] = []
    for node in nodes:
        type_nodes = node.types
        if type_nodes:  # pragma: no cover else
            member_type_nodes.extend(
                type_node
                for type_node in type_nodes
                if type_node.name.value == type_name
            )
    return member_type_nodes


def get_deprecated_directive_node(
    definition_node: InputValueDefinitionNode | None,
) -> DirectiveNode | None:
    directives = definition_node and definition_node.directives
    if directives:
        for directive in directives:
            if (
                directive.name.value == GraphQLDeprecatedDirective.name
            ):  # pragma: no cover else
                return directive
    return None  # pragma: no cover
