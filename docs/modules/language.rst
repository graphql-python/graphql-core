Language
========

.. currentmodule:: graphql.language

.. automodule:: graphql.language
   :no-members:
   :no-inherited-members:

AST
---

.. autoclass:: Location
.. autoclass:: Node

Each kind of AST node has its own class:

.. autoclass:: ArgumentNode
.. autoclass:: BooleanValueNode
.. autoclass:: ConstArgumentNode
.. autoclass:: ConstDirectiveNode
.. autoclass:: ConstListValueNode
.. autoclass:: ConstObjectFieldNode
.. autoclass:: ConstObjectValueNode
.. autoclass:: ConstValueNode
.. autoclass:: DefinitionNode
.. autoclass:: DirectiveDefinitionNode
.. autoclass:: DirectiveNode
.. autoclass:: DocumentNode
.. autoclass:: EnumTypeDefinitionNode
.. autoclass:: EnumTypeExtensionNode
.. autoclass:: EnumValueDefinitionNode
.. autoclass:: EnumValueNode
.. autoclass:: ExecutableDefinitionNode
.. autoclass:: FieldDefinitionNode
.. autoclass:: FieldNode
.. autoclass:: FloatValueNode
.. autoclass:: FragmentDefinitionNode
.. autoclass:: FragmentSpreadNode
.. autoclass:: InlineFragmentNode
.. autoclass:: InputObjectTypeDefinitionNode
.. autoclass:: InputObjectTypeExtensionNode
.. autoclass:: InputValueDefinitionNode
.. autoclass:: IntValueNode
.. autoclass:: InterfaceTypeDefinitionNode
.. autoclass:: InterfaceTypeExtensionNode
.. autoclass:: ListTypeNode
.. autoclass:: ListValueNode
.. autoclass:: NameNode
.. autoclass:: NamedTypeNode
.. autoclass:: NonNullTypeNode
.. autoclass:: NullValueNode
.. autoclass:: ObjectFieldNode
.. autoclass:: ObjectTypeDefinitionNode
.. autoclass:: ObjectTypeExtensionNode
.. autoclass:: ObjectValueNode
.. autoclass:: OperationDefinitionNode
.. autoclass:: OperationType
.. autoclass:: OperationTypeDefinitionNode
.. autoclass:: ScalarTypeDefinitionNode
.. autoclass:: ScalarTypeExtensionNode
.. autoclass:: SchemaDefinitionNode
.. autoclass:: SchemaExtensionNode
.. autoclass:: SelectionNode
.. autoclass:: SelectionSetNode
.. autoclass:: StringValueNode
.. autoclass:: TypeDefinitionNode
.. autoclass:: TypeExtensionNode
.. autoclass:: TypeNode
.. autoclass:: TypeSystemDefinitionNode
.. autoclass:: TypeSystemExtensionNode
.. autoclass:: UnionTypeDefinitionNode
.. autoclass:: UnionTypeExtensionNode
.. autoclass:: ValueNode
.. autoclass:: VariableDefinitionNode
.. autoclass:: VariableNode

Directive locations are specified using the following enumeration:

.. autoclass:: DirectiveLocation

You can also check the type of nodes with the following predicates:

.. autofunction:: is_definition_node
.. autofunction:: is_executable_definition_node
.. autofunction:: is_selection_node
.. autofunction:: is_value_node
.. autofunction:: is_const_value_node
.. autofunction:: is_type_node
.. autofunction:: is_type_system_definition_node
.. autofunction:: is_type_definition_node
.. autofunction:: is_type_system_extension_node
.. autofunction:: is_type_extension_node

Lexer
-----

.. autoclass:: Lexer
.. autoclass:: TokenKind
.. autoclass:: Token

Location
--------

.. autofunction:: get_location
.. autoclass:: SourceLocation
.. autofunction:: print_location
.. autoclass:: FormattedSourceLocation
   :no-inherited-members:


Parser
------

.. autofunction:: parse
.. autofunction:: parse_type
.. autofunction:: parse_value
.. autofunction:: parse_const_value

Printer
-------

.. autofunction:: print_ast

Source
------

.. autoclass:: Source
.. autofunction:: print_source_location

Visitor
-------

.. autofunction:: visit
.. autoclass:: Visitor
.. autoclass:: ParallelVisitor

The module also exports the following enumeration that can be used as the return type
for :class:`Visitor` methods:

.. currentmodule:: graphql.language.visitor

.. autoclass:: VisitorActionEnum

.. currentmodule:: graphql.language

The module also exports the values of this enumeration directly. These can be used as
return values of :class:`Visitor` methods to signal particular actions:

.. data:: BREAK
   :annotation: (same as ``True``)

   This return value signals that no further nodes shall be visited.

.. data:: SKIP
   :annotation: (same as ``False``)

   This return value signals that the current node shall be skipped.

.. data:: REMOVE
   :annotation: (same as``Ellipsis``)

   This return value signals that the current node shall be deleted.

.. data:: IDLE
   :annotation: = None

   This return value signals that no additional action shall take place.
