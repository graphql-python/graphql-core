Validation
==========

.. currentmodule:: graphql.validation

.. automodule:: graphql.validation
   :no-members:
   :no-inherited-members:

.. autofunction:: validate

.. autoclass:: ASTValidationContext

.. autoclass:: ASTValidationRule

.. autoclass:: SDLValidationContext

.. autoclass:: SDLValidationRule

.. autoclass:: ValidationContext

.. autoclass:: ValidationRule



Rules
-----

.. module:: graphql.validation.rules
.. currentmodule:: graphql.validation

.. autodata:: specified_rules
   :annotation: = FrozenList([...])

**Spec Section: "Executable Definitions"**

.. autoclass:: ExecutableDefinitionsRule

**Spec Section: "Field Selections on Objects, Interfaces, and Unions Types"**

.. autoclass:: FieldsOnCorrectTypeRule

**Spec Section: "Fragments on Composite Types"**

.. autoclass:: FragmentsOnCompositeTypesRule

**Spec Section: "Argument Names"**

.. autoclass:: KnownArgumentNamesRule

**Spec Section: "Directives Are Defined"**

.. autoclass:: KnownDirectivesRule

**Spec Section: "Fragment spread target defined"**

.. autoclass:: KnownFragmentNamesRule

**Spec Section: "Fragment Spread Type Existence"**

.. autoclass:: KnownTypeNamesRule

**Spec Section: "Lone Anonymous Operation"**

.. autoclass:: LoneAnonymousOperationRule

**Spec Section: "Fragments must not form cycles"**

.. autoclass:: NoFragmentCyclesRule

**Spec Section: "All Variable Used Defined"**

.. autoclass:: NoUndefinedVariablesRule

**Spec Section: "Fragments must be used"**

.. autoclass:: NoUnusedFragmentsRule

**Spec Section: "All Variables Used"**

.. autoclass:: NoUnusedVariablesRule

**Spec Section: "Field Selection Merging"**

.. autoclass:: OverlappingFieldsCanBeMergedRule

**Spec Section: "Fragment spread is possible"**

.. autoclass:: PossibleFragmentSpreadsRule

**Spec Section: "Argument Optionality"**

.. autoclass:: ProvidedRequiredArgumentsRule

**Spec Section: "Leaf Field Selections"**

.. autoclass:: ScalarLeafsRule

**Spec Section: "Subscriptions with Single Root Field"**

.. autoclass:: SingleFieldSubscriptionsRule

**Spec Section: "Argument Uniqueness"**

.. autoclass:: UniqueArgumentNamesRule

**Spec Section: "Directives Are Unique Per Location"**

.. autoclass:: UniqueDirectivesPerLocationRule

**Spec Section: "Fragment Name Uniqueness"**

.. autoclass:: UniqueFragmentNamesRule

**Spec Section: "Input Object Field Uniqueness"**

.. autoclass:: UniqueInputFieldNamesRule

**Spec Section: "Operation Name Uniqueness"**

.. autoclass:: UniqueOperationNamesRule

**Spec Section: "Variable Uniqueness"**

.. autoclass:: UniqueVariableNamesRule

**Spec Section: "Value Type Correctness"**

.. autoclass:: ValuesOfCorrectTypeRule

**Spec Section: "Variables are Input Types"**

.. autoclass:: VariablesAreInputTypesRule

**Spec Section: "All Variable Usages Are Allowed"**

.. autoclass:: VariablesInAllowedPositionRule

**SDL-specific validation rules**

.. autoclass:: LoneSchemaDefinitionRule
.. autoclass:: UniqueOperationTypesRule
.. autoclass:: UniqueTypeNamesRule
.. autoclass:: UniqueEnumValueNamesRule
.. autoclass:: UniqueFieldDefinitionNamesRule
.. autoclass:: UniqueDirectiveNamesRule
.. autoclass:: PossibleTypeExtensionsRule
