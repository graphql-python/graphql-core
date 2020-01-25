Language
========

.. automodule:: graphql.language

AST
---

.. autoclass:: Location
.. autoclass:: Node

Each kind of AST node has its own class:

.. autoclass:: ArgumentNode
.. autoclass:: BooleanValueNode
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

Parser
------

.. autofunction:: parse
.. autofunction:: parse_type
.. autofunction:: parse_value

Source
------

.. autoclass:: Source
.. autofunction:: print_source_location

Visitor
-------

.. autofunction:: visit
.. autoclass:: Visitor
.. autoclass:: ParallelVisitor

The module also exports the following special symbols which can be used as
return values in the :class:`Visitor` methods to signal particular actions:

.. data:: BREAK
   :annotation: = True

   This return value signals that no further nodes shall be visited.

.. data:: SKIP
   :annotation: = False

   This return value signals that the current node shall be skipped.

.. data:: REMOVE
   :annotation: = Ellipsis

   This return value signals that the current node shall be deleted.

.. data:: IDLE
   :annotation: = None

   This return value signals that no additional action shall take place.
