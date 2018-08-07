from ...error import GraphQLError, INVALID
from ...language import DirectiveNode, FieldNode
from ...type import is_non_null_type
from . import ValidationRule

__all__ = [
    'ProvidedRequiredArgumentsRule',
    'missing_field_arg_message', 'missing_directive_arg_message']


def missing_field_arg_message(
        field_name: str, arg_name: str, type_: str) -> str:
    return (f"Field '{field_name}' argument '{arg_name}'"
            f" of type '{type_}' is required but not provided.")


def missing_directive_arg_message(
        directive_name: str, arg_name: str, type_: str) -> str:
    return (f"Directive '@{directive_name}' argument '{arg_name}'"
            f" of type '{type_}' is required but not provided.")


class ProvidedRequiredArgumentsRule(ValidationRule):
    """Provided required arguments

    A field or directive is only valid if all required (non-null without a
    default value) field arguments have been provided.
    """

    def leave_field(self, node: FieldNode, *_args):
        # Validate on leave to allow for deeper errors to appear first.
        field_def = self.context.get_field_def()
        if not field_def:
            return self.SKIP
        arg_nodes = node.arguments or []

        arg_node_map = {arg.name.value: arg for arg in arg_nodes}
        for arg_name, arg_def in field_def.args.items():
            arg_node = arg_node_map.get(arg_name)
            if not arg_node and is_non_null_type(
                    arg_def.type) and arg_def.default_value is INVALID:
                self.report_error(GraphQLError(missing_field_arg_message(
                    node.name.value, arg_name, str(arg_def.type)), [node]))

    def leave_directive(self, node: DirectiveNode, *_args):
        # Validate on leave to allow for deeper errors to appear first.
        directive_def = self.context.get_directive()
        if not directive_def:
            return False
        arg_nodes = node.arguments or []

        arg_node_map = {arg.name.value: arg for arg in arg_nodes}
        for arg_name, arg_def in directive_def.args.items():
            arg_node = arg_node_map.get(arg_name)
            if not arg_node and is_non_null_type(
                    arg_def.type) and arg_def.default_value is INVALID:
                self.report_error(GraphQLError(missing_directive_arg_message(
                    node.name.value, arg_name, str(arg_def.type)), [node]))
