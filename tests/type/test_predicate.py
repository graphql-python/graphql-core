from pytest import raises

from graphql.type import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLString,
    GraphQLUnionType,
    assert_abstract_type,
    assert_composite_type,
    assert_enum_type,
    assert_input_object_type,
    assert_input_type,
    assert_interface_type,
    assert_leaf_type,
    assert_list_type,
    assert_named_type,
    assert_non_null_type,
    assert_nullable_type,
    assert_object_type,
    assert_output_type,
    assert_scalar_type,
    assert_type,
    assert_union_type,
    assert_wrapping_type,
    get_named_type,
    get_nullable_type,
    is_abstract_type,
    is_composite_type,
    is_enum_type,
    is_input_object_type,
    is_input_type,
    is_interface_type,
    is_leaf_type,
    is_list_type,
    is_named_type,
    is_required_argument,
    is_required_input_field,
    is_non_null_type,
    is_nullable_type,
    is_object_type,
    is_output_type,
    is_scalar_type,
    is_type,
    is_union_type,
    is_wrapping_type,
)

ObjectType = GraphQLObjectType("Object", {})
InterfaceType = GraphQLInterfaceType("Interface")
UnionType = GraphQLUnionType("Union", types=[ObjectType])
EnumType = GraphQLEnumType("Enum", values={"foo": {}})
InputObjectType = GraphQLInputObjectType("InputObject", {})
ScalarType = GraphQLScalarType(
    "Scalar", serialize=lambda: {}, parse_value=lambda: {}, parse_literal=lambda: {}
)


def describe_type_predicates():
    def describe_is_type():
        def returns_true_for_unwrapped_types():
            assert is_type(GraphQLString) is True
            assert_type(GraphQLString)
            assert is_type(ObjectType) is True
            assert_type(ObjectType)

        def returns_true_for_wrapped_types():
            assert is_type(GraphQLNonNull(GraphQLString)) is True
            assert_type(GraphQLNonNull(GraphQLString))

        def returns_false_for_type_classes_rather_than_instance():
            assert is_type(GraphQLObjectType) is False
            with raises(TypeError):
                assert_type(GraphQLObjectType)

        def returns_false_for_random_garbage():
            assert is_type({"what": "is this"}) is False
            with raises(TypeError):
                assert_type({"what": "is this"})

    def describe_is_scalar_type():
        def returns_true_for_spec_defined_scalar():
            assert is_scalar_type(GraphQLString) is True
            assert_scalar_type(GraphQLString)

        def returns_true_for_custom_scalar():
            assert is_scalar_type(ScalarType) is True
            assert_scalar_type(ScalarType)

        def returns_false_for_non_scalar():
            assert is_scalar_type(EnumType) is False
            with raises(TypeError):
                assert_scalar_type(EnumType)

    def describe_is_object_type():
        def returns_true_for_object_type():
            assert is_object_type(ObjectType) is True
            assert_object_type(ObjectType)

        def returns_false_for_wrapped_object_type():
            assert is_object_type(GraphQLList(ObjectType)) is False
            with raises(TypeError):
                assert_object_type(GraphQLList(ObjectType))

        def returns_false_for_non_object_type():
            assert is_scalar_type(InterfaceType) is False
            with raises(TypeError):
                assert_scalar_type(InterfaceType)

    def describe_is_interface_type():
        def returns_true_for_interface_type():
            assert is_interface_type(InterfaceType) is True
            assert_interface_type(InterfaceType)

        def returns_false_for_wrapped_interface_type():
            assert is_interface_type(GraphQLList(InterfaceType)) is False
            with raises(TypeError):
                assert_interface_type(GraphQLList(InterfaceType))

        def returns_false_for_non_interface_type():
            assert is_interface_type(ObjectType) is False
            with raises(TypeError):
                assert_interface_type(ObjectType)

    def describe_is_union_type():
        def returns_true_for_union_type():
            assert is_union_type(UnionType) is True
            assert_union_type(UnionType)

        def returns_false_for_wrapped_union_type():
            assert is_union_type(GraphQLList(UnionType)) is False
            with raises(TypeError):
                assert_union_type(GraphQLList(UnionType))

        def returns_false_for_non_union_type():
            assert is_union_type(ObjectType) is False
            with raises(TypeError):
                assert_union_type(ObjectType)

    def describe_is_enum_type():
        def returns_true_for_enum_type():
            assert is_enum_type(EnumType) is True
            assert_enum_type(EnumType)

        def returns_false_for_wrapped_enum_type():
            assert is_enum_type(GraphQLList(EnumType)) is False
            with raises(TypeError):
                assert_enum_type(GraphQLList(EnumType))

        def returns_false_for_non_enum_type():
            assert is_enum_type(ScalarType) is False
            with raises(TypeError):
                assert_enum_type(ScalarType)

    def describe_is_input_object_type():
        def returns_true_for_input_object_type():
            assert is_input_object_type(InputObjectType) is True
            assert_input_object_type(InputObjectType)

        def returns_false_for_wrapped_input_object_type():
            assert is_input_object_type(GraphQLList(InputObjectType)) is False
            with raises(TypeError):
                assert_input_object_type(GraphQLList(InputObjectType))

        def returns_false_for_non_input_object_type():
            assert is_input_object_type(ObjectType) is False
            with raises(TypeError):
                assert_input_object_type(ObjectType)

    def describe_is_list_type():
        def returns_true_for_a_list_wrapped_type():
            assert is_list_type(GraphQLList(ObjectType)) is True
            assert_list_type(GraphQLList(ObjectType))

        def returns_false_for_an_unwrapped_type():
            assert is_list_type(ObjectType) is False
            with raises(TypeError):
                assert_list_type(ObjectType)

        def returns_true_for_a_non_list_wrapped_type():
            assert is_list_type(GraphQLNonNull(GraphQLList(ObjectType))) is False
            with raises(TypeError):
                assert_list_type(GraphQLNonNull(GraphQLList(ObjectType)))

    def describe_is_non_null_type():
        def returns_true_for_a_non_null_wrapped_type():
            assert is_non_null_type(GraphQLNonNull(ObjectType)) is True
            assert_non_null_type(GraphQLNonNull(ObjectType))

        def returns_false_for_an_unwrapped_type():
            assert is_non_null_type(ObjectType) is False
            with raises(TypeError):
                assert_non_null_type(ObjectType)

        def returns_true_for_a_not_non_null_wrapped_type():
            assert is_non_null_type(GraphQLList(GraphQLNonNull(ObjectType))) is False
            with raises(TypeError):
                assert_non_null_type(GraphQLList(GraphQLNonNull(ObjectType)))

    def describe_is_input_type():
        def returns_true_for_an_input_type():
            assert is_input_type(InputObjectType) is True
            assert_input_type(InputObjectType)

        def returns_true_for_a_wrapped_input_type():
            assert is_input_type(GraphQLList(InputObjectType)) is True
            assert_input_type(GraphQLList(InputObjectType))
            assert is_input_type(GraphQLNonNull(InputObjectType)) is True
            assert_input_type(GraphQLNonNull(InputObjectType))

        def returns_false_for_an_output_type():
            assert is_input_type(ObjectType) is False
            with raises(TypeError):
                assert_input_type(ObjectType)

        def returns_false_for_a_wrapped_output_type():
            assert is_input_type(GraphQLList(ObjectType)) is False
            with raises(TypeError):
                assert_input_type(GraphQLList(ObjectType))
            assert is_input_type(GraphQLNonNull(ObjectType)) is False
            with raises(TypeError):
                assert_input_type(GraphQLNonNull(ObjectType))

    def describe_is_output_type():
        def returns_true_for_an_output_type():
            assert is_output_type(ObjectType) is True
            assert_output_type(ObjectType)

        def returns_true_for_a_wrapped_output_type():
            assert is_output_type(GraphQLList(ObjectType)) is True
            assert_output_type(GraphQLList(ObjectType))
            assert is_output_type(GraphQLNonNull(ObjectType)) is True
            assert_output_type(GraphQLNonNull(ObjectType))

        def returns_false_for_an_input_type():
            assert is_output_type(InputObjectType) is False
            with raises(TypeError):
                assert_output_type(InputObjectType)

        def returns_false_for_a_wrapped_input_type():
            assert is_output_type(GraphQLList(InputObjectType)) is False
            with raises(TypeError):
                assert_output_type(GraphQLList(InputObjectType))
            assert is_output_type(GraphQLNonNull(InputObjectType)) is False
            with raises(TypeError):
                assert_output_type(GraphQLNonNull(InputObjectType))

    def describe_is_leaf_type():
        def returns_true_for_scalar_and_enum_types():
            assert is_leaf_type(ScalarType) is True
            assert_leaf_type(ScalarType)
            assert is_leaf_type(EnumType) is True
            assert_leaf_type(EnumType)

        def returns_false_for_wrapped_leaf_type():
            assert is_leaf_type(GraphQLList(ScalarType)) is False
            with raises(TypeError):
                assert_leaf_type(GraphQLList(ScalarType))

        def returns_false_for_non_leaf_type():
            assert is_leaf_type(ObjectType) is False
            with raises(TypeError):
                assert_leaf_type(ObjectType)

        def returns_false_for_wrapped_non_leaf_type():
            assert is_leaf_type(GraphQLList(ObjectType)) is False
            with raises(TypeError):
                assert_leaf_type(GraphQLList(ObjectType))

    def describe_is_composite_type():
        def returns_true_for_object_interface_and_union_types():
            assert is_composite_type(ObjectType) is True
            assert_composite_type(ObjectType)
            assert is_composite_type(InterfaceType) is True
            assert_composite_type(InterfaceType)
            assert is_composite_type(UnionType) is True
            assert_composite_type(UnionType)

        def returns_false_for_wrapped_composite_type():
            assert is_composite_type(GraphQLList(ObjectType)) is False
            with raises(TypeError):
                assert_composite_type(GraphQLList(ObjectType))

        def returns_false_for_non_composite_type():
            assert is_composite_type(InputObjectType) is False
            with raises(TypeError):
                assert_composite_type(InputObjectType)

        def returns_false_for_wrapped_non_composite_type():
            assert is_composite_type(GraphQLList(InputObjectType)) is False
            with raises(TypeError):
                assert_composite_type(GraphQLList(InputObjectType))

    def describe_is_abstract_type():
        def returns_true_for_interface_and_union_types():
            assert is_abstract_type(InterfaceType) is True
            assert_abstract_type(InterfaceType)
            assert is_abstract_type(UnionType) is True
            assert_abstract_type(UnionType)

        def returns_false_for_wrapped_abstract_type():
            assert is_abstract_type(GraphQLList(InterfaceType)) is False
            with raises(TypeError):
                assert_abstract_type(GraphQLList(InterfaceType))

        def returns_false_for_non_abstract_type():
            assert is_abstract_type(ObjectType) is False
            with raises(TypeError):
                assert_abstract_type(ObjectType)

        def returns_false_for_wrapped_non_abstract_type():
            assert is_abstract_type(GraphQLList(ObjectType)) is False
            with raises(TypeError):
                assert_abstract_type(GraphQLList(ObjectType))

    def describe_is_wrapping_type():
        def returns_true_for_list_and_non_null_types():
            assert is_wrapping_type(GraphQLList(ObjectType)) is True
            assert_wrapping_type(GraphQLList(ObjectType))
            assert is_wrapping_type(GraphQLNonNull(ObjectType)) is True
            assert_wrapping_type(GraphQLNonNull(ObjectType))

        def returns_false_for_unwrapped_types():
            assert is_wrapping_type(ObjectType) is False
            with raises(TypeError):
                assert_wrapping_type(ObjectType)

    def describe_is_nullable_type():
        def returns_true_for_unwrapped_types():
            assert is_nullable_type(ObjectType) is True
            assert_nullable_type(ObjectType)

        def returns_true_for_list_of_non_null_types():
            assert is_nullable_type(GraphQLList(GraphQLNonNull(ObjectType))) is True
            assert_nullable_type(GraphQLList(GraphQLNonNull(ObjectType)))

        def returns_false_for_non_null_types():
            assert is_nullable_type(GraphQLNonNull(ObjectType)) is False
            with raises(TypeError):
                assert_nullable_type(GraphQLNonNull(ObjectType))

    def describe_get_nullable_type():
        def returns_none_for_no_type():
            assert get_nullable_type(None) is None

        def returns_self_for_a_nullable_type():
            assert get_nullable_type(ObjectType) is ObjectType
            list_of_obj = GraphQLList(ObjectType)
            assert get_nullable_type(list_of_obj) is list_of_obj

        def unwraps_non_null_type():
            assert get_nullable_type(GraphQLNonNull(ObjectType)) is ObjectType

    def describe_is_named_type():
        def returns_true_for_unwrapped_types():
            assert is_named_type(ObjectType) is True
            assert_named_type(ObjectType)

        def returns_false_for_list_and_non_null_types():
            assert is_named_type(GraphQLList(ObjectType)) is False
            with raises(TypeError):
                assert_named_type(GraphQLList(ObjectType))
            assert is_named_type(GraphQLNonNull(ObjectType)) is False
            with raises(TypeError):
                assert_named_type(GraphQLNonNull(ObjectType))

    def describe_get_named_type():
        def returns_none_for_no_type():
            assert get_named_type(None) is None

        def returns_self_for_an_unwrapped_type():
            assert get_named_type(ObjectType) is ObjectType

        def unwraps_wrapper_types():
            assert get_named_type(GraphQLNonNull(ObjectType)) is ObjectType
            assert get_named_type(GraphQLList(ObjectType)) is ObjectType

        def unwraps_deeply_wrapper_types():
            assert (
                get_named_type(GraphQLNonNull(GraphQLList(GraphQLNonNull(ObjectType))))
                is ObjectType
            )

    def describe_is_required_argument():
        def returns_true_for_required_arguments():
            required_arg = GraphQLArgument(GraphQLNonNull(GraphQLString))
            assert is_required_argument(required_arg) is True

        def returns_false_for_optional_arguments():
            opt_arg1 = GraphQLArgument(GraphQLString)
            assert is_required_argument(opt_arg1) is False

            opt_arg2 = GraphQLArgument(GraphQLString, default_value=None)
            assert is_required_argument(opt_arg2) is False

            opt_arg3 = GraphQLArgument(GraphQLList(GraphQLNonNull(GraphQLString)))
            assert is_required_argument(opt_arg3) is False

            opt_arg4 = GraphQLArgument(
                GraphQLNonNull(GraphQLString), default_value="default"
            )
            assert is_required_argument(opt_arg4) is False

    def describe_is_required_input_field():
        def returns_true_for_required_input_field():
            required_field = GraphQLInputField(GraphQLNonNull(GraphQLString))
            assert is_required_input_field(required_field) is True

        def returns_false_for_optional_input_field():
            opt_field1 = GraphQLInputField(GraphQLString)
            assert is_required_input_field(opt_field1) is False

            opt_field2 = GraphQLInputField(GraphQLString, default_value=None)
            assert is_required_input_field(opt_field2) is False

            opt_field3 = GraphQLInputField(GraphQLList(GraphQLNonNull(GraphQLString)))
            assert is_required_input_field(opt_field3) is False

            opt_field4 = GraphQLInputField(
                GraphQLNonNull(GraphQLString), default_value="default"
            )
            assert is_required_input_field(opt_field4) is False
