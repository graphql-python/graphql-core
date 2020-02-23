from typing import Any, Callable, List, Optional, Union, cast

from ..language import (
    ArgumentNode,
    DirectiveNode,
    EnumValueNode,
    FieldNode,
    InlineFragmentNode,
    ListValueNode,
    Node,
    ObjectFieldNode,
    OperationDefinitionNode,
    SelectionSetNode,
    VariableDefinitionNode,
    Visitor,
)
from ..pyutils import Undefined
from ..type import (
    GraphQLArgument,
    GraphQLCompositeType,
    GraphQLDirective,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLSchema,
    GraphQLType,
    is_composite_type,
    is_input_type,
    is_output_type,
    get_named_type,
    SchemaMetaFieldDef,
    TypeMetaFieldDef,
    TypeNameMetaFieldDef,
    is_object_type,
    is_interface_type,
    get_nullable_type,
    is_list_type,
    is_input_object_type,
    is_enum_type,
)
from .type_from_ast import type_from_ast

__all__ = ["TypeInfo", "TypeInfoVisitor"]


GetFieldDefType = Callable[
    [GraphQLSchema, GraphQLType, FieldNode], Optional[GraphQLField]
]


class TypeInfo:
    """Utility class for keeping track of type definitions.

    TypeInfo is a utility class which, given a GraphQL schema, can keep track of the
    current field and type definitions at any point in a GraphQL document AST during
    a recursive descent by calling `enter(node)` and `leave(node)`.
    """

    def __init__(
        self,
        schema: GraphQLSchema,
        get_field_def_fn: Optional[GetFieldDefType] = None,
        initial_type: Optional[GraphQLType] = None,
    ) -> None:
        """Initialize the TypeInfo for the given GraphQL schema.

        The experimental optional second parameter is only needed in order to support
        non-spec-compliant code bases. You should never need to use it. It may disappear
        in the future.

        Initial type may be provided in rare cases to facilitate traversals beginning
        somewhere other than documents.
        """
        self._schema = schema
        self._type_stack: List[Optional[GraphQLOutputType]] = []
        self._parent_type_stack: List[Optional[GraphQLCompositeType]] = []
        self._input_type_stack: List[Optional[GraphQLInputType]] = []
        self._field_def_stack: List[Optional[GraphQLField]] = []
        self._default_value_stack: List[Any] = []
        self._directive: Optional[GraphQLDirective] = None
        self._argument: Optional[GraphQLArgument] = None
        self._enum_value: Optional[GraphQLEnumValue] = None
        self._get_field_def = get_field_def_fn or get_field_def
        if initial_type:
            if is_input_type(initial_type):
                self._input_type_stack.append(cast(GraphQLInputType, initial_type))
            if is_composite_type(initial_type):
                self._parent_type_stack.append(cast(GraphQLCompositeType, initial_type))
            if is_output_type(initial_type):
                self._type_stack.append(cast(GraphQLOutputType, initial_type))

    def get_type(self):
        if self._type_stack:
            return self._type_stack[-1]

    def get_parent_type(self):
        if self._parent_type_stack:
            return self._parent_type_stack[-1]

    def get_input_type(self):
        if self._input_type_stack:
            return self._input_type_stack[-1]

    def get_parent_input_type(self):
        if len(self._input_type_stack) > 1:
            return self._input_type_stack[-2]

    def get_field_def(self):
        if self._field_def_stack:
            return self._field_def_stack[-1]

    def get_default_value(self):
        if self._default_value_stack:
            return self._default_value_stack[-1]

    def get_directive(self):
        return self._directive

    def get_argument(self):
        return self._argument

    def get_enum_value(self):
        return self._enum_value

    def enter(self, node: Node):
        method = getattr(self, "enter_" + node.kind, None)
        if method:
            return method(node)

    def leave(self, node: Node):
        method = getattr(self, "leave_" + node.kind, None)
        if method:
            return method()

    # noinspection PyUnusedLocal
    def enter_selection_set(self, node: SelectionSetNode):
        named_type = get_named_type(self.get_type())
        self._parent_type_stack.append(
            named_type if is_composite_type(named_type) else None
        )

    def enter_field(self, node: FieldNode):
        parent_type = self.get_parent_type()
        if parent_type:
            field_def = self._get_field_def(self._schema, parent_type, node)
            field_type = field_def.type if field_def else None
        else:
            field_def = field_type = None
        self._field_def_stack.append(field_def)
        self._type_stack.append(field_type if is_output_type(field_type) else None)

    def enter_directive(self, node: DirectiveNode):
        self._directive = self._schema.get_directive(node.name.value)

    def enter_operation_definition(self, node: OperationDefinitionNode):
        type_ = getattr(self._schema, f"{node.operation.value}_type")
        self._type_stack.append(type_ if is_object_type(type_) else None)

    def enter_inline_fragment(self, node: InlineFragmentNode):
        type_condition_ast = node.type_condition
        output_type = (
            type_from_ast(self._schema, type_condition_ast)
            if type_condition_ast
            else get_named_type(self.get_type())
        )
        self._type_stack.append(
            cast(GraphQLOutputType, output_type)
            if is_output_type(output_type)
            else None
        )

    enter_fragment_definition = enter_inline_fragment

    def enter_variable_definition(self, node: VariableDefinitionNode):
        input_type = type_from_ast(self._schema, node.type)
        self._input_type_stack.append(
            cast(GraphQLInputType, input_type) if is_input_type(input_type) else None
        )

    def enter_argument(self, node: ArgumentNode):
        field_or_directive = self.get_directive() or self.get_field_def()
        if field_or_directive:
            arg_def = field_or_directive.args.get(node.name.value)
            arg_type = arg_def.type if arg_def else None
        else:
            arg_def = arg_type = None
        self._argument = arg_def
        self._default_value_stack.append(
            arg_def.default_value if arg_def else Undefined
        )
        self._input_type_stack.append(arg_type if is_input_type(arg_type) else None)

    # noinspection PyUnusedLocal
    def enter_list_value(self, node: ListValueNode):
        list_type = get_nullable_type(self.get_input_type())
        item_type = list_type.of_type if is_list_type(list_type) else list_type
        # List positions never have a default value.
        self._default_value_stack.append(Undefined)
        self._input_type_stack.append(item_type if is_input_type(item_type) else None)

    def enter_object_field(self, node: ObjectFieldNode):
        object_type = get_named_type(self.get_input_type())
        if is_input_object_type(object_type):
            input_field = object_type.fields.get(node.name.value)
            input_field_type = input_field.type if input_field else None
        else:
            input_field = input_field_type = None
        self._default_value_stack.append(
            input_field.default_value if input_field else Undefined
        )
        self._input_type_stack.append(
            input_field_type if is_input_type(input_field_type) else None
        )

    def enter_enum_value(self, node: EnumValueNode):
        enum_type = get_named_type(self.get_input_type())
        if is_enum_type(enum_type):
            enum_value = enum_type.values.get(node.value)
        else:
            enum_value = None
        self._enum_value = enum_value

    def leave_selection_set(self):
        del self._parent_type_stack[-1:]

    def leave_field(self):
        del self._field_def_stack[-1:]
        del self._type_stack[-1:]

    def leave_directive(self):
        self._directive = None

    def leave_operation_definition(self):
        del self._type_stack[-1:]

    leave_inline_fragment = leave_operation_definition
    leave_fragment_definition = leave_operation_definition

    def leave_variable_definition(self):
        del self._input_type_stack[-1:]

    def leave_argument(self):
        self._argument = None
        del self._default_value_stack[-1:]
        del self._input_type_stack[-1:]

    def leave_list_value(self):
        del self._default_value_stack[-1:]
        del self._input_type_stack[-1:]

    leave_object_field = leave_list_value

    def leave_enum_value(self):
        self._enum_value = None


def get_field_def(
    schema: GraphQLSchema, parent_type: GraphQLType, field_node: FieldNode
) -> Optional[GraphQLField]:
    """Get field definition.

    Not exactly the same as the executor's definition of `get_field_def()`, in this
    statically evaluated environment we do not always have an Object type, and need
    to handle Interface and Union types.
    """
    name = field_node.name.value
    if name == "__schema" and schema.query_type is parent_type:
        return SchemaMetaFieldDef
    if name == "__type" and schema.query_type is parent_type:
        return TypeMetaFieldDef
    if name == "__typename" and is_composite_type(parent_type):
        return TypeNameMetaFieldDef
    if is_object_type(parent_type) or is_interface_type(parent_type):
        parent_type = cast(Union[GraphQLObjectType, GraphQLInterfaceType], parent_type)
        return parent_type.fields.get(name)
    return None


class TypeInfoVisitor(Visitor):
    """A visitor which maintains a provided TypeInfo."""

    def __init__(self, type_info: "TypeInfo", visitor: Visitor):
        self.type_info = type_info
        self.visitor = visitor

    def enter(self, node, *args):
        self.type_info.enter(node)
        fn = self.visitor.get_visit_fn(node.kind)
        if fn:
            result = fn(self.visitor, node, *args)
            if result is not None:
                self.type_info.leave(node)
                if isinstance(result, Node):
                    self.type_info.enter(result)
            return result

    def leave(self, node, *args):
        fn = self.visitor.get_visit_fn(node.kind, is_leaving=True)
        result = fn(self.visitor, node, *args) if fn else None
        self.type_info.leave(node)
        return result
