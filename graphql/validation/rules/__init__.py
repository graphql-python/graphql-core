"""graphql.validation.rules package"""

from typing import Type

from ...error import GraphQLError
from ...language.visitor import Visitor
from ..validation_context import ASTValidationContext, ValidationContext

__all__ = ['ASTValidationRule', 'ValidationRule', 'RuleType']


class ASTValidationRule(Visitor):

    context: ASTValidationContext

    def __init__(self, context: ASTValidationContext) -> None:
        self.context = context

    def report_error(self, error: GraphQLError):
        self.context.report_error(error)


class ValidationRule(ASTValidationRule):

    context: ValidationContext

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)


RuleType = Type[ASTValidationRule]
