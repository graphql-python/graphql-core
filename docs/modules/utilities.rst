Utilities
=========

.. currentmodule:: graphql.utilities

.. automodule:: graphql.utilities
   :no-members:
   :no-inherited-members:

The GraphQL query recommended for a full schema introspection:

.. autofunction:: get_introspection_query

.. autoclass:: IntrospectionQuery
   :no-inherited-members:

Get the target Operation from a Document:

.. autofunction:: get_operation_ast

Convert a GraphQLSchema to an IntrospectionQuery:

.. autofunction:: introspection_from_schema

Build a GraphQLSchema from an introspection result:

.. autofunction:: build_client_schema

Build a GraphQLSchema from GraphQL Schema language:

.. autofunction:: build_ast_schema
.. autofunction:: build_schema

Extend an existing GraphQLSchema from a parsed GraphQL Schema language AST:

.. autofunction:: extend_schema

Sort a GraphQLSchema:

.. autofunction:: lexicographic_sort_schema

Print a GraphQLSchema to GraphQL Schema language:

.. autofunction:: print_schema
.. autofunction:: print_type
.. autofunction:: print_directive
.. autofunction:: print_introspection_schema

Create a GraphQLType from a GraphQL language AST:

.. autofunction:: type_from_ast

Convert a language AST to a dictionary:

.. autofunction:: ast_to_dict

Create a Python value from a GraphQL language AST with a type:

.. autofunction:: value_from_ast

Create a Python value from a GraphQL language AST without a type:

.. autofunction:: value_from_ast_untyped

Create a GraphQL language AST from a Python value:

.. autofunction:: ast_from_value

Create a GraphQL literal (AST) from a Python value:

.. autofunction:: value_to_literal

Replace any variables in an AST value with their literal values:

.. autofunction:: replace_variables

A helper to use within recursive-descent visitors which need to be aware of the GraphQL
type system:

.. autoclass:: TypeInfo
.. autoclass:: TypeInfoVisitor

Coerce a Python value to a GraphQL type, or return ``Undefined``:

.. autofunction:: coerce_input_value

Coerce a GraphQL literal (AST) to a GraphQL type, or return ``Undefined``:

.. autofunction:: coerce_input_literal

Validate a Python value with a GraphQL type, collecting all errors:

.. autofunction:: validate_input_value

Validate a GraphQL literal (AST) with a GraphQL type, collecting all errors:

.. autofunction:: validate_input_literal

Concatenate multiple ASTs together:

.. autofunction:: concat_ast

Separate an AST into an AST per Operation:

.. autofunction:: separate_operations

Strip characters that are not significant to the validity or execution
of a GraphQL document:

.. autofunction:: strip_ignored_characters

Comparators for types:

.. autofunction:: is_equal_type
.. autofunction:: is_type_sub_type_of
.. autofunction:: do_types_overlap

Compare two GraphQLSchemas and detect changes:

.. autofunction:: find_schema_changes
.. autofunction:: find_breaking_changes
.. autofunction:: find_dangerous_changes

.. autoclass:: SafeChange
.. autoclass:: SafeChangeType
.. autoclass:: BreakingChange
.. autoclass:: BreakingChangeType
.. autoclass:: DangerousChange
.. autoclass:: DangerousChangeType
.. autoclass:: SchemaChange

Resolve a schema coordinate to the schema element it refers to:

.. autofunction:: resolve_schema_coordinate
.. autofunction:: resolve_ast_schema_coordinate

.. autoclass:: ResolvedNamedType
.. autoclass:: ResolvedField
.. autoclass:: ResolvedInputField
.. autoclass:: ResolvedEnumValue
.. autoclass:: ResolvedFieldArgument
.. autoclass:: ResolvedDirective
.. autoclass:: ResolvedDirectiveArgument
.. autoclass:: ResolvedSchemaElement
