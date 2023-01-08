import pickle
from enum import Enum
from math import isnan, nan
from typing import Dict

from pytest import mark, raises

from graphql.error import GraphQLError
from graphql.language import (
    EnumTypeDefinitionNode,
    EnumTypeExtensionNode,
    EnumValueNode,
    InputObjectTypeDefinitionNode,
    InputObjectTypeExtensionNode,
    InputValueDefinitionNode,
    InterfaceTypeDefinitionNode,
    InterfaceTypeExtensionNode,
    ObjectTypeDefinitionNode,
    ObjectTypeExtensionNode,
    ScalarTypeDefinitionNode,
    ScalarTypeExtensionNode,
    StringValueNode,
    UnionTypeDefinitionNode,
    UnionTypeExtensionNode,
    ValueNode,
    parse_value,
)
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
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
    introspection_types,
)


ScalarType = GraphQLScalarType("Scalar")
ObjectType = GraphQLObjectType("Object", {})
InterfaceType = GraphQLInterfaceType("Interface", {})
UnionType = GraphQLUnionType(
    "Union",
    [ObjectType],
    resolve_type=lambda _obj, _info, _type: None,  # pragma: no cover
)
EnumType = GraphQLEnumType("Enum", {"foo": GraphQLEnumValue()})
InputObjectType = GraphQLInputObjectType("InputObject", {})

ListOfScalarsType = GraphQLList(ScalarType)
NonNullScalarType = GraphQLNonNull(ScalarType)
ListOfNonNullScalarsType = GraphQLList(NonNullScalarType)
NonNullListOfScalars = GraphQLNonNull(ListOfScalarsType)


def describe_type_system_scalars():
    def defines_a_scalar_type():
        scalar = GraphQLScalarType("SomeScalar")
        assert scalar.name == "SomeScalar"
        kwargs = scalar.to_kwargs()
        assert kwargs == {
            "name": "SomeScalar",
            "description": None,
            "specified_by_url": None,
            "serialize": None,
            "parse_value": None,
            "parse_literal": None,
            "extensions": {},
            "ast_node": None,
            "extension_ast_nodes": (),
        }

    def accepts_a_scalar_type_defining_serialize():
        def serialize(value):
            pass

        scalar = GraphQLScalarType("SomeScalar", serialize)
        assert scalar.serialize is serialize
        assert scalar.to_kwargs()["serialize"] is serialize

    def defines_a_scalar_type_with_a_description():
        description = "nice scalar"
        scalar = GraphQLScalarType("SomeScalar", description=description)
        assert scalar.description is description
        assert scalar.to_kwargs()["description"] is description

    def accepts_a_scalar_type_defining_specified_by_url():
        url = "https://example.com/foo_spec"
        scalar = GraphQLScalarType("SomeScalar", specified_by_url=url)
        assert scalar.specified_by_url == url
        assert scalar.to_kwargs()["specified_by_url"] == url

    def accepts_a_scalar_type_defining_parse_value_and_parse_literal():
        def parse_value(_value):
            pass

        def parse_literal(_value_node, _variables):
            pass

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
        assert (
            scalar.parse_literal.__func__  # type: ignore
            is GraphQLScalarType.parse_literal
        )

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
        assert (
            scalar.parse_literal(parse_value("{foo: { bar: $var } }"), {"var": "baz"})
            == "parse_value: {'foo': {'bar': 'baz'}}"
        )

    def accepts_a_scalar_type_with_ast_node_and_extension_ast_nodes():
        ast_node = ScalarTypeDefinitionNode()
        extension_ast_nodes = [ScalarTypeExtensionNode()]
        scalar = GraphQLScalarType(
            "SomeScalar", ast_node=ast_node, extension_ast_nodes=extension_ast_nodes
        )
        assert scalar.ast_node is ast_node
        assert scalar.extension_ast_nodes == tuple(extension_ast_nodes)

    def rejects_a_scalar_type_with_incorrectly_typed_name():
        with raises(TypeError, match="missing .* required .* 'name'"):
            # noinspection PyArgumentList
            GraphQLScalarType()  # type: ignore
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType(None)  # type: ignore
        assert str(exc_info.value) == "Must provide name."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLScalarType(42, {})  # type: ignore
        assert str(exc_info.value) == "Expected name to be a string."

    def rejects_a_scalar_type_with_invalid_name():
        with raises(GraphQLError) as exc_info:
            GraphQLScalarType("")
        assert str(exc_info.value) == "Expected name to be a non-empty string."
        with raises(GraphQLError) as exc_info:
            GraphQLScalarType("bad-name")
        assert str(exc_info.value) == (
            "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
        )

    def rejects_a_scalar_type_defining_parse_literal_but_not_parse_value():
        def parse_literal(_node: ValueNode, _vars=None):
            return Undefined  # pragma: no cover

        with raises(TypeError) as exc_info:
            GraphQLScalarType("SomeScalar", parse_literal=parse_literal)
        assert str(exc_info.value) == (
            "SomeScalar must provide both"
            " 'parse_value' and 'parse_literal' functions."
        )

    def pickles_a_custom_scalar_type():
        foo_type = GraphQLScalarType("Foo")
        cycled_foo_type = pickle.loads(pickle.dumps(foo_type))
        assert cycled_foo_type.name == foo_type.name
        assert cycled_foo_type is not foo_type

    def pickles_a_specified_scalar_type():
        cycled_int_type = pickle.loads(pickle.dumps(GraphQLInt))
        assert cycled_int_type.name == "Int"
        assert cycled_int_type is GraphQLInt


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
            "extensions": {},
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
        field = GraphQLField(GraphQLString, {"arg": GraphQLString})  # type: ignore
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


def describe_type_system_objects():
    def defines_an_object_type():
        fields = {"f": GraphQLField(ScalarType)}
        interfaces = (InterfaceType,)
        type_ = GraphQLObjectType("AnotherObjectType", fields, interfaces)
        assert type_.name == "AnotherObjectType"
        assert type_.fields == fields
        assert type_.fields is not fields
        assert type_.interfaces == interfaces
        assert type_.interfaces is interfaces
        assert type_.extensions == {}
        kwargs = type_.to_kwargs()
        assert kwargs == {
            "name": "AnotherObjectType",
            "description": None,
            "fields": fields,
            "interfaces": interfaces,
            "is_type_of": None,
            "extensions": {},
            "ast_node": None,
            "extension_ast_nodes": (),
        }

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
            {
                "bar": GraphQLField(ScalarType, deprecation_reason="A terrible reason"),
                "baz": GraphQLField(ScalarType, deprecation_reason=""),
            },
        )

        deprecated_field = TypeWithDeprecatedField.fields["bar"]
        assert deprecated_field == GraphQLField(
            ScalarType, deprecation_reason="A terrible reason"
        )
        assert deprecated_field.deprecation_reason == "A terrible reason"

        deprecated_field = TypeWithDeprecatedField.fields["baz"]
        assert deprecated_field == GraphQLField(ScalarType, deprecation_reason="")
        assert deprecated_field.deprecation_reason == ""

    def accepts_an_object_type_with_output_type_as_field():
        # this is a shortcut syntax for simple fields
        obj_type = GraphQLObjectType("SomeObject", {"f": ScalarType})  # type: ignore
        assert list(obj_type.fields) == ["f"]
        field = obj_type.fields["f"]
        assert isinstance(field, GraphQLField)
        assert field.type is ScalarType
        assert field.args == {}
        assert field.deprecation_reason is None

    def accepts_an_object_type_with_a_field_function():
        obj_type = GraphQLObjectType(
            "SomeObject", lambda: {"f": GraphQLField(ScalarType)}
        )
        assert list(obj_type.fields) == ["f"]
        field = obj_type.fields["f"]
        assert isinstance(field, GraphQLField)
        assert field.description is None
        assert field.type is ScalarType
        assert field.args == {}
        assert field.resolve is None
        assert field.subscribe is None
        assert field.deprecation_reason is None
        assert field.extensions == {}
        assert field.ast_node is None

    def thunk_for_fields_of_object_type_is_resolved_only_once():
        calls = 0

        def fields():
            nonlocal calls
            calls += 1
            return {"f": GraphQLField(ScalarType)}

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
        assert field.description is None
        assert field.type is ScalarType
        assert isinstance(field.args, dict)
        assert list(field.args) == ["arg"]
        arg = field.args["arg"]
        assert isinstance(arg, GraphQLArgument)
        assert arg.description is None
        assert arg.type is ScalarType
        assert arg.default_value is Undefined
        assert arg.deprecation_reason is None
        assert arg.extensions == {}
        assert arg.ast_node is None
        assert field.resolve is None
        assert field.subscribe is None
        assert field.deprecation_reason is None
        assert field.extensions == {}
        assert field.ast_node is None

    def accepts_an_object_type_with_list_interfaces():
        obj_type = GraphQLObjectType("SomeObject", {}, [InterfaceType])
        assert obj_type.interfaces == (InterfaceType,)

    def accepts_object_type_with_interfaces_as_a_function_returning_a_list():
        obj_type = GraphQLObjectType("SomeObject", {}, lambda: [InterfaceType])
        assert obj_type.interfaces == (InterfaceType,)

    def thunk_for_interfaces_of_object_type_is_resolved_only_once():
        calls = 0

        def interfaces():
            nonlocal calls
            calls += 1
            return [InterfaceType]

        obj_type = GraphQLObjectType("SomeObject", {}, interfaces)
        assert obj_type.interfaces == (InterfaceType,)
        assert calls == 1
        assert obj_type.interfaces == (InterfaceType,)
        assert calls == 1

    def accepts_a_lambda_as_an_object_field_resolver():
        obj_type = GraphQLObjectType(
            "SomeObject",
            {
                "f": GraphQLField(
                    ScalarType, resolve=lambda _obj, _info: {}  # pragma: no cover
                )
            },
        )
        assert obj_type.fields

    def accepts_an_object_type_with_ast_node_and_extension_ast_nodes():
        ast_node = ObjectTypeDefinitionNode()
        extension_ast_nodes = [ObjectTypeExtensionNode()]
        object_type = GraphQLObjectType(
            "SomeObject",
            {"f": GraphQLField(ScalarType)},
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        assert object_type.ast_node is ast_node
        assert object_type.extension_ast_nodes == tuple(extension_ast_nodes)

    def rejects_an_object_type_with_incorrectly_typed_name():
        with raises(TypeError, match="missing .* required .* 'name'"):
            # noinspection PyArgumentList
            GraphQLObjectType()  # type: ignore
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType(None, {})  # type: ignore
        assert str(exc_info.value) == "Must provide name."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLObjectType(42, {})  # type: ignore
        assert str(exc_info.value) == "Expected name to be a string."

    def rejects_an_object_type_with_invalid_name():
        with raises(GraphQLError) as exc_info:
            GraphQLObjectType("", {})
        assert str(exc_info.value) == "Expected name to be a non-empty string."
        with raises(GraphQLError) as exc_info:
            GraphQLObjectType("bad-name", {})
        assert str(exc_info.value) == (
            "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
        )

    def rejects_an_object_type_with_incorrectly_named_fields():
        obj_type = GraphQLObjectType(
            "SomeObject", {"bad-name": GraphQLField(ScalarType)}
        )
        with raises(GraphQLError) as exc_info:
            assert not obj_type.fields
        msg = str(exc_info.value)
        assert msg == "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."

    def rejects_an_object_type_field_function_that_raises_an_error():
        def fields():
            raise RuntimeError("Oops!")

        obj_type = GraphQLObjectType("SomeObject", fields)
        with raises(TypeError) as exc_info:
            assert not obj_type.fields
        assert str(exc_info.value) == "SomeObject fields cannot be resolved. Oops!"

    def rejects_an_object_type_with_incorrectly_named_field_args():
        obj_type = GraphQLObjectType(
            "SomeObject",
            lambda: {
                "badField": GraphQLField(
                    ScalarType, args={"bad-name": GraphQLArgument(ScalarType)}
                )
            },
        )
        with raises(GraphQLError) as exc_info:
            assert not obj_type.fields
        msg = str(exc_info.value)
        assert msg == (
            "SomeObject fields cannot be resolved."
            " Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
        )

    def rejects_object_type_with_interfaces_as_function_that_raises_an_error():
        def interfaces():
            raise RuntimeError("Oops!")

        obj_type = GraphQLObjectType("SomeObject", {}, interfaces=interfaces)
        with raises(TypeError) as exc_info:
            assert not obj_type.interfaces
        assert str(exc_info.value) == "SomeObject interfaces cannot be resolved. Oops!"


def describe_type_system_interfaces():
    def defines_an_interface_type():
        fields = {"f": GraphQLField(ScalarType)}
        interface = GraphQLInterfaceType("AnotherInterface", fields)
        assert interface.name == "AnotherInterface"
        assert interface.fields == fields
        assert interface.fields is not fields
        assert interface.resolve_type is None
        assert interface.extensions == {}
        kwargs = interface.to_kwargs()
        assert kwargs == {
            "name": "AnotherInterface",
            "description": None,
            "fields": fields,
            "interfaces": (),
            "resolve_type": None,
            "extensions": {},
            "ast_node": None,
            "extension_ast_nodes": (),
        }

    def accepts_an_interface_type_defining_resolve_type():
        def resolve_type(_obj, _info, _type):
            pass

        interface = GraphQLInterfaceType(
            "AnotherInterface", {}, resolve_type=resolve_type
        )
        assert interface.resolve_type is resolve_type

    def accepts_an_interface_type_with_output_types_as_fields():
        interface = GraphQLInterfaceType(
            "AnotherInterface", {"someField": ScalarType}  # type: ignore
        )
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
        calls = 0

        def fields():
            nonlocal calls
            calls += 1
            return {"f": GraphQLField(ScalarType)}

        interface = GraphQLInterfaceType("AnotherInterface", fields)
        assert "f" in interface.fields
        assert calls == 1
        assert "f" in interface.fields
        assert calls == 1

    def accepts_an_interface_type_with_a_list_of_interfaces():
        implementing = GraphQLInterfaceType(
            "AnotherInterface", {}, interfaces=[InterfaceType]
        )
        assert implementing.interfaces == (InterfaceType,)

    def accepts_an_interface_type_with_an_interfaces_function():
        implementing = GraphQLInterfaceType(
            "AnotherInterface", {}, interfaces=lambda: [InterfaceType]
        )
        assert implementing.interfaces == (InterfaceType,)

    def thunk_for_interfaces_of_interface_type_is_resolved_only_once():
        calls = 0

        def interfaces():
            nonlocal calls
            calls += 1
            return [InterfaceType]

        implementing = GraphQLInterfaceType(
            "AnotherInterface", {}, interfaces=interfaces
        )
        assert implementing.interfaces == (InterfaceType,)
        assert calls == 1
        assert implementing.interfaces == (InterfaceType,)
        assert calls == 1

    def accepts_an_interface_type_with_ast_node_and_extension_ast_nodes():
        ast_node = InterfaceTypeDefinitionNode()
        extension_ast_nodes = [InterfaceTypeExtensionNode()]
        interface_type = GraphQLInterfaceType(
            "SomeInterface",
            {"f": GraphQLField(ScalarType)},
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        assert interface_type.ast_node is ast_node
        assert interface_type.extension_ast_nodes == tuple(extension_ast_nodes)

    def rejects_an_interface_type_with_unresolvable_fields():
        def fields():
            raise RuntimeError("Oops!")

        interface = GraphQLInterfaceType("SomeInterface", fields)
        with raises(TypeError) as exc_info:
            assert not interface.fields
        assert str(exc_info.value) == "SomeInterface fields cannot be resolved. Oops!"

    def rejects_an_interface_type_with_invalid_name():
        with raises(GraphQLError) as exc_info:
            GraphQLInterfaceType("", {})
        assert str(exc_info.value) == "Expected name to be a non-empty string."
        with raises(GraphQLError) as exc_info:
            GraphQLInterfaceType("bad-name", {})
        assert str(exc_info.value) == (
            "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
        )

    def rejects_an_interface_type_with_unresolvable_interfaces():
        def interfaces():
            raise RuntimeError("Oops!")

        interface = GraphQLInterfaceType("AnotherInterface", {}, interfaces)
        with raises(TypeError) as exc_info:
            assert not interface.interfaces
        assert (
            str(exc_info.value)
            == "AnotherInterface interfaces cannot be resolved. Oops!"
        )


def describe_type_system_unions():
    def accepts_a_union_type_defining_resolve_type():
        assert GraphQLUnionType("SomeUnion", [ObjectType])

    def accepts_a_union_type_with_list_types():
        union_type = GraphQLUnionType("SomeUnion", [ObjectType])
        assert union_type.types == (ObjectType,)

    def accepts_a_union_type_with_function_returning_a_list_of_types():
        union_type = GraphQLUnionType("SomeUnion", lambda: [ObjectType])
        assert union_type.types == (ObjectType,)

    def accepts_a_union_type_without_types():
        with raises(TypeError, match="missing 1 required positional argument: 'types'"):
            # noinspection PyArgumentList
            GraphQLUnionType("SomeUnion")  # type: ignore
        union_type = GraphQLUnionType("SomeUnion", None)  # type: ignore
        assert union_type.types == ()
        union_type = GraphQLUnionType("SomeUnion", [])
        assert union_type.types == ()

    def accepts_a_union_type_with_ast_node_and_extension_ast_nodes():
        ast_node = UnionTypeDefinitionNode()
        extension_ast_nodes = [UnionTypeExtensionNode()]
        union_type = GraphQLUnionType(
            "SomeUnion",
            [ObjectType],
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        assert union_type.ast_node is ast_node
        assert union_type.extension_ast_nodes == tuple(extension_ast_nodes)

    def rejects_a_union_type_with_invalid_name():
        with raises(GraphQLError) as exc_info:
            GraphQLUnionType("", [])
        assert str(exc_info.value) == "Expected name to be a non-empty string."
        with raises(GraphQLError) as exc_info:
            GraphQLUnionType("bad-name", [])
        assert str(exc_info.value) == (
            "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
        )

    def rejects_a_union_type_with_unresolvable_types():
        def types():
            raise RuntimeError("Oops!")

        union_type = GraphQLUnionType("SomeUnion", types)
        with raises(TypeError) as exc_info:
            assert not union_type.types
        assert str(exc_info.value) == "SomeUnion types cannot be resolved. Oops!"


def describe_type_system_enums():
    def defines_an_enum_using_a_dict():
        enum_type = GraphQLEnumType("SomeEnum", {"RED": 1, "BLUE": 2})
        assert enum_type.values == {
            "RED": GraphQLEnumValue(1),
            "BLUE": GraphQLEnumValue(2),
        }

    def defines_an_enum_using_an_enum_value_map():
        red, blue = GraphQLEnumValue(1), GraphQLEnumValue(2)
        enum_type = GraphQLEnumType("SomeEnum", {"RED": red, "BLUE": blue})
        assert enum_type.values == {"RED": red, "BLUE": blue}

    def defines_an_enum_using_a_python_enum():
        colors = Enum("Colors", "RED BLUE")
        enum_type = GraphQLEnumType("SomeEnum", colors)
        assert enum_type.values == {
            "RED": GraphQLEnumValue(1),
            "BLUE": GraphQLEnumValue(2),
        }

    def defines_an_enum_using_values_of_a_python_enum():
        colors = Enum("Colors", "RED BLUE")
        enum_type = GraphQLEnumType("SomeEnum", colors, names_as_values=False)
        assert enum_type.values == {
            "RED": GraphQLEnumValue(1),
            "BLUE": GraphQLEnumValue(2),
        }

    def defines_an_enum_using_names_of_a_python_enum():
        colors = Enum("Colors", "RED BLUE")
        enum_type = GraphQLEnumType("SomeEnum", colors, names_as_values=True)
        assert enum_type.values == {
            "RED": GraphQLEnumValue("RED"),
            "BLUE": GraphQLEnumValue("BLUE"),
        }

    def defines_an_enum_using_members_of_a_python_enum():
        colors = Enum("Colors", "RED BLUE")
        enum_type = GraphQLEnumType("SomeEnum", colors, names_as_values=None)
        assert enum_type.values == {
            "RED": GraphQLEnumValue(colors.RED),
            "BLUE": GraphQLEnumValue(colors.BLUE),
        }

    def defines_an_enum_type_with_a_description():
        description = "nice enum"
        enum_type = GraphQLEnumType(
            "SomeEnum", {}, description=description  # type: ignore
        )
        assert enum_type.description is description
        assert enum_type.to_kwargs()["description"] is description

    def defines_an_enum_type_with_deprecated_value():
        EnumTypeWithDeprecatedValue = GraphQLEnumType(
            name="EnumWithDeprecatedValue",
            values={"foo": GraphQLEnumValue(deprecation_reason="Just because")},
        )

        deprecated_value = EnumTypeWithDeprecatedValue.values["foo"]
        assert deprecated_value == GraphQLEnumValue(deprecation_reason="Just because")
        assert deprecated_value.deprecation_reason == "Just because"
        assert deprecated_value.value is None
        assert deprecated_value.extensions == {}
        assert deprecated_value.ast_node is None

    def defines_an_enum_type_with_a_value_of_none_and_invalid():
        EnumTypeWithNullishValue = GraphQLEnumType(
            name="EnumWithNullishValue",
            values={"NULL": None, "NAN": nan, "NO_CUSTOM_VALUE": Undefined},
        )

        assert list(EnumTypeWithNullishValue.values) == [
            "NULL",
            "NAN",
            "NO_CUSTOM_VALUE",
        ]
        null_value = EnumTypeWithNullishValue.values["NULL"]
        assert null_value.description is None
        assert null_value.value is None
        assert null_value.deprecation_reason is None
        assert null_value.extensions == {}
        assert null_value.ast_node is None
        null_value = EnumTypeWithNullishValue.values["NAN"]
        assert null_value.description is None
        assert isnan(null_value.value)
        assert null_value.deprecation_reason is None
        assert null_value.extensions == {}
        assert null_value.ast_node is None
        no_custom_value = EnumTypeWithNullishValue.values["NO_CUSTOM_VALUE"]
        assert no_custom_value.description is None
        assert no_custom_value.value is Undefined
        assert no_custom_value.deprecation_reason is None
        assert no_custom_value.extensions == {}
        assert no_custom_value.ast_node is None

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
        with raises(GraphQLError) as exc_info:
            enum_type.serialize(None)
        msg = exc_info.value.message
        assert msg == "Enum 'SomeEnum' cannot represent value: None"
        with raises(GraphQLError) as exc_info:
            enum_type.serialize(Undefined)
        msg = exc_info.value.message
        assert msg == "Enum 'SomeEnum' cannot represent value: Undefined"
        assert enum_type.serialize("fooValue") == "FOO"
        with raises(GraphQLError) as exc_info:
            enum_type.serialize("FOO")
        msg = exc_info.value.message
        assert msg == "Enum 'SomeEnum' cannot represent value: 'FOO'"
        assert enum_type.serialize(["barValue"]) == "BAR"
        with raises(GraphQLError) as exc_info:
            enum_type.serialize("BAR")
        msg = exc_info.value.message
        assert msg == "Enum 'SomeEnum' cannot represent value: 'BAR'"
        assert enum_type.serialize("BAZ") == "BAZ"
        with raises(GraphQLError) as exc_info:
            enum_type.serialize("bazValue")
        msg = exc_info.value.message
        assert msg == "Enum 'SomeEnum' cannot represent value: 'bazValue'"
        with raises(GraphQLError) as exc_info:
            enum_type.serialize(["bazValue"])
        msg = exc_info.value.message
        assert msg == "Enum 'SomeEnum' cannot represent value: ['bazValue']"

    def use_first_name_for_duplicate_values():
        enum_type = GraphQLEnumType("SomeEnum", {"FOO": "fooValue", "BAR": "fooValue"})
        assert enum_type.values["FOO"].value == "fooValue"
        assert enum_type.values["BAR"].value == "fooValue"
        assert enum_type.serialize("fooValue") == "FOO"

    def parses_an_enum():
        enum_type = GraphQLEnumType(
            "SomeEnum", {"FOO": "fooValue", "BAR": ["barValue"], "BAZ": None}
        )
        assert enum_type.parse_value("FOO") == "fooValue"
        with raises(GraphQLError) as exc_info:
            enum_type.parse_value("fooValue")
        msg = exc_info.value.message
        assert msg == "Value 'fooValue' does not exist in 'SomeEnum' enum."
        assert enum_type.parse_value("BAR") == ["barValue"]
        with raises(GraphQLError) as exc_info:
            # noinspection PyTypeChecker
            enum_type.parse_value(["barValue"])  # type: ignore
        msg = exc_info.value.message
        assert msg == "Enum 'SomeEnum' cannot represent non-string value: ['barValue']."
        assert enum_type.parse_value("BAZ") is None
        assert enum_type.parse_literal(EnumValueNode(value="FOO")) == "fooValue"
        with raises(GraphQLError) as exc_info:
            enum_type.parse_literal(StringValueNode(value="FOO"))
        assert exc_info.value.message == (
            "Enum 'SomeEnum' cannot represent non-enum value: \"FOO\"."
            " Did you mean the enum value 'FOO'?"
        )
        with raises(GraphQLError) as exc_info:
            enum_type.parse_literal(EnumValueNode(value="fooValue"))
        msg = exc_info.value.message
        assert msg == "Value 'fooValue' does not exist in 'SomeEnum' enum."
        assert enum_type.parse_literal(EnumValueNode(value="BAR")) == ["barValue"]
        with raises(GraphQLError) as exc_info:
            enum_type.parse_literal(StringValueNode(value="BAR"))
        assert exc_info.value.message == (
            "Enum 'SomeEnum' cannot represent non-enum value: \"BAR\"."
            " Did you mean the enum value 'BAR' or 'BAZ'?"
        )
        assert enum_type.parse_literal(EnumValueNode(value="BAZ")) is None
        with raises(GraphQLError) as exc_info:
            enum_type.parse_literal(StringValueNode(value="BAZ"))
        assert exc_info.value.message == (
            "Enum 'SomeEnum' cannot represent non-enum value: \"BAZ\"."
            " Did you mean the enum value 'BAZ' or 'BAR'?"
        )

    def accepts_an_enum_type_with_ast_node_and_extension_ast_nodes():
        ast_node = EnumTypeDefinitionNode()
        extension_ast_nodes = [EnumTypeExtensionNode()]
        enum_type = GraphQLEnumType(
            "SomeEnum",
            {},  # type: ignore
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        assert enum_type.ast_node is ast_node
        assert enum_type.extension_ast_nodes == tuple(extension_ast_nodes)

    def rejects_an_enum_type_with_incorrectly_typed_name():
        with raises(TypeError, match="missing .* required .* 'name'"):
            # noinspection PyArgumentList
            GraphQLEnumType()  # type: ignore
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType(None, {})  # type: ignore
        assert str(exc_info.value) == "Must provide name."
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType(42, {})  # type: ignore
        assert str(exc_info.value) == "Expected name to be a string."

    def rejects_an_enum_type_with_invalid_name():
        values: Dict[str, GraphQLEnumValue] = {}
        with raises(GraphQLError) as exc_info:
            GraphQLEnumType("", values)
        assert str(exc_info.value) == "Expected name to be a non-empty string."
        with raises(GraphQLError) as exc_info:
            GraphQLEnumType("bad-name", values)
        assert str(exc_info.value) == (
            "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
        )

    def rejects_an_enum_type_with_incorrectly_named_values():
        with raises(GraphQLError) as exc_info:
            GraphQLEnumType("SomeEnum", {"bad-name": GraphQLField(ScalarType)})
        msg = str(exc_info.value)
        assert msg == "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."

    def rejects_an_enum_type_without_values():
        with raises(TypeError, match="missing .* required .* 'values'"):
            # noinspection PyArgumentList
            GraphQLEnumType("SomeEnum")  # type: ignore
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", values=None)  # type: ignore
        assert str(exc_info.value) == (
            "SomeEnum values must be an Enum or a mapping with value names as keys."
        )

    def rejects_an_enum_type_with_incorrectly_typed_values():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLEnumType("SomeEnum", [{"FOO": 10}])  # type: ignore
        assert str(exc_info.value) == (
            "SomeEnum values must be an Enum or a mapping with value names as keys."
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

    def accepts_an_input_object_type_with_ast_node_and_extension_ast_nodes():
        ast_node = InputObjectTypeDefinitionNode()
        extension_ast_nodes = [InputObjectTypeExtensionNode()]
        input_obj_type = GraphQLInputObjectType(
            "SomeInputObject",
            {},
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        assert input_obj_type.ast_node is ast_node
        assert input_obj_type.extension_ast_nodes == tuple(extension_ast_nodes)

    def describe_input_objects_must_have_fields():
        def accepts_an_input_object_type_with_fields():
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": GraphQLInputField(ScalarType)}
            )
            assert list(input_obj_type.fields) == ["f"]
            input_field = input_obj_type.fields["f"]
            assert isinstance(input_field, GraphQLInputField)
            assert input_field.description is None
            assert input_field.type is ScalarType
            assert input_field.default_value is Undefined
            assert input_field.deprecation_reason is None
            assert input_field.extensions == {}
            assert input_field.ast_node is None
            assert input_field.out_name is None

        def accepts_an_input_object_type_with_input_type_as_field():
            # this is a shortcut syntax for simple input fields
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"f": ScalarType}  # type: ignore
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
            assert input_field.description is None
            assert input_field.type is ScalarType
            assert input_field.default_value is Undefined
            assert input_field.deprecation_reason is None
            assert input_field.extensions == {}
            assert input_field.ast_node is None
            assert input_field.out_name is None

        def rejects_an_input_object_type_with_incorrectly_typed_name():
            with raises(TypeError, match="missing .* required .* 'name'"):
                # noinspection PyArgumentList
                GraphQLInputObjectType()  # type: ignore
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLInputObjectType(None, {})  # type: ignore
            assert str(exc_info.value) == "Must provide name."
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLInputObjectType(42, {})  # type: ignore
            assert str(exc_info.value) == "Expected name to be a string."

        def rejects_an_input_object_type_with_invalid_name():
            with raises(GraphQLError) as exc_info:
                GraphQLInputObjectType("", {})
            assert str(exc_info.value) == "Expected name to be a non-empty string."
            with raises(GraphQLError) as exc_info:
                GraphQLInputObjectType("bad-name", {})
            assert str(exc_info.value) == (
                "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
            )

        def rejects_an_input_object_type_with_incorrectly_named_fields():
            input_obj_type = GraphQLInputObjectType(
                "SomeInputObject", {"bad-name": GraphQLInputField(ScalarType)}
            )
            with raises(GraphQLError) as exc_info:
                assert not input_obj_type.fields
            msg = str(exc_info.value)
            assert msg == (
                "Names must only contain [_a-zA-Z0-9] but 'bad-name' does not."
            )

        def rejects_an_input_object_type_with_unresolvable_fields():
            def fields():
                raise RuntimeError("Oops!")

            input_obj_type = GraphQLInputObjectType("SomeInputObject", fields)
            with raises(TypeError) as exc_info:
                assert not input_obj_type.fields
            assert str(exc_info.value) == (
                "SomeInputObject fields cannot be resolved. Oops!"
            )

    def describe_input_objects_fields_must_not_have_resolvers():
        def rejects_an_input_object_type_with_resolvers():
            def resolve():
                pass

            with raises(
                TypeError, match="got an unexpected keyword argument 'resolve'"
            ):
                # noinspection PyArgumentList
                GraphQLInputObjectType(
                    "SomeInputObject",
                    {
                        "f": GraphQLInputField(  # type: ignore
                            ScalarType,
                            resolve=resolve,
                        )
                    },
                )

        def rejects_an_input_object_type_with_resolver_constant():
            with raises(
                TypeError, match="got an unexpected keyword argument 'resolve'"
            ):
                # noinspection PyArgumentList
                GraphQLInputObjectType(
                    "SomeInputObject",
                    {"f": GraphQLInputField(ScalarType, resolve={})},  # type: ignore
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
            GraphQLArgument()  # type: ignore


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
            GraphQLInputField()  # type: ignore

    def deprecation_reason_is_preserved_on_fields():
        input_obj_type = GraphQLInputObjectType(
            "someInputObject",
            {
                "deprecatedField": GraphQLInputField(
                    ScalarType, deprecation_reason="not used anymore"
                )
            },
        )
        deprecated_field = input_obj_type.fields["deprecatedField"]
        assert (
            input_obj_type.to_kwargs()["fields"]["deprecatedField"] is deprecated_field
        )
        deprecation_reason = deprecated_field.deprecation_reason
        assert deprecation_reason == "not used anymore"
        assert deprecated_field.to_kwargs()["deprecation_reason"] is deprecation_reason


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
        assert str(NonNullListOfScalars) == "[Scalar]!"
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


def describe_type_system_introspection_types():
    def cannot_redefine_introspection_types():
        for name, introspection_type in introspection_types.items():
            assert introspection_type.name == name
            with raises(TypeError, match=f"Redefinition of reserved type '{name}'"):
                introspection_type.__class__(**introspection_type.to_kwargs())
