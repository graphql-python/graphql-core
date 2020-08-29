Utilities
=========

.. currentmodule:: graphql.utilities

.. automodule:: graphql.utilities
   :no-members:
   :no-inherited-members:

The GraphQL query recommended for a full schema introspection:

.. autofunction:: get_introspection_query

Get the target Operation from a Document:

.. autofunction:: get_operation_ast

Get the Type for the target Operation AST:

.. autofunction:: get_operation_root_type

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

.. autofunction:: print_introspection_schema
.. autofunction:: print_schema
.. autofunction:: print_type
.. autofunction:: print_value

Create a GraphQLType from a GraphQL language AST:

.. autofunction:: type_from_ast

Create a Python value from a GraphQL language AST with a type:

.. autofunction:: value_from_ast

Create a Python value from a GraphQL language AST without a type:

.. autofunction:: value_from_ast_untyped

Create a GraphQL language AST from a Python value:

.. autofunction:: ast_from_value

A helper to use within recursive-descent visitors which need to be aware of the GraphQL
type system:

.. autoclass:: TypeInfo
.. autoclass:: TypeInfoVisitor

Coerce a Python value to a GraphQL type, or produce errors:

.. autofunction:: coerce_input_value

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

Assert that a string is a valid GraphQL name:

.. autofunction:: assert_valid_name
.. autofunction:: is_valid_name_error

Compare two GraphQLSchemas and detect breaking changes:

.. autofunction:: find_breaking_changes
.. autofunction:: find_dangerous_changes

.. autoclass:: BreakingChange
.. autoclass:: BreakingChangeType
.. autoclass:: DangerousChange
.. autoclass:: DangerousChangeType

Report all deprecated usages within a GraphQL document:

.. autofunction:: find_deprecated_usages
