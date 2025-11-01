"""Specified rules"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Spec Section: "Defer And Stream Directive Labels Are Unique"
from .rules.defer_stream_directive_label import DeferStreamDirectiveLabel

# Spec Section: "Defer And Stream Directives Are Used On Valid Root Field"
from .rules.defer_stream_directive_on_root_field import DeferStreamDirectiveOnRootField

# Spec Section: "Defer And Stream Directives Are Used On Valid Operations"
from .rules.defer_stream_directive_on_valid_operations_rule import (
    DeferStreamDirectiveOnValidOperationsRule,
)

# Spec Section: "Executable Definitions"
from .rules.executable_definitions import ExecutableDefinitionsRule

# Spec Section: "Field Selections on Objects, Interfaces, and Unions Types"
from .rules.fields_on_correct_type import FieldsOnCorrectTypeRule

# Spec Section: "Fragments on Composite Types"
from .rules.fragments_on_composite_types import FragmentsOnCompositeTypesRule

# Spec Section: "Argument Names"
from .rules.known_argument_names import (
    KnownArgumentNamesOnDirectivesRule,
    KnownArgumentNamesRule,
)

# Spec Section: "Directives Are Defined"
from .rules.known_directives import KnownDirectivesRule

# Spec Section: "Fragment spread target defined"
from .rules.known_fragment_names import KnownFragmentNamesRule

# Spec Section: "Fragment Spread Type Existence"
from .rules.known_type_names import KnownTypeNamesRule

# Spec Section: "Lone Anonymous Operation"
from .rules.lone_anonymous_operation import LoneAnonymousOperationRule

# Schema definition language:
from .rules.lone_schema_definition import LoneSchemaDefinitionRule

# No spec section: "Maximum introspection depth"
from .rules.max_introspection_depth_rule import MaxIntrospectionDepthRule

# Spec Section: "Fragments must not form cycles"
from .rules.no_fragment_cycles import NoFragmentCyclesRule

# Spec Section: "All Variable Used Defined"
from .rules.no_undefined_variables import NoUndefinedVariablesRule

# Spec Section: "Fragments must be used"
from .rules.no_unused_fragments import NoUnusedFragmentsRule

# Spec Section: "All Variables Used"
from .rules.no_unused_variables import NoUnusedVariablesRule

# Spec Section: "Field Selection Merging"
from .rules.overlapping_fields_can_be_merged import OverlappingFieldsCanBeMergedRule

# Spec Section: "Fragment spread is possible"
from .rules.possible_fragment_spreads import PossibleFragmentSpreadsRule
from .rules.possible_type_extensions import PossibleTypeExtensionsRule

# Spec Section: "Argument Optionality"
from .rules.provided_required_arguments import (
    ProvidedRequiredArgumentsOnDirectivesRule,
    ProvidedRequiredArgumentsRule,
)

# Spec Section: "Leaf Field Selections"
from .rules.scalar_leafs import ScalarLeafsRule

# Spec Section: "Subscriptions with Single Root Field"
from .rules.single_field_subscriptions import SingleFieldSubscriptionsRule

# Spec Section: "Stream Directives Are Used On List Fields"
from .rules.stream_directive_on_list_field import StreamDirectiveOnListField

# Spec Section: "Argument Uniqueness"
from .rules.unique_argument_definition_names import UniqueArgumentDefinitionNamesRule
from .rules.unique_argument_names import UniqueArgumentNamesRule
from .rules.unique_directive_names import UniqueDirectiveNamesRule

# Spec Section: "Directives Are Unique Per Location"
from .rules.unique_directives_per_location import UniqueDirectivesPerLocationRule
from .rules.unique_enum_value_names import UniqueEnumValueNamesRule
from .rules.unique_field_definition_names import UniqueFieldDefinitionNamesRule

# Spec Section: "Fragment Name Uniqueness"
from .rules.unique_fragment_names import UniqueFragmentNamesRule

# Spec Section: "Input Object Field Uniqueness"
from .rules.unique_input_field_names import UniqueInputFieldNamesRule

# Spec Section: "Operation Name Uniqueness"
from .rules.unique_operation_names import UniqueOperationNamesRule
from .rules.unique_operation_types import UniqueOperationTypesRule
from .rules.unique_type_names import UniqueTypeNamesRule

# Spec Section: "Variable Uniqueness"
from .rules.unique_variable_names import UniqueVariableNamesRule

# Spec Section: "Value Type Correctness"
from .rules.values_of_correct_type import ValuesOfCorrectTypeRule

# Spec Section: "Variables are Input Types"
from .rules.variables_are_input_types import VariablesAreInputTypesRule

# Spec Section: "All Variable Usages Are Allowed"
from .rules.variables_in_allowed_position import VariablesInAllowedPositionRule

if TYPE_CHECKING:
    from .rules import ASTValidationRule

__all__ = ["recommended_rules", "specified_rules", "specified_sdl_rules"]


# Technically these aren't part of the spec but they are strongly encouraged
# validation rules.

recommended_rules: tuple[type[ASTValidationRule], ...] = (MaxIntrospectionDepthRule,)
"""A tuple with all recommended validation rules."""

# This list includes all validation rules defined by the GraphQL spec.
#
# The order of the rules in this list has been adjusted to lead to the
# most clear output when encountering multiple validation errors.

specified_rules: tuple[type[ASTValidationRule], ...] = (
    ExecutableDefinitionsRule,
    UniqueOperationNamesRule,
    LoneAnonymousOperationRule,
    SingleFieldSubscriptionsRule,
    KnownTypeNamesRule,
    FragmentsOnCompositeTypesRule,
    VariablesAreInputTypesRule,
    ScalarLeafsRule,
    FieldsOnCorrectTypeRule,
    UniqueFragmentNamesRule,
    KnownFragmentNamesRule,
    NoUnusedFragmentsRule,
    PossibleFragmentSpreadsRule,
    NoFragmentCyclesRule,
    UniqueVariableNamesRule,
    NoUndefinedVariablesRule,
    NoUnusedVariablesRule,
    KnownDirectivesRule,
    UniqueDirectivesPerLocationRule,
    DeferStreamDirectiveOnRootField,
    DeferStreamDirectiveOnValidOperationsRule,
    DeferStreamDirectiveLabel,
    StreamDirectiveOnListField,
    KnownArgumentNamesRule,
    UniqueArgumentNamesRule,
    ValuesOfCorrectTypeRule,
    ProvidedRequiredArgumentsRule,
    VariablesInAllowedPositionRule,
    OverlappingFieldsCanBeMergedRule,
    UniqueInputFieldNamesRule,
    *recommended_rules,
)
"""A tuple with all validation rules defined by the GraphQL specification.

The order of the rules in this tuple has been adjusted to lead to the
most clear output when encountering multiple validation errors.
"""

specified_sdl_rules: tuple[type[ASTValidationRule], ...] = (
    LoneSchemaDefinitionRule,
    UniqueOperationTypesRule,
    UniqueTypeNamesRule,
    UniqueEnumValueNamesRule,
    UniqueFieldDefinitionNamesRule,
    UniqueArgumentDefinitionNamesRule,
    UniqueDirectiveNamesRule,
    KnownTypeNamesRule,
    KnownDirectivesRule,
    UniqueDirectivesPerLocationRule,
    PossibleTypeExtensionsRule,
    KnownArgumentNamesOnDirectivesRule,
    UniqueArgumentNamesRule,
    UniqueInputFieldNamesRule,
    ProvidedRequiredArgumentsOnDirectivesRule,
)
"""This tuple includes all rules for validating SDL.

For internal use only.
"""
