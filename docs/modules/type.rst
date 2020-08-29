Type
====

.. currentmodule:: graphql.type

.. automodule:: graphql.type
   :no-members:
   :no-inherited-members:

Definition
----------

Predicates
^^^^^^^^^^

.. autofunction:: is_composite_type
.. autofunction:: is_enum_type
.. autofunction:: is_input_object_type
.. autofunction:: is_input_type
.. autofunction:: is_interface_type
.. autofunction:: is_leaf_type
.. autofunction:: is_list_type
.. autofunction:: is_named_type
.. autofunction:: is_non_null_type
.. autofunction:: is_nullable_type
.. autofunction:: is_object_type
.. autofunction:: is_output_type
.. autofunction:: is_scalar_type
.. autofunction:: is_type
.. autofunction:: is_union_type
.. autofunction:: is_wrapping_type

Assertions
^^^^^^^^^^

.. autofunction:: assert_abstract_type
.. autofunction:: assert_composite_type
.. autofunction:: assert_enum_type
.. autofunction:: assert_input_object_type
.. autofunction:: assert_input_type
.. autofunction:: assert_interface_type
.. autofunction:: assert_leaf_type
.. autofunction:: assert_list_type
.. autofunction:: assert_named_type
.. autofunction:: assert_non_null_type
.. autofunction:: assert_nullable_type
.. autofunction:: assert_object_type
.. autofunction:: assert_output_type
.. autofunction:: assert_scalar_type
.. autofunction:: assert_type
.. autofunction:: assert_union_type
.. autofunction:: assert_wrapping_type

Un-modifiers
^^^^^^^^^^^^

.. autofunction:: get_nullable_type
.. autofunction:: get_named_type

Definitions
^^^^^^^^^^^
.. autoclass:: GraphQLEnumType
.. autoclass:: GraphQLInputObjectType
.. autoclass:: GraphQLInterfaceType
.. autoclass:: GraphQLObjectType
.. autoclass:: GraphQLScalarType
.. autoclass:: GraphQLUnionType

Type Wrappers
^^^^^^^^^^^^^

.. autoclass:: GraphQLList
.. autoclass:: GraphQLNonNull

Types
^^^^^
.. autoclass:: GraphQLAbstractType
.. autoclass:: GraphQLArgument
.. autoclass:: GraphQLArgumentMap
.. autoclass:: GraphQLCompositeType
.. autoclass:: GraphQLEnumValue
.. autoclass:: GraphQLEnumValueMap
.. autoclass:: GraphQLField
.. autoclass:: GraphQLFieldMap
.. autoclass:: GraphQLInputField
.. autoclass:: GraphQLInputFieldMap
.. autoclass:: GraphQLInputType
.. autoclass:: GraphQLLeafType
.. autoclass:: GraphQLNamedType
.. autoclass:: GraphQLNullableType
.. autoclass:: GraphQLOutputType
.. autoclass:: GraphQLType
.. autoclass:: GraphQLWrappingType

.. autoclass:: Thunk

Resolvers
^^^^^^^^^

.. autoclass:: GraphQLFieldResolver
.. autoclass:: GraphQLIsTypeOfFn
.. autoclass:: GraphQLResolveInfo
.. autoclass:: GraphQLTypeResolver


Directives
----------

Predicates
^^^^^^^^^^

.. autofunction:: is_directive
.. autofunction:: is_specified_directive

Definitions
^^^^^^^^^^^

.. autoclass:: GraphQLDirective
.. autoclass:: GraphQLIncludeDirective
.. autoclass:: GraphQLSkipDirective
.. autoclass:: GraphQLDeprecatedDirective

.. autodata:: specified_directives

.. data:: DEFAULT_DEPRECATION_REASON
   :annotation: = 'No longer supported'

   String constant that can be used as the default value for ``deprecation_reason``.


Introspection
-------------

Predicates
^^^^^^^^^^

.. autofunction:: is_introspection_type

Definitions
^^^^^^^^^^^

.. autoclass:: TypeKind
.. autoclass:: TypeMetaFieldDef
.. autoclass:: TypeNameMetaFieldDef
.. autoclass:: SchemaMetaFieldDef

.. autodata:: introspection_types


Scalars
-------

Predicates
^^^^^^^^^^

.. autofunction:: is_specified_scalar_type

Definitions
^^^^^^^^^^^

.. autoclass:: GraphQLBoolean
.. autoclass:: GraphQLFloat
.. autoclass:: GraphQLID
.. autoclass:: GraphQLInt
.. autoclass:: GraphQLString

The list of all specified directives is available as
:data:`specified_directives`.


Schema
------

Predicates
^^^^^^^^^^

.. autofunction:: is_schema

Definitions
^^^^^^^^^^^

.. autoclass:: GraphQLSchema


Validate
--------

Functions:
^^^^^^^^^^

.. autofunction:: validate_schema

Assertions
^^^^^^^^^^

.. autofunction:: assert_valid_schema
