from graphql.language import (
    DefinitionNode,
    DocumentNode,
    ExecutableDefinitionNode,
    FieldDefinitionNode,
    FieldNode,
    InlineFragmentNode,
    IntValueNode,
    Node,
    NonNullTypeNode,
    ObjectValueNode,
    ScalarTypeDefinitionNode,
    ScalarTypeExtensionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    SelectionNode,
    SelectionSetNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    TypeNode,
    TypeSystemDefinitionNode,
    ValueNode,
    is_definition_node,
    is_executable_definition_node,
    is_selection_node,
    is_value_node,
    is_type_node,
    is_type_system_definition_node,
    is_type_definition_node,
    is_type_system_extension_node,
    is_type_extension_node,
)


def describe_predicates():
    def check_definition_node():
        assert not is_definition_node(Node())
        assert not is_definition_node(DocumentNode())
        assert is_definition_node(DefinitionNode())
        assert is_definition_node(ExecutableDefinitionNode())
        assert is_definition_node(TypeSystemDefinitionNode())

    def check_exectuable_definition_node():
        assert not is_executable_definition_node(Node())
        assert not is_executable_definition_node(DocumentNode())
        assert not is_executable_definition_node(DefinitionNode())
        assert is_executable_definition_node(ExecutableDefinitionNode())
        assert not is_executable_definition_node(TypeSystemDefinitionNode())

    def check_selection_node():
        assert not is_selection_node(Node())
        assert not is_selection_node(DocumentNode())
        assert is_selection_node(SelectionNode())
        assert is_selection_node(FieldNode())
        assert is_selection_node(InlineFragmentNode())
        assert not is_selection_node(SelectionSetNode())

    def check_value_node():
        assert not is_value_node(Node())
        assert not is_value_node(DocumentNode())
        assert is_value_node(ValueNode())
        assert is_value_node(IntValueNode())
        assert is_value_node(ObjectValueNode())
        assert not is_value_node(TypeNode())

    def check_type_node():
        assert not is_type_node(Node())
        assert not is_type_node(DocumentNode())
        assert not is_type_node(ValueNode())
        assert is_type_node(TypeNode())
        assert is_type_node(NonNullTypeNode())

    def check_type_system_definition_node():
        assert not is_type_system_definition_node(Node())
        assert not is_type_system_definition_node(DocumentNode())
        assert is_type_system_definition_node(TypeSystemDefinitionNode())
        assert not is_type_system_definition_node(TypeNode())
        assert not is_type_system_definition_node(DefinitionNode())
        assert is_type_system_definition_node(TypeDefinitionNode())
        assert is_type_system_definition_node(SchemaDefinitionNode())
        assert is_type_system_definition_node(ScalarTypeDefinitionNode())
        assert is_type_system_definition_node(FieldDefinitionNode())

    def check_type_definition_node():
        assert not is_type_definition_node(Node())
        assert not is_type_definition_node(DocumentNode())
        assert is_type_definition_node(TypeDefinitionNode())
        assert is_type_definition_node(ScalarTypeDefinitionNode())
        assert not is_type_definition_node(TypeSystemDefinitionNode())
        assert not is_type_definition_node(DefinitionNode())
        assert not is_type_definition_node(TypeNode())

    def check_type_system_extension_node():
        assert not is_type_system_extension_node(Node())
        assert not is_type_system_extension_node(DocumentNode())
        assert is_type_system_extension_node(SchemaExtensionNode())
        assert is_type_system_extension_node(TypeExtensionNode())
        assert not is_type_system_extension_node(TypeSystemDefinitionNode())
        assert not is_type_system_extension_node(DefinitionNode())
        assert not is_type_system_extension_node(TypeNode())

    def check_type_extension_node():
        assert not is_type_extension_node(Node())
        assert not is_type_extension_node(DocumentNode())
        assert is_type_extension_node(TypeExtensionNode())
        assert not is_type_extension_node(ScalarTypeDefinitionNode())
        assert is_type_extension_node(ScalarTypeExtensionNode())
        assert not is_type_extension_node(DefinitionNode())
        assert not is_type_extension_node(TypeNode())
