from typing import cast, Dict

from pytest import mark, raises

from graphql.error import INVALID
from graphql.type import (
    GraphQLArgument,
    GraphQLEnumValue,
    GraphQLEnumType,
    GraphQLField,
    GraphQLFieldResolver,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
)

ScalarType = GraphQLScalarType("Scalar", serialize=lambda: None)
ObjectType = GraphQLObjectType("Object", {})
InterfaceType = GraphQLInterfaceType("Interface")
UnionType = GraphQLUnionType("Union", [ObjectType], resolve_type=lambda: None)
EnumType = GraphQLEnumType("Enum", {"foo": GraphQLEnumValue()})
InputObjectType = GraphQLInputObjectType("InputObject", {})

ListOfScalarsType = GraphQLList(ScalarType)
NonNullScalarType = GraphQLNonNull(ScalarType)
ListOfNonNullScalarsType = GraphQLList(NonNullScalarType)
NonNullListOfScalarsType = GraphQLNonNull(ListOfScalarsType)


def schema_with_field_type(type_: GraphQLOutputType) -> GraphQLSchema:
    return GraphQLSchema(
        query=GraphQLObjectType("Query", {"field": GraphQLField(type_)}), types=[type_]
    )


def schema_with_object_with_field_resolver(
    resolve_value: GraphQLFieldResolver
) -> GraphQLSchema:
    BadResolverType = GraphQLObjectType(
        "BadResolver", {"badField": GraphQLField(GraphQLString, resolve=resolve_value)}
    )

    return GraphQLSchema(
        GraphQLObjectType("Query", {"f": GraphQLField(BadResolverType)})
    )


def describe_type_system_scalars():
    def accepts_a_scalar_type_defining_serialize():
        schema_with_field_type(GraphQLScalarType("SomeScalar", lambda: None))

    def accepts_a_scalar_type_defining_parse_value_and_parse_literal():
        schema_with_field_type(
            GraphQLScalarType(
                "SomeScalar",
                serialize=lambda: None,
                parse_value=lambda: None,
                parse_literal=lambda: None,
            )
        )

    def rejects_a_scalar_type_not_defining_serialize():
        with raises(
            TypeError, match="missing 1 required positional argument: 'serialize'"
        ):
            # noinspection PyArgumentList
            schema_with_field_type(GraphQLScalarType("SomeScalar"))
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_field_type(GraphQLScalarType("SomeScalar", None))
        msg = str(exc_info.value)
        assert msg == (
            "SomeScalar must provide 'serialize' function."
            " If this custom Scalar is also used as an input type,"
            " ensure 'parse_value' and 'parse_literal' functions"
            " are also provided."
        )

    def rejects_a_scalar_type_defining_serialize_with_incorrect_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_field_type(GraphQLScalarType("SomeScalar", {}))
        msg = str(exc_info.value)
        assert msg == (
            "SomeScalar must provide 'serialize' function."
            " If this custom Scalar is also used as an input type,"
            " ensure 'parse_value' and 'parse_literal' functions"
            " are also provided."
        )

    def rejects_a_scalar_type_defining_parse_value_but_not_parse_literal():
        with raises(TypeError) as exc_info:
            schema_with_field_type(
                GraphQLScalarType("SomeScalar", lambda: None, parse_value=lambda: None)
            )
        msg = str(exc_info.value)
        assert msg == (
            "SomeScalar must provide both"
            " 'parse_value' and 'parse_literal' functions."
        )

    def rejects_a_scalar_type_defining_parse_literal_but_not_parse_value():
        with raises(TypeError) as exc_info:
            schema_with_field_type(
                GraphQLScalarType(
                    "SomeScalar", lambda: None, parse_literal=lambda: None
                )
            )
        msg = str(exc_info.value)
        assert msg == (
            "SomeScalar must provide both"
            " 'parse_value' and 'parse_literal' functions."
        )

    def rejects_a_scalar_type_incorrectly_defining_parse_literal_and_value():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_field_type(
                GraphQLScalarType(
                    "SomeScalar", lambda: None, parse_value={}, parse_literal={}
                )
            )
        msg = str(exc_info.value)
        assert msg == (
            "SomeScalar must provide both"
            " 'parse_value' and 'parse_literal' functions."
        )


def describe_type_system_objects():
    def does_not_mutate_passed_field_definitions():
        output_fields = {
            "field1": GraphQLField(GraphQLString),
            "field2": GraphQLField(
                GraphQLString, args={"id": GraphQLArgument(GraphQLString)}
            ),
        }

        TestObject1 = GraphQLObjectType("Test1", output_fields)
        TestObject2 = GraphQLObjectType("Test2", output_fields)

        assert TestObject1.fields == TestObject2.fields
        assert output_fields == {
            "field1": GraphQLField(GraphQLString),
            "field2": GraphQLField(
                GraphQLString, args={"id": GraphQLArgument(GraphQLString)}
            ),
        }

        input_fields = {
            "field1": GraphQLInputField(GraphQLString),
            "field2": GraphQLInputField(GraphQLString),
        }

        TestInputObject1 = GraphQLInputObjectType("Test1", input_fields)
        TestInputObject2 = GraphQLInputObjectType("Test2", input_fields)

        assert TestInputObject1.fields == TestInputObject2.fields
        assert input_fields == {
            "field1": GraphQLInputField(GraphQLString),
            "field2": GraphQLInputField(GraphQLString),
        }

    def defines_an_object_type_with_deprecated_field():
        TypeWithDeprecatedField = GraphQLObjectType(
            "foo",
            {
                "bar": GraphQLField(
                    GraphQLString, deprecation_reason="A terrible reason"
                )
            },
        )

        deprecated_field = TypeWithDeprecatedField.fields["bar"]
        assert deprecated_field == GraphQLField(
            GraphQLString, deprecation_reason="A terrible reason"
        )
        assert deprecated_field.is_deprecated is True
        assert deprecated_field.deprecation_reason == "A terrible reason"
        assert deprecated_field.type is GraphQLString
        assert deprecated_field.args == {}

    def accepts_an_object_type_with_output_type_as_field():
        # this is a shortcut syntax for simple fields
        obj_type = GraphQLObjectType("SomeObject", {"f": GraphQLString})
        field = obj_type.fields["f"]
        assert isinstance(field, GraphQLField)
        assert field.type is GraphQLString

    def accepts_an_object_type_with_a_field_function():
        obj_type = GraphQLObjectType(
            "SomeObject", lambda: {"f": GraphQLField(GraphQLString)}
        )
        assert obj_type.fields["f"].type is GraphQLString

    def thunk_for_fields_of_object_type_is_resolved_only_once():
        def fields():
            nonlocal calls
            calls += 1
            return {"f": GraphQLField(GraphQLString)}

        calls = 0
        obj_type = GraphQLObjectType("SomeObject", fields)
        assert "f" in obj_type.fields
        assert calls == 1
        assert "f" in obj_type.fields
        assert calls == 1

    def accepts_an_object_type_with_field_args():
        obj_type = GraphQLObjectType(
            "SomeObject",
            {
                "goodField": GraphQLField(
                    GraphQLString, args={"goodArg": GraphQLArgument(GraphQLString)}
                )
            },
        )
        assert "goodArg" in obj_type.fields["goodField"].args

    def accepts_an_object_type_with_list_interfaces():
        obj_type = GraphQLObjectType(
            "SomeObject",
            interfaces=[InterfaceType],
            fields={"f": GraphQLField(GraphQLString)},
        )
        assert obj_type.interfaces == [InterfaceType]

    def accepts_object_type_with_interfaces_as_a_function_returning_a_list():
        obj_type = GraphQLObjectType(
            "SomeObject",
            interfaces=lambda: [InterfaceType],
            fields={"f": GraphQLField(GraphQLString)},
        )
        assert obj_type.interfaces == [InterfaceType]

    def thunk_for_interfaces_of_object_type_is_resolved_only_once():
        def interfaces():
            nonlocal calls
            calls += 1
            return [InterfaceType]

        calls = 0
        obj_type = GraphQLObjectType(
            "SomeObject",
            interfaces=interfaces,
            fields={"f": GraphQLField(GraphQLString)},
        )
        assert obj_type.interfaces == [InterfaceType]
        assert calls == 1
        assert obj_type.interfaces == [InterfaceType]
        assert calls == 1

    def accepts_a_lambda_as_an_object_field_resolver():
        schema_with_object_with_field_resolver(lambda _obj, _info: {})

    def rejects_an_object_type_field_with_undefined_config():
        undefined_field = cast(GraphQLField, None)
        obj_type = GraphQLObjectType("SomeObject", {"f": undefined_field})
        with raises(TypeError) as exc_info:
            if obj_type.fields:
                pass
        msg = str(exc_info.value)
        assert msg == "SomeObject fields must be GraphQLField or output type objects."

    def rejects_an_object_type_with_incorrectly_typed_fields():
        invalid_field = cast(GraphQLField, [GraphQLField(GraphQLString)])
        obj_type = GraphQLObjectType("SomeObject", {"f": invalid_field})
        with raises(TypeError) as exc_info:
            if obj_type.fields:
                pass
        msg = str(exc_info.value)
        assert msg == "SomeObject fields must be GraphQLField or output type objects."

    def rejects_an_object_type_field_function_that_returns_incorrect_type():
        obj_type = GraphQLObjectType(
            "SomeObject", lambda: [GraphQLField(GraphQLString)]
        )
        with raises(TypeError) as exc_info:
            if obj_type.fields:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeObject fields must be a dict with field names as keys"
            " or a function which returns such an object."
        )

    def rejects_an_object_type_with_incorrectly_typed_field_args():
        invalid_args = [{"bad_args": GraphQLArgument(GraphQLString)}]
        invalid_args = cast(Dict[str, GraphQLArgument], invalid_args)
        with raises(TypeError) as exc_info:
            GraphQLObjectType(
                "SomeObject",
                {"badField": GraphQLField(GraphQLString, args=invalid_args)},
            )
        msg = str(exc_info.value)
        assert msg == "Field args must be a dict with argument names as keys."

    def rejects_an_object_with_is_deprecated_instead_of_deprecation_reason_on_field():
        kwargs = dict(is_deprecated=True)
        with raises(
            TypeError, match="got an unexpected keyword argument 'is_deprecated'"
        ):
            GraphQLObjectType(
                "OldObject", {"field": GraphQLField(GraphQLString, **kwargs)}
            )

    def rejects_an_object_type_with_incorrectly_typed_interfaces():
        obj_type = GraphQLObjectType(
            "SomeObject", interfaces={}, fields={"f": GraphQLField(GraphQLString)}
        )
        with raises(TypeError) as exc_info:
            if obj_type.interfaces:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeObject interfaces must be a list/tuple"
            " or a function which returns a list/tuple."
        )

    def rejects_object_type_with_incorrectly_typed_interfaces_as_a_function():
        obj_type = GraphQLObjectType(
            "SomeObject",
            interfaces=lambda: {},
            fields={"f": GraphQLField(GraphQLString)},
        )
        with raises(TypeError) as exc_info:
            if obj_type.interfaces:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeObject interfaces must be a list/tuple"
            " or a function which returns a list/tuple."
        )

    def rejects_an_empty_object_field_resolver():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_object_with_field_resolver({})
        msg = str(exc_info.value)
        assert msg == "Field resolver must be a function if provided,  but got: {}."

    def rejects_a_constant_scalar_value_resolver():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_object_with_field_resolver(0)
        msg = str(exc_info.value)
        assert msg == "Field resolver must be a function if provided,  but got: 0."

    def rejects_an_object_type_with_an_incorrect_type_for_is_type_of():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_field_type(
                GraphQLObjectType(
                    "AnotherObject", {"f": GraphQLField(GraphQLString)}, is_type_of={}
                )
            )
        msg = str(exc_info.value)
        assert msg == (
            "AnotherObject must provide 'is_type_of' as a function, but got: {}."
        )


def describe_type_system_interfaces():
    def accepts_an_interface_type_defining_resolve_type():
        AnotherInterfaceType = GraphQLInterfaceType(
            "AnotherInterface", {"f": GraphQLField(GraphQLString)}
        )

        schema = schema_with_field_type(
            GraphQLObjectType(
                "SomeObject", {"f": GraphQLField(GraphQLString)}, [AnotherInterfaceType]
            )
        )

        assert (
            schema.query_type.fields["field"].type.interfaces[0] is AnotherInterfaceType
        )

    def rejects_an_interface_type_with_an_incorrect_type_for_resolve_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInterfaceType(
                "AnotherInterface", {"f": GraphQLField(GraphQLString)}, resolve_type={}
            )
        msg = str(exc_info.value)
        assert msg == (
            "AnotherInterface must provide 'resolve_type' as a function,"
            " but got: {}."
        )


def describe_type_system_unions():
    def allows_a_thunk_for_union_member_types():
        union = GraphQLUnionType("ThunkUnion", lambda: [ObjectType])

        types = union.types
        assert len(types) == 1
        assert types[0] is ObjectType

    def accepts_a_union_type_defining_resolve_type():
        assert schema_with_field_type(GraphQLUnionType("SomeUnion", [ObjectType]))

    def accepts_a_union_type_with_list_types():
        assert schema_with_field_type(GraphQLUnionType("SomeUnion", [ObjectType]))

    def accepts_a_union_type_with_function_returning_a_list_of_types():
        schema_with_field_type(GraphQLUnionType("SomeUnion", lambda: [ObjectType]))

    def accepts_a_union_type_without_types():
        with raises(TypeError, match="missing 1 required positional argument: 'types'"):
            # noinspection PyArgumentList
            schema_with_field_type(GraphQLUnionType("SomeUnion"))
        assert schema_with_field_type(GraphQLUnionType("SomeUnion", None))
        assert schema_with_field_type(GraphQLUnionType("SomeUnion", []))

    def rejects_an_interface_type_with_an_incorrect_type_for_resolve_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_field_type(GraphQLUnionType("SomeUnion", [], resolve_type={}))
        msg = str(exc_info.value)
        assert msg == (
            "SomeUnion must provide 'resolve_type' as a function, but got: {}."
        )

    def rejects_a_union_type_with_incorrectly_typed_types():
        with raises(TypeError) as exc_info:
            schema_with_field_type(GraphQLUnionType("SomeUnion", {"type": ObjectType}))
        msg = str(exc_info.value)
        assert msg == (
            "SomeUnion types must be a list/tuple"
            " or a function which returns a list/tuple."
        )


def describe_type_system_enums():
    def defines_an_enum_type_with_deprecated_value():
        EnumTypeWithDeprecatedValue = GraphQLEnumType(
            name="EnumWithDeprecatedValue",
            values={"foo": GraphQLEnumValue(deprecation_reason="Just because")},
        )

        deprecated_value = EnumTypeWithDeprecatedValue.values["foo"]
        assert deprecated_value == GraphQLEnumValue(deprecation_reason="Just because")
        assert deprecated_value.is_deprecated is True
        assert deprecated_value.deprecation_reason == "Just because"
        assert deprecated_value.value is None
        assert deprecated_value.ast_node is None

    def defines_an_enum_type_with_a_value_of_none_and_invalid():
        EnumTypeWithNullishValue = GraphQLEnumType(
            name="EnumWithNullishValue", values={"NULL": None, "UNDEFINED": INVALID}
        )

        assert EnumTypeWithNullishValue.values == {
            "NULL": GraphQLEnumValue(),
            "UNDEFINED": GraphQLEnumValue(INVALID),
        }
        null_value = EnumTypeWithNullishValue.values["NULL"]
        assert null_value.description is None
        assert null_value.is_deprecated is False
        assert null_value.deprecation_reason is None
        assert null_value.value is None
        assert null_value.ast_node is None
        undefined_value = EnumTypeWithNullishValue.values["UNDEFINED"]
        assert undefined_value.description is None
        assert undefined_value.is_deprecated is False
        assert undefined_value.deprecation_reason is None
        assert undefined_value.value is INVALID
        assert undefined_value.ast_node is None

    def accepts_a_well_defined_enum_type_with_empty_value_definition():
        enum_type = GraphQLEnumType("SomeEnum", {"FOO": None, "BAR": None})
        assert enum_type.values["FOO"].value is None
        assert enum_type.values["BAR"].value is None

    def accepts_a_well_defined_enum_type_with_internal_value_definition():
        enum_type = GraphQLEnumType("SomeEnum", {"FOO": 10, "BAR": 20})
        assert enum_type.values["FOO"].value == 10
        assert enum_type.values["BAR"].value == 20
        enum_type = GraphQLEnumType(
            "SomeEnum", {"FOO": GraphQLEnumValue(10), "BAR": GraphQLEnumValue(20)}
        )
        assert enum_type.values["FOO"].value == 10
        assert enum_type.values["BAR"].value == 20

    def rejects_an_enum_type_with_incorrectly_typed_values():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", [{"FOO": 10}])  # type: ignore
        msg = str(exc_info.value)
        assert msg == (
            "SomeEnum values must be an Enum or a dict with value names as keys."
        )

    def does_not_allow_is_deprecated_instead_of_deprecation_reason_on_enum():
        with raises(
            TypeError, match="got an unexpected keyword argument 'is_deprecated'"
        ):
            # noinspection PyArgumentList
            GraphQLEnumType("SomeEnum", {"FOO": GraphQLEnumValue(is_deprecated=True)})


def describe_type_system_input_objects():
    def describe_type_system_input_objects_must_have_fields():
        def accepts_an_input_object_type_with_fields():
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": GraphQLInputField(GraphQLString)}
            )
            assert input_obj_type.fields["f"].type is GraphQLString

        def accepts_an_input_object_type_with_a_field_function():
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", lambda: {"f": GraphQLInputField(GraphQLString)}
            )
            assert input_obj_type.fields["f"].type is GraphQLString

        def rejects_an_input_object_type_with_incorrect_fields():
            input_obj_type = GraphQLInputObjectType("SomeInputObject", [])
            with raises(TypeError) as exc_info:
                if input_obj_type.fields:
                    pass
            msg = str(exc_info.value)
            assert msg == (
                "SomeInputObject fields must be a dict with field names as keys"
                " or a function which returns such an object."
            )

        def accepts_an_input_object_type_with_input_type_as_field():
            # this is a shortcut syntax for simple input fields
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": GraphQLString}
            )
            field = input_obj_type.fields["f"]
            assert isinstance(field, GraphQLInputField)
            assert field.type is GraphQLString

        def rejects_an_input_object_type_with_incorrect_fields_function():
            input_obj_type = GraphQLInputObjectType("SomeInputObject", lambda: [])
            with raises(TypeError) as exc_info:
                if input_obj_type.fields:
                    pass
            msg = str(exc_info.value)
            assert msg == (
                "SomeInputObject fields must be a dict with field names as keys"
                " or a function which returns such an object."
            )

    def describe_type_system_input_objects_fields_must_not_have_resolvers():
        def rejects_an_input_object_type_with_resolvers():
            with raises(
                TypeError, match="got an unexpected keyword argument 'resolve'"
            ):
                # noinspection PyArgumentList
                GraphQLInputObjectType(
                    "SomeInputObject",
                    {"f": GraphQLInputField(GraphQLString, resolve=lambda: 0)},
                )
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": GraphQLField(GraphQLString, resolve=lambda: 0)}
            )
            with raises(TypeError) as exc_info:
                if input_obj_type.fields:
                    pass
            msg = str(exc_info.value)
            assert msg == (
                "SomeInputObject fields must be GraphQLInputField"
                " or input type objects."
            )

        def rejects_an_input_object_type_with_resolver_constant():
            with raises(
                TypeError, match="got an unexpected keyword argument 'resolve'"
            ):
                # noinspection PyArgumentList
                GraphQLInputObjectType(
                    "SomeInputObject",
                    {"f": GraphQLInputField(GraphQLString, resolve={})},
                )


def describe_type_system_list():
    types = [
        ScalarType,
        ObjectType,
        UnionType,
        InterfaceType,
        EnumType,
        InputObjectType,
        ListOfScalarsType,
        NonNullScalarType,
    ]

    @mark.parametrize("type_", types, ids=lambda type_: type_.__class__.__name__)
    def accepts_a_type_as_item_type_of_list(type_):
        assert GraphQLList(type_)

    not_types = [{}, dict, str, object, None]

    @mark.parametrize("type_", not_types, ids=lambda type_: repr(type_))
    def rejects_a_non_type_as_item_type_of_list(type_):
        with raises(TypeError) as exc_info:
            GraphQLList(type_)
        msg = str(exc_info.value)
        assert msg == (
            f"Can only create a wrapper for a GraphQLType, but got: {type_}."
        )


def describe_type_system_non_null():
    types = [
        ScalarType,
        ObjectType,
        UnionType,
        InterfaceType,
        EnumType,
        InputObjectType,
        ListOfScalarsType,
        ListOfNonNullScalarsType,
    ]

    @mark.parametrize("type_", types, ids=lambda type_: type_.__class__.__name__)
    def accepts_a_type_as_nullable_type_of_non_null(type_):
        assert GraphQLNonNull(type_)

    not_types = [NonNullScalarType, {}, dict, str, object, None]

    @mark.parametrize("type_", not_types, ids=lambda type_: repr(type_))
    def rejects_a_non_type_as_nullable_type_of_non_null(type_):
        with raises(TypeError) as exc_info:
            GraphQLNonNull(type_)
        msg = str(exc_info.value)
        assert (
            msg
            == (
                "Can only create NonNull of a Nullable GraphQLType"
                f" but got: {type_}."
            )
            if isinstance(type_, GraphQLNonNull)
            else f"Can only create a wrapper for a GraphQLType, but got: {type_}."
        )


def describe_type_system_test_utility_methods():
    def stringifies_simple_types():
        assert str(ScalarType) == "Scalar"
        assert str(ObjectType) == "Object"
        assert str(InterfaceType) == "Interface"
        assert str(UnionType) == "Union"
        assert str(EnumType) == "Enum"
        assert str(InputObjectType) == "InputObject"

        assert str(NonNullScalarType) == "Scalar!"
        assert str(ListOfScalarsType) == "[Scalar]"
        assert str(NonNullListOfScalarsType) == "[Scalar]!"
        assert str(ListOfNonNullScalarsType) == "[Scalar!]"
        assert str(GraphQLList(ListOfScalarsType)) == "[[Scalar]]"

    def simple_types_have_repr():
        assert repr(ScalarType) == "<GraphQLScalarType 'Scalar'>"
        assert repr(ObjectType) == "<GraphQLObjectType 'Object'>"
        assert repr(InterfaceType) == "<GraphQLInterfaceType 'Interface'>"
        assert repr(UnionType) == "<GraphQLUnionType 'Union'>"
        assert repr(EnumType) == "<GraphQLEnumType 'Enum'>"
        assert repr(InputObjectType) == "<GraphQLInputObjectType 'InputObject'>"
        assert (
            repr(ListOfNonNullScalarsType)
            == "<GraphQLList <GraphQLNonNull <GraphQLScalarType 'Scalar'>>>"
        )
        assert (
            repr(GraphQLList(ListOfScalarsType))
            == "<GraphQLList <GraphQLList <GraphQLScalarType 'Scalar'>>>"
        )
