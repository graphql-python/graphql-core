from typing import cast, Dict

from pytest import mark, raises  # type: ignore

from graphql.error import INVALID
from graphql.language import (
    parse_value,
    EnumValueNode,
    Node,
    InputValueDefinitionNode,
    StringValueNode,
    TypeDefinitionNode,
    TypeExtensionNode,
)
from graphql.type import (
    GraphQLArgument,
    GraphQLEnumValue,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLString,
    GraphQLUnionType,
)

ScalarType = GraphQLScalarType("Scalar")
ObjectType = GraphQLObjectType("Object", {})
InterfaceType = GraphQLInterfaceType("Interface")
UnionType = GraphQLUnionType(
    "Union", [ObjectType], resolve_type=lambda _obj, _info, _type: None
)
EnumType = GraphQLEnumType("Enum", {"foo": GraphQLEnumValue()})
InputObjectType = GraphQLInputObjectType("InputObject", {})

ListOfScalarsType = GraphQLList(ScalarType)
NonNullScalarType = GraphQLNonNull(ScalarType)
ListOfNonNullScalarsType = GraphQLList(NonNullScalarType)
NonNullListOfScalarsType = GraphQLNonNull(ListOfScalarsType)


def describe_type_system_scalars():
    def defines_a_scalar_type():
        scalar = GraphQLScalarType("SomeScalar")
        assert scalar.name == "SomeScalar"
        kwargs = scalar.to_kwargs()
        assert kwargs == {
            "name": "SomeScalar",
            "description": None,
            "serialize": None,
            "parse_value": None,
            "parse_literal": None,
            "ast_node": None,
            "extension_ast_nodes": [],
        }

    def accepts_a_scalar_type_defining_serialize():
        def serialize(value):
            return value

        scalar = GraphQLScalarType("SomeScalar", serialize)
        assert scalar.serialize is serialize
        assert scalar.to_kwargs()["serialize"] is serialize

    def defines_a_scalar_type_with_a_description():
        description = "nice scalar"
        scalar = GraphQLScalarType("SomeScalar", description=description)
        assert scalar.description is description
        assert scalar.to_kwargs()["description"] is description

    def accepts_a_scalar_type_defining_parse_value_and_parse_literal():
        def parse_value(_value):
            return None

        def parse_literal(_value_node, _variables):
            return None

        scalar = GraphQLScalarType(
            "SomeScalar", parse_value=parse_value, parse_literal=parse_literal
        )
        assert scalar.parse_value is parse_value
        assert scalar.parse_literal is parse_literal

        kwargs = scalar.to_kwargs()
        assert kwargs["parse_value"] is parse_value
        assert kwargs["parse_literal"] is parse_literal

    def provides_default_methods_if_omitted():
        scalar = GraphQLScalarType("Foo")

        assert scalar.serialize is GraphQLScalarType.serialize
        assert scalar.parse_value is GraphQLScalarType.parse_value
        assert scalar.parse_literal.__func__ is GraphQLScalarType.parse_literal

        kwargs = scalar.to_kwargs()
        assert kwargs["serialize"] is None
        assert kwargs["parse_value"] is None
        assert kwargs["parse_literal"] is None

    def use_parse_value_for_parsing_literals_if_parse_literal_omitted():
        scalar = GraphQLScalarType(
            "Foo", parse_value=lambda value: f"parse_value: {value!r}"
        )

        assert scalar.parse_literal(parse_value("null")) == "parse_value: None"
        assert (
            scalar.parse_literal(parse_value('{foo: "bar"}'))
            == "parse_value: {'foo': 'bar'}"
        )

    def rejects_a_scalar_type_without_a_name():
        with raises(TypeError, match="missing .* required .* 'name'"):
            # noinspection PyArgumentList
            GraphQLScalarType()
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType(None)
        assert str(exc_info.value) == "Must provide name."
        with raises(TypeError) as exc_info:
            GraphQLScalarType("")
        assert str(exc_info.value) == "Must provide name."

    def rejects_a_scalar_type_with_incorrectly_typed_name():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType(name=42)
        assert str(exc_info.value) == "The name must be a string."

    def rejects_a_scalar_type_with_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType("SomeScalar", description=[])
        assert str(exc_info.value) == "The description must be a string."

    def rejects_a_scalar_type_defining_serialize_with_incorrect_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType("SomeScalar", {})
        assert str(exc_info.value) == (
            "SomeScalar must provide 'serialize' as a function."
            " If this custom Scalar is also used as an input type,"
            " ensure 'parse_value' and 'parse_literal' functions"
            " are also provided."
        )

    def rejects_a_scalar_type_defining_parse_literal_but_not_parse_value():
        with raises(TypeError) as exc_info:
            GraphQLScalarType("SomeScalar", parse_literal=lambda: None)
        assert str(exc_info.value) == (
            "SomeScalar must provide both"
            " 'parse_value' and 'parse_literal' as functions."
        )

    def rejects_a_scalar_type_incorrectly_defining_parse_literal_and_value():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType("SomeScalar", parse_value={}, parse_literal={})
        assert str(exc_info.value) == (
            "SomeScalar must provide both"
            " 'parse_value' and 'parse_literal' as functions."
        )

    def rejects_a_scalar_type_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType("SomeScalar", ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "SomeScalar AST node must be a TypeDefinitionNode."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType("SomeScalar", ast_node=TypeDefinitionNode())
        msg = str(exc_info.value)
        assert msg == "SomeScalar AST node must be a ScalarTypeDefinitionNode."

    def rejects_a_scalar_type_with_incorrect_extension_ast_nodes():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType("SomeScalar", extension_ast_nodes=[Node()])
        assert str(exc_info.value) == (
            "SomeScalar extension AST nodes must be specified"
            " as a sequence of TypeExtensionNode instances."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType("SomeScalar", extension_ast_nodes=[TypeExtensionNode()])
        assert str(exc_info.value) == (
            "SomeScalar extension AST nodes must be specified"
            " as a sequence of ScalarTypeExtensionNode instances."
        )


def describe_type_system_fields():
    def defines_a_field():
        field = GraphQLField(GraphQLString)
        assert field.type is GraphQLString
        kwargs = field.to_kwargs()
        assert kwargs == {
            "type_": GraphQLString,
            "args": None,
            "resolve": None,
            "subscribe": None,
            "description": None,
            "deprecation_reason": None,
            "ast_node": None,
        }

    def defines_a_field_with_args():
        arg = GraphQLArgument(GraphQLInt)
        field = GraphQLField(GraphQLString, {"arg": arg})
        assert isinstance(field.args, dict)
        assert list(field.args) == ["arg"]
        assert field.args["arg"] is arg
        assert field.to_kwargs()["args"] == {"arg": arg}

    def defines_a_field_with_input_types_as_args():
        field = GraphQLField(GraphQLString, {"arg": GraphQLString})
        assert isinstance(field.args, dict)
        assert list(field.args) == ["arg"]
        arg = field.args["arg"]
        assert isinstance(arg, GraphQLArgument)
        assert arg.type is GraphQLString

    def defines_a_scalar_type_with_a_description():
        description = "nice field"
        field = GraphQLField(GraphQLString, description=description)
        assert field.description is description
        assert field.to_kwargs()["description"] is description

    def defines_a_scalar_type_with_a_deprecation_reason():
        deprecation_reason = "field is redundant"
        field = GraphQLField(GraphQLString, deprecation_reason=deprecation_reason)
        assert field.deprecation_reason is deprecation_reason
        assert field.to_kwargs()["deprecation_reason"] is deprecation_reason

    def rejects_a_field_with_incorrect_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLField(InputObjectType)
        assert str(exc_info.value) == "Field type must be an output type."

    def rejects_a_field_with_incorrect_args():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLField(GraphQLString, args=[])
        assert str(exc_info.value) == (
            "Field args must be a dict with argument names as keys."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLField(GraphQLString, args={"arg": GraphQLObjectType})
        assert str(exc_info.value) == (
            "Field args must be GraphQLArguments or input type objects."
        )

    def rejects_a_field_with_an_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLField(GraphQLString, description=[])
        msg = str(exc_info.value)
        assert msg == "The description must be a string."

    def rejects_a_field_with_an_incorrectly_typed_deprecation_reason():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLField(GraphQLString, deprecation_reason=[])
        msg = str(exc_info.value)
        assert msg == "The deprecation reason must be a string."

    def rejects_a_field_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLField(GraphQLString, ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "Field AST node must be a FieldDefinitionNode."


def describe_type_system_objects():
    def does_not_mutate_passed_field_definitions():
        output_fields = {
            "field1": GraphQLField(ScalarType),
            "field2": GraphQLField(
                ScalarType, args={"id": GraphQLArgument(ScalarType)}
            ),
        }

        test_object_1 = GraphQLObjectType("Test1", output_fields)
        test_object_2 = GraphQLObjectType("Test2", output_fields)

        assert test_object_1.fields == test_object_2.fields
        assert output_fields == {
            "field1": GraphQLField(ScalarType),
            "field2": GraphQLField(
                ScalarType, args={"id": GraphQLArgument(ScalarType)}
            ),
        }

        input_fields = {
            "field1": GraphQLInputField(ScalarType),
            "field2": GraphQLInputField(ScalarType),
        }

        test_input_object_1 = GraphQLInputObjectType("Test1", input_fields)
        test_input_object_2 = GraphQLInputObjectType("Test2", input_fields)

        assert test_input_object_1.fields == test_input_object_2.fields
        assert input_fields == {
            "field1": GraphQLInputField(ScalarType),
            "field2": GraphQLInputField(ScalarType),
        }

    def defines_an_object_type_with_deprecated_field():
        TypeWithDeprecatedField = GraphQLObjectType(
            "foo",
            {"bar": GraphQLField(ScalarType, deprecation_reason="A terrible reason")},
        )

        deprecated_field = TypeWithDeprecatedField.fields["bar"]
        assert deprecated_field == GraphQLField(
            ScalarType, deprecation_reason="A terrible reason"
        )
        assert deprecated_field.is_deprecated is True
        assert deprecated_field.deprecation_reason == "A terrible reason"
        assert deprecated_field.type is ScalarType
        assert deprecated_field.args == {}

    def accepts_an_object_type_with_output_type_as_field():
        # this is a shortcut syntax for simple fields
        obj_type = GraphQLObjectType("SomeObject", {"f": ScalarType})
        assert list(obj_type.fields) == ["f"]
        field = obj_type.fields["f"]
        assert isinstance(field, GraphQLField)
        assert field.type is ScalarType
        assert field.args == {}
        assert field.is_deprecated is False

    def accepts_an_object_type_with_a_field_function():
        obj_type = GraphQLObjectType(
            "SomeObject", lambda: {"f": GraphQLField(ScalarType)}
        )
        assert list(obj_type.fields) == ["f"]
        field = obj_type.fields["f"]
        assert isinstance(field, GraphQLField)
        assert field.type is ScalarType
        assert field.args == {}
        assert field.is_deprecated is False

    def thunk_for_fields_of_object_type_is_resolved_only_once():
        def fields():
            nonlocal calls
            calls += 1
            return {"f": GraphQLField(ScalarType)}

        calls = 0
        obj_type = GraphQLObjectType("SomeObject", fields)
        assert "f" in obj_type.fields
        assert calls == 1
        assert "f" in obj_type.fields
        assert calls == 1

    def accepts_an_object_type_with_field_args():
        obj_type = GraphQLObjectType(
            "SomeObject",
            {"f": GraphQLField(ScalarType, args={"arg": GraphQLArgument(ScalarType)})},
        )
        field = obj_type.fields["f"]
        assert isinstance(field, GraphQLField)
        assert field.type is ScalarType
        assert list(field.args) == ["arg"]
        arg = field.args["arg"]
        assert isinstance(arg, GraphQLArgument)
        assert arg.type is ScalarType
        assert arg.description is None
        assert arg.default_value is INVALID
        assert arg.ast_node is None
        assert field.is_deprecated is False

    def accepts_an_object_type_with_list_interfaces():
        obj_type = GraphQLObjectType("SomeObject", {}, [InterfaceType])
        assert obj_type.interfaces == [InterfaceType]

    def accepts_object_type_with_interfaces_as_a_function_returning_a_list():
        obj_type = GraphQLObjectType("SomeObject", {}, lambda: [InterfaceType])
        assert obj_type.interfaces == [InterfaceType]

    def thunk_for_interfaces_of_object_type_is_resolved_only_once():
        def interfaces():
            nonlocal calls
            calls += 1
            return [InterfaceType]

        calls = 0
        obj_type = GraphQLObjectType("SomeObject", {}, interfaces)
        assert obj_type.interfaces == [InterfaceType]
        assert calls == 1
        assert obj_type.interfaces == [InterfaceType]
        assert calls == 1

    def accepts_a_lambda_as_an_object_field_resolver():
        obj_type = GraphQLObjectType(
            "SomeObject",
            {"f": GraphQLField(ScalarType, resolve=lambda _obj, _info: {})},
        )
        assert obj_type.fields

    def rejects_an_object_type_field_with_undefined_config():
        undefined_field = cast(GraphQLField, None)
        obj_type = GraphQLObjectType("SomeObject", {"f": undefined_field})
        with raises(TypeError) as exc_info:
            if obj_type.fields:
                pass
        msg = str(exc_info.value)
        assert msg == "SomeObject fields must be GraphQLField or output type objects."

    def rejects_an_object_type_with_incorrectly_typed_fields():
        invalid_field = cast(GraphQLField, [GraphQLField(ScalarType)])
        obj_type = GraphQLObjectType("SomeObject", {"f": invalid_field})
        with raises(TypeError) as exc_info:
            if obj_type.fields:
                pass
        msg = str(exc_info.value)
        assert msg == "SomeObject fields must be GraphQLField or output type objects."

    def rejects_an_object_type_field_function_that_returns_incorrect_type():
        obj_type = GraphQLObjectType("SomeObject", lambda: [GraphQLField(ScalarType)])
        with raises(TypeError) as exc_info:
            if obj_type.fields:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeObject fields must be specified as a dict with field names as keys."
        )

    def rejects_an_object_type_with_incorrectly_typed_field_args():
        invalid_args = [{"bad_args": GraphQLArgument(ScalarType)}]
        invalid_args = cast(Dict[str, GraphQLArgument], invalid_args)
        with raises(TypeError) as exc_info:
            GraphQLObjectType(
                "SomeObject", {"badField": GraphQLField(ScalarType, args=invalid_args)}
            )
        msg = str(exc_info.value)
        assert msg == "Field args must be a dict with argument names as keys."

    def rejects_an_object_with_is_deprecated_instead_of_deprecation_reason_on_field():
        kwargs = dict(is_deprecated=True)
        with raises(
            TypeError, match="got an unexpected keyword argument 'is_deprecated'"
        ):
            GraphQLObjectType(
                "OldObject", {"field": GraphQLField(ScalarType, **kwargs)}
            )

    def rejects_an_object_type_with_incorrectly_typed_interfaces():
        obj_type = GraphQLObjectType("SomeObject", {}, interfaces={})
        with raises(TypeError) as exc_info:
            if obj_type.interfaces:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeObject interfaces must be specified"
            " as a sequence of GraphQLInterfaceType instances."
        )

    def rejects_object_type_with_incorrectly_typed_interfaces_as_a_function():
        obj_type = GraphQLObjectType("SomeObject", {}, interfaces=lambda: {})
        with raises(TypeError) as exc_info:
            if obj_type.interfaces:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeObject interfaces must be specified"
            " as a sequence of GraphQLInterfaceType instances."
        )

    def rejects_an_empty_object_field_resolver():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType(
                "SomeObject", {"field": GraphQLField(ScalarType, resolve={})}
            )
        msg = str(exc_info.value)
        assert msg == "Field resolver must be a function if provided,  but got: {}."

    def rejects_a_constant_scalar_value_resolver():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType(
                "SomeObject", {"field": GraphQLField(ScalarType, resolve=0)}
            )
        msg = str(exc_info.value)
        assert msg == "Field resolver must be a function if provided,  but got: 0."

    def rejects_an_object_type_with_an_incorrect_type_for_is_type_of():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType("AnotherObject", {}, is_type_of={})
        msg = str(exc_info.value)
        assert msg == (
            "AnotherObject must provide 'is_type_of' as a function, but got: {}."
        )

    def rejects_an_object_type_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType("SomeObject", {}, ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "SomeObject AST node must be a TypeDefinitionNode."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType("SomeObject", {}, ast_node=TypeDefinitionNode())
        msg = str(exc_info.value)
        assert msg == "SomeObject AST node must be an ObjectTypeDefinitionNode."

    def rejects_an_object_type_with_incorrect_extension_ast_nodes():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType("SomeObject", {}, extension_ast_nodes=[Node()])
        assert str(exc_info.value) == (
            "SomeObject extension AST nodes must be specified"
            " as a sequence of TypeExtensionNode instances."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType(
                "SomeObject", {}, extension_ast_nodes=[TypeExtensionNode()]
            )
        assert str(exc_info.value) == (
            "SomeObject extension AST nodes must be specified"
            " as a sequence of ObjectTypeExtensionNode instances."
        )


def describe_type_system_interfaces():
    def defines_an_interface_type():
        fields = {"f": GraphQLField(ScalarType)}
        interface = GraphQLInterfaceType("AnotherInterface", fields)
        assert interface.name == "AnotherInterface"
        assert interface.fields == fields
        assert interface.fields is not fields
        assert interface.resolve_type is None
        kwargs = interface.to_kwargs()
        assert kwargs == {
            "name": "AnotherInterface",
            "description": None,
            "fields": fields,
            "resolve_type": None,
            "ast_node": None,
            "extension_ast_nodes": [],
        }

    def accepts_an_interface_type_defining_resolve_type():
        def resolve_type(_obj, _info, _type):
            return None

        interface = GraphQLInterfaceType(
            "AnotherInterface", {}, resolve_type=resolve_type
        )
        assert interface.resolve_type is resolve_type

    def accepts_an_interface_type_with_output_types_as_fields():
        interface = GraphQLInterfaceType("AnotherInterface", {"someField": ScalarType})
        fields = interface.fields
        assert isinstance(fields, dict)
        assert list(fields) == ["someField"]
        field = fields["someField"]
        assert isinstance(field, GraphQLField)
        assert field.type is ScalarType

    def accepts_an_interface_type_with_a_field_function():
        fields = {"f": GraphQLField(ScalarType)}
        interface = GraphQLInterfaceType("AnotherInterface", lambda: fields)
        assert interface.fields == fields

    def thunk_for_fields_of_interface_type_is_resolved_only_once():
        def fields():
            nonlocal calls
            calls += 1
            return {"f": GraphQLField(ScalarType)}

        calls = 0
        interface = GraphQLInterfaceType("AnotherInterface", fields)
        assert "f" in interface.fields
        assert calls == 1
        assert "f" in interface.fields
        assert calls == 1

    def rejects_an_interface_type_with_incorrectly_typed_fields():
        interface = GraphQLInterfaceType("SomeInterface", [])
        with raises(TypeError) as exc_info:
            if interface.fields:
                pass
        assert str(exc_info.value) == (
            "SomeInterface fields must be specified as a dict with field names as keys."
        )
        interface = GraphQLInterfaceType("SomeInterface", {"f": InputObjectType})
        with raises(TypeError) as exc_info:
            if interface.fields:
                pass
        assert str(exc_info.value) == (
            "SomeInterface fields must be GraphQLField or output type objects."
        )

    def rejects_an_interface_type_with_an_incorrect_type_for_resolve_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInterfaceType("AnotherInterface", {}, resolve_type={})
        assert str(exc_info.value) == (
            "AnotherInterface must provide 'resolve_type' as a function,"
            " but got: {}."
        )

    def rejects_an_interface_type_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInterfaceType("SomeInterface", ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "SomeInterface AST node must be a TypeDefinitionNode."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInterfaceType("SomeInterface", ast_node=TypeDefinitionNode())
        msg = str(exc_info.value)
        assert msg == "SomeInterface AST node must be an InterfaceTypeDefinitionNode."

    def rejects_an_interface_type_with_incorrect_extension_ast_nodes():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInterfaceType("SomeInterface", extension_ast_nodes=[Node()])
        assert str(exc_info.value) == (
            "SomeInterface extension AST nodes must be specified"
            " as a sequence of TypeExtensionNode instances."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInterfaceType(
                "SomeInterface", extension_ast_nodes=[TypeExtensionNode()]
            )
        assert str(exc_info.value) == (
            "SomeInterface extension AST nodes must be specified"
            " as a sequence of InterfaceTypeExtensionNode instances."
        )


def describe_type_system_unions():
    def accepts_a_union_type_defining_resolve_type():
        assert GraphQLUnionType("SomeUnion", [ObjectType])

    def accepts_a_union_type_with_list_types():
        union_type = GraphQLUnionType("SomeUnion", [ObjectType])
        assert union_type.types == [ObjectType]

    def accepts_a_union_type_with_function_returning_a_list_of_types():
        union_type = GraphQLUnionType("SomeUnion", lambda: [ObjectType])
        assert union_type.types == [ObjectType]

    def accepts_a_union_type_without_types():
        with raises(TypeError, match="missing 1 required positional argument: 'types'"):
            # noinspection PyArgumentList
            GraphQLUnionType("SomeUnion")
        union_type = GraphQLUnionType("SomeUnion", None)
        assert union_type.types == []
        union_type = GraphQLUnionType("SomeUnion", [])
        assert union_type.types == []

    def rejects_an_interface_type_with_an_incorrect_type_for_resolve_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLUnionType("SomeUnion", [], resolve_type={})
        msg = str(exc_info.value)
        assert msg == (
            "SomeUnion must provide 'resolve_type' as a function, but got: {}."
        )

    def rejects_a_union_type_with_incorrectly_typed_types():
        union_type = GraphQLUnionType("SomeUnion", {"type": ObjectType})
        with raises(TypeError) as exc_info:
            if union_type.types:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeUnion types must be specified"
            " as a sequence of GraphQLObjectType instances."
        )

    def rejects_a_union_type_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLUnionType("SomeUnion", [], ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "SomeUnion AST node must be a TypeDefinitionNode."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLUnionType("SomeUnion", [], ast_node=TypeDefinitionNode())
        msg = str(exc_info.value)
        assert msg == "SomeUnion AST node must be a UnionTypeDefinitionNode."

    def rejects_a_union_type_with_incorrect_extension_ast_nodes():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLUnionType("SomeUnion", [], extension_ast_nodes=[Node()])
        assert str(exc_info.value) == (
            "SomeUnion extension AST nodes must be specified"
            " as a sequence of TypeExtensionNode instances."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLUnionType("SomeUnion", [], extension_ast_nodes=[TypeExtensionNode()])
        assert str(exc_info.value) == (
            "SomeUnion extension AST nodes must be specified"
            " as a sequence of UnionTypeExtensionNode instances."
        )


def describe_type_system_enums():
    def defines_an_enum_type_with_a_description():
        description = "nice enum"
        enum_type = GraphQLEnumType("SomeEnum", {}, description=description)
        assert enum_type.description is description
        assert enum_type.to_kwargs()["description"] is description

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

    def serializes_an_enum():
        enum_type = GraphQLEnumType(
            "SomeEnum", {"FOO": "fooValue", "BAR": ["barValue"], "BAZ": None}
        )
        assert enum_type.values["FOO"].value == "fooValue"
        assert enum_type.values["BAR"].value == ["barValue"]
        assert enum_type.values["BAZ"].value is None
        assert enum_type.serialize(None) is INVALID
        assert enum_type.serialize(INVALID) is INVALID
        assert enum_type.serialize("fooValue") == "FOO"
        assert enum_type.serialize("FOO") is INVALID
        assert enum_type.serialize(["barValue"]) == "BAR"
        assert enum_type.serialize("BAR") is INVALID
        assert enum_type.serialize("BAZ") == "BAZ"
        assert enum_type.serialize("bazValue") is INVALID
        assert enum_type.serialize(["bazValue"]) is INVALID

    def parses_an_enum():
        enum_type = GraphQLEnumType(
            "SomeEnum", {"FOO": "fooValue", "BAR": ["barValue"], "BAZ": None}
        )
        assert enum_type.parse_value("FOO") == "fooValue"
        assert enum_type.parse_value("fooValue") is INVALID
        assert enum_type.parse_value("BAR") == ["barValue"]
        # noinspection PyTypeChecker
        assert enum_type.parse_value(["barValue"]) is INVALID  # type : ignore
        assert enum_type.parse_value("BAZ") == "BAZ"
        assert enum_type.parse_literal(EnumValueNode(value="FOO")) == "fooValue"
        assert enum_type.parse_literal(StringValueNode(value="FOO")) is INVALID
        assert enum_type.parse_literal(EnumValueNode(value="fooValue")) is INVALID
        assert enum_type.parse_literal(EnumValueNode(value="BAR")) == ["barValue"]
        assert enum_type.parse_literal(StringValueNode(value="BAR")) is INVALID
        assert enum_type.parse_literal(EnumValueNode(value="BAZ")) == "BAZ"
        assert enum_type.parse_literal(StringValueNode(value="BAZ")) is INVALID

    def rejects_an_enum_type_without_a_name():
        with raises(TypeError, match="missing .* required .* 'name'"):
            # noinspection PyArgumentList
            GraphQLEnumType(values={})
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType(None, values={})
        assert str(exc_info.value) == "Must provide name."
        with raises(TypeError) as exc_info:
            GraphQLEnumType("", values={})
        assert str(exc_info.value) == "Must provide name."

    def rejects_an_enum_type_with_incorrectly_typed_name():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType(name=42, values={})
        assert str(exc_info.value) == "The name must be a string."

    def rejects_an_enum_type_without_values():
        with raises(TypeError, match="missing .* required .* 'values'"):
            # noinspection PyArgumentList
            GraphQLEnumType("SomeEnum")
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", values=None)
        assert str(exc_info.value) == (
            "SomeEnum values must be an Enum or a dict with value names as keys."
        )

    def rejects_an_enum_type_with_incorrectly_typed_values():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", [{"FOO": 10}])
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

    def rejects_an_enum_type_with_an_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", {}, description=[])
        msg = str(exc_info.value)
        assert msg == "The description must be a string."

    def rejects_an_enum_type_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", {}, ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "SomeEnum AST node must be a TypeDefinitionNode."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", {}, ast_node=TypeDefinitionNode())
        msg = str(exc_info.value)
        assert msg == "SomeEnum AST node must be an EnumTypeDefinitionNode."

    def rejects_an_enum_type_with_incorrect_extension_ast_nodes():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", {}, extension_ast_nodes=[Node()])
        assert str(exc_info.value) == (
            "SomeEnum extension AST nodes must be specified"
            " as a sequence of TypeExtensionNode instances."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", {}, extension_ast_nodes=[TypeExtensionNode()])
        assert str(exc_info.value) == (
            "SomeEnum extension AST nodes must be specified"
            " as a sequence of EnumTypeExtensionNode instances."
        )

    def describe_enum_values():
        def accepts_an_enum_value_without_value():
            enum_value = GraphQLEnumValue()
            assert enum_value.value is None
            assert enum_value.to_kwargs()["value"] is None

        def accepts_an_enum_value_with_a_value():
            value = object()
            enum_value = GraphQLEnumValue(value)
            assert enum_value.value is value
            assert enum_value.to_kwargs()["value"] is value

        def accepts_an_enum_value_with_a_description():
            description = "nice enum value"
            enum_value = GraphQLEnumValue(description=description)
            assert enum_value.description is description
            assert enum_value.to_kwargs()["description"] is description

        def accepts_an_enum_value_with_deprecation_reason():
            deprecation_reason = "This has been overvalued"
            enum_value = GraphQLEnumValue(deprecation_reason=deprecation_reason)
            assert enum_value.deprecation_reason is deprecation_reason
            assert enum_value.to_kwargs()["deprecation_reason"] is deprecation_reason

        def can_compare_enum_values():
            assert GraphQLEnumValue() == GraphQLEnumValue()
            assert GraphQLEnumValue(
                "value", description="description", deprecation_reason="reason"
            ) == GraphQLEnumValue(
                "value", description="description", deprecation_reason="reason"
            )
            assert GraphQLEnumValue("value 1") != GraphQLEnumValue("value 2")
            assert GraphQLEnumValue(description="description 1") != GraphQLEnumValue(
                description="description 2"
            )
            assert GraphQLEnumValue(deprecation_reason="reason 1") != GraphQLEnumValue(
                deprecation_reason="reason 2"
            )

        def rejects_an_enum_value_with_an_incorrectly_typed_description():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLEnumValue(description=[])
            msg = str(exc_info.value)
            assert msg == "The description of the enum value must be a string."

        def rejects_an_enum_value_with_an_incorrectly_typed_deprecation_reason():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLEnumValue(deprecation_reason=[])
            msg = str(exc_info.value)
            assert msg == "The deprecation reason for the enum value must be a string."

        def rejects_an_enum_value_with_an_incorrect_ast_node():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLEnumValue(ast_node=TypeDefinitionNode())
            msg = str(exc_info.value)
            assert msg == "AST node must be an EnumValueDefinitionNode."


def describe_type_system_input_objects():
    def accepts_an_input_object_type_with_a_description():
        description = "nice input object"
        input_obj_type = GraphQLInputObjectType(
            "SomeInputObject", {}, description=description
        )
        assert input_obj_type.description is description
        assert input_obj_type.to_kwargs()["description"] is description

    def accepts_an_input_object_type_with_an_out_type_function():
        # This is an extension of GraphQL.js.
        input_obj_type = GraphQLInputObjectType("SomeInputObject", {}, out_type=dict)
        assert input_obj_type.out_type is dict
        assert input_obj_type.to_kwargs()["out_type"] is dict

    def provides_default_out_type_if_omitted():
        # This is an extension of GraphQL.js.
        input_obj_type = GraphQLInputObjectType("SomeInputObject", {})
        assert input_obj_type.out_type is GraphQLInputObjectType.out_type
        assert input_obj_type.to_kwargs()["out_type"] is None

    def rejects_an_input_object_type_with_incorrect_out_type_function():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputObjectType("SomeInputObject", {}, out_type=[])
        msg = str(exc_info.value)
        assert msg == (
            "The out type for SomeInputObject must be a function or a class."
        )

    def rejects_an_input_object_type_with_incorrectyl_typed_description():
        # noinspection PyTypeChecker
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputObjectType("SomeInputObject", {}, description=[])
        msg = str(exc_info.value)
        assert msg == "The description must be a string."

    def rejects_an_input_object_type_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputObjectType("SomeInputObject", {}, ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "SomeInputObject AST node must be a TypeDefinitionNode."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputObjectType("SomeInputObject", {}, ast_node=TypeDefinitionNode())
        assert str(exc_info.value) == (
            "SomeInputObject AST node must be an InputObjectTypeDefinitionNode."
        )

    def rejects_an_input_object_type_with_incorrect_extension_ast_nodes():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputObjectType("SomeInputObject", {}, extension_ast_nodes=[Node()])
        assert str(exc_info.value) == (
            "SomeInputObject extension AST nodes must be specified"
            " as a sequence of TypeExtensionNode instances."
        )
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputObjectType(
                "SomeInputObject", {}, extension_ast_nodes=[TypeExtensionNode()]
            )
        assert str(exc_info.value) == (
            "SomeInputObject extension AST nodes must be specified"
            " as a sequence of InputObjectTypeExtensionNode instances."
        )

    def describe_input_objects_must_have_fields():
        def accepts_an_input_object_type_with_fields():
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": GraphQLInputField(ScalarType)}
            )
            assert list(input_obj_type.fields) == ["f"]
            input_field = input_obj_type.fields["f"]
            assert isinstance(input_field, GraphQLInputField)
            assert input_field.type is ScalarType

        def accepts_an_input_object_type_with_input_type_as_field():
            # this is a shortcut syntax for simple input fields
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": ScalarType}
            )
            field = input_obj_type.fields["f"]
            assert isinstance(field, GraphQLInputField)
            assert field.type is ScalarType

        def accepts_an_input_object_type_with_a_field_function():
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", lambda: {"f": GraphQLInputField(ScalarType)}
            )
            assert list(input_obj_type.fields) == ["f"]
            input_field = input_obj_type.fields["f"]
            assert isinstance(input_field, GraphQLInputField)
            assert input_field.type is ScalarType

        def rejects_an_input_object_type_with_incorrect_fields():
            input_obj_type = GraphQLInputObjectType("SomeInputObject", [])
            with raises(TypeError) as exc_info:
                if input_obj_type.fields:
                    pass
            assert str(exc_info.value) == (
                "SomeInputObject fields must be specified"
                " as a dict with field names as keys."
            )

        def rejects_an_input_object_type_with_incorrect_fields_function():
            input_obj_type = GraphQLInputObjectType("SomeInputObject", lambda: [])
            with raises(TypeError) as exc_info:
                if input_obj_type.fields:
                    pass
            assert str(exc_info.value) == (
                "SomeInputObject fields must be specified"
                " as a dict with field names as keys."
            )

    def describe_input_objects_fields_must_not_have_resolvers():
        def rejects_an_input_object_type_with_resolvers():
            with raises(
                TypeError, match="got an unexpected keyword argument 'resolve'"
            ):
                # noinspection PyArgumentList
                GraphQLInputObjectType(
                    "SomeInputObject",
                    {"f": GraphQLInputField(ScalarType, resolve=lambda: 0)},
                )
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": GraphQLField(ScalarType, resolve=lambda: 0)}
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
                    "SomeInputObject", {"f": GraphQLInputField(ScalarType, resolve={})}
                )


def describe_type_system_arguments():
    def accepts_an_argument_with_a_description():
        description = "nice argument"
        argument = GraphQLArgument(GraphQLString, description=description)
        assert argument.description is description
        assert argument.to_kwargs()["description"] is description

    def accepts_an_argument_with_an_out_name():
        # This is an extension of GraphQL.js.
        out_name = "python_rocks"
        argument = GraphQLArgument(GraphQLString, out_name=out_name)
        assert argument.out_name is out_name
        assert argument.to_kwargs()["out_name"] is out_name

    def provides_no_out_name_if_omitted():
        # This is an extension of GraphQL.js.
        argument = GraphQLArgument(GraphQLString)
        assert argument.out_name is None
        assert argument.to_kwargs()["out_name"] is None

    def accepts_an_argument_with_an_ast_node():
        ast_node = InputValueDefinitionNode()
        argument = GraphQLArgument(GraphQLString, ast_node=ast_node)
        assert argument.ast_node is ast_node
        assert argument.to_kwargs()["ast_node"] is ast_node

    def rejects_an_argument_without_type():
        with raises(TypeError, match="missing 1 required positional argument"):
            # noinspection PyArgumentList
            GraphQLArgument()

    def rejects_an_argument_with_an_incorrect_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLArgument(GraphQLObjectType)
        msg = str(exc_info.value)
        assert msg == "Argument type must be a GraphQL input type."

    def rejects_an_argument_with_an_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLArgument(GraphQLString, description=[])
        msg = str(exc_info.value)
        assert msg == "Argument description must be a string."

    def rejects_an_argument_with_an_incorrect_out_name():
        # This is an extension of GraphQL.js.
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLArgument(GraphQLString, out_name=[])
        msg = str(exc_info.value)
        assert msg == "Argument out name must be a string."

    def rejects_an_argument_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLArgument(GraphQLString, ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "Argument AST node must be an InputValueDefinitionNode."


def describe_type_system_input_fields():
    def accepts_an_input_field_with_a_description():
        description = "good input"
        input_field = GraphQLInputField(GraphQLString, description=description)
        assert input_field.description is description
        assert input_field.to_kwargs()["description"] is description

    def accepts_an_input_field_with_an_out_name():
        # This is an extension of GraphQL.js.
        out_name = "python_rocks"
        input_field = GraphQLInputField(GraphQLString, out_name=out_name)
        assert input_field.out_name is out_name
        assert input_field.to_kwargs()["out_name"] is out_name

    def provides_no_out_name_if_omitted():
        # This is an extension of GraphQL.js.
        input_field = GraphQLInputField(GraphQLString)
        assert input_field.out_name is None
        assert input_field.to_kwargs()["out_name"] is None

    def accepts_an_input_field_with_an_ast_node():
        ast_node = InputValueDefinitionNode()
        input_field = GraphQLArgument(GraphQLString, ast_node=ast_node)
        assert input_field.ast_node is ast_node
        assert input_field.to_kwargs()["ast_node"] is ast_node

    def rejects_an_input_field_without_type():
        with raises(TypeError, match="missing 1 required positional argument"):
            # noinspection PyArgumentList
            GraphQLInputField()

    def rejects_an_input_field_with_an_incorrect_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputField(GraphQLObjectType)
        msg = str(exc_info.value)
        assert msg == "Input field type must be a GraphQL input type."

    def rejects_an_input_field_with_an_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputField(GraphQLString, description=[])
        msg = str(exc_info.value)
        assert msg == "Input field description must be a string."

    def rejects_an_input_field_with_an_incorrect_out_name():
        # This is an extension of GraphQL.js.
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputField(GraphQLString, out_name=[])
        msg = str(exc_info.value)
        assert msg == "Input field out name must be a string."

    def rejects_an_input_field_with_an_incorrect_ast_node():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLInputField(GraphQLString, ast_node=Node())
        msg = str(exc_info.value)
        assert msg == "Input field AST node must be an InputValueDefinitionNode."


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

    def stringifies_fields():
        assert str(GraphQLField(GraphQLNonNull(GraphQLString))) == "Field: String!"
        assert str(GraphQLField(GraphQLList(GraphQLInt))) == "Field: [Int]"

    def fields_have_repr():
        assert (
            repr(GraphQLField(GraphQLNonNull(GraphQLString)))
            == "<GraphQLField <GraphQLNonNull <GraphQLScalarType 'String'>>>"
        )
        assert (
            repr(GraphQLField(GraphQLList(GraphQLInt)))
            == "<GraphQLField <GraphQLList <GraphQLScalarType 'Int'>>>"
        )
