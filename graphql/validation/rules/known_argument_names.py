from typing import List

from ...error import GraphQLError
from ...language import FieldNode, DirectiveNode
from ...pyutils import quoted_or_list, suggestion_list
from . import ValidationRule

__all__ = [
    'KnownArgumentNamesRule',
    'unknown_arg_message', 'unknown_directive_arg_message']


def unknown_arg_message(
        arg_name: str, field_name: str, type_name: str,
        suggested_args: List[str]) -> str:
    message = (f"Unknown argument '{arg_name}' on field '{field_name}'"
               f" of type '{type_name}'.")
    if suggested_args:
        message += f' Did you mean {quoted_or_list(suggested_args)}?'
    return message


def unknown_directive_arg_message(
        arg_name: str, directive_name: str,
        suggested_args: List[str]) -> str:
    message = (f"Unknown argument '{arg_name}'"
               f" on directive '@{directive_name}'.")
    if suggested_args:
        message += f' Did you mean {quoted_or_list(suggested_args)}?'
    return message


class KnownArgumentNamesRule(ValidationRule):
    """Known argument names

    A GraphQL field is only valid if all supplied arguments are defined by
    that field.
    """

    def enter_argument(self, node, _key, _parent, _path, ancestors):
        context = self.context
        arg_def = context.get_argument()
        if not arg_def:
            argument_of = ancestors[-1]
            if isinstance(argument_of, FieldNode):
                field_def = context.get_field_def()
                parent_type = context.get_parent_type()
                if field_def and parent_type:
                    context.report_error(GraphQLError(
                        unknown_arg_message(
                            node.name.value,
                            argument_of.name.value,
                            parent_type.name,
                            suggestion_list(
                                node.name.value, list(field_def.args))),
                        [node]))
            elif isinstance(argument_of, DirectiveNode):
                directive = context.get_directive()
                if directive:
                    context.report_error(GraphQLError(
                        unknown_directive_arg_message(
                            node.name.value,
                            directive.name,
                            suggestion_list(
                                node.name.value, list(directive.args))),
                        [node]))
