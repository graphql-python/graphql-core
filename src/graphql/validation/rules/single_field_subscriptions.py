from typing import Any, Dict, cast

from ...error import GraphQLError
from ...execution import ExecutionContext, default_field_resolver, default_type_resolver
from ...language import (
    FieldNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    OperationType,
)
from . import ValidationRule

__all__ = ["SingleFieldSubscriptionsRule"]


class SingleFieldSubscriptionsRule(ValidationRule):
    """Subscriptions must only include a single non-introspection field.

    A GraphQL subscription is valid only if it contains a single root field and
    that root field is not an introspection field.
    """

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> None:
        if node.operation == OperationType.SUBSCRIPTION:
            schema = self.context.schema
            subscription_type = schema.subscription_type
            if subscription_type:
                operation_name = node.name.value if node.name else None
                variable_values: Dict[str, Any] = {}
                document = self.context.document
                fragments: Dict[str, FragmentDefinitionNode] = {
                    definition.name.value: definition
                    for definition in document.definitions
                    if isinstance(definition, FragmentDefinitionNode)
                }
                fake_execution_context = ExecutionContext(
                    schema,
                    fragments,
                    root_value=None,
                    context_value=None,
                    operation=node,
                    variable_values=variable_values,
                    field_resolver=default_field_resolver,
                    type_resolver=default_type_resolver,
                    errors=[],
                    middleware_manager=None,
                    is_awaitable=None,
                )
                fields = fake_execution_context.collect_fields(
                    subscription_type, node.selection_set, {}, set()
                )
                if len(fields) > 1:
                    field_selection_lists = list(fields.values())
                    extra_field_selection_lists = field_selection_lists[1:]
                    extra_field_selection = [
                        field
                        for fields in extra_field_selection_lists
                        for field in (
                            fields
                            if isinstance(fields, list)
                            else [cast(FieldNode, fields)]
                        )
                    ]
                    self.report_error(
                        GraphQLError(
                            (
                                "Anonymous Subscription"
                                if operation_name is None
                                else f"Subscription '{operation_name}'"
                            )
                            + " must select only one top level field.",
                            extra_field_selection,
                        )
                    )
                for field_nodes in fields.values():
                    field = field_nodes[0]
                    field_name = field.name.value
                    if field_name.startswith("__"):
                        self.report_error(
                            GraphQLError(
                                (
                                    "Anonymous Subscription"
                                    if operation_name is None
                                    else f"Subscription '{operation_name}'"
                                )
                                + " must not select an introspection top level field.",
                                field_nodes,
                            )
                        )
