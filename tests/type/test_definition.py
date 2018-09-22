from typing import cast, Dict

from pytest import fixture, mark, raises

from graphql.error import INVALID
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLField,
    GraphQLInt,
    GraphQLString,
    GraphQLObjectType,
    GraphQLList,
    GraphQLScalarType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLInputObjectType,
    GraphQLSchema,
    GraphQLOutputType,
    GraphQLInputField,
    GraphQLNonNull,
    is_input_type,
    is_output_type,
)


BlogImage = GraphQLObjectType(
    "Image",
    {
        "url": GraphQLField(GraphQLString),
        "width": GraphQLField(GraphQLInt),
        "height": GraphQLField(GraphQLInt),
    },
)


BlogAuthor = GraphQLObjectType(
    "Author",
    lambda: {
        "id": GraphQLField(GraphQLString),
        "name": GraphQLField(GraphQLString),
        "pic": GraphQLField(
            BlogImage,
            args={
                "width": GraphQLArgument(GraphQLInt),
                "height": GraphQLArgument(GraphQLInt),
            },
        ),
        "recentArticle": GraphQLField(BlogArticle),
    },
)


BlogArticle = GraphQLObjectType(
    "Article",
    lambda: {
        "id": GraphQLField(GraphQLString),
        "isPublished": GraphQLField(GraphQLBoolean),
        "author": GraphQLField(BlogAuthor),
        "title": GraphQLField(GraphQLString),
        "body": GraphQLField(GraphQLString),
    },
)


BlogQuery = GraphQLObjectType(
    "Query",
    {
        "article": GraphQLField(
            BlogArticle, args={"id": GraphQLArgument(GraphQLString)}
        ),
        "feed": GraphQLField(GraphQLList(BlogArticle)),
    },
)


BlogMutation = GraphQLObjectType(
    "Mutation", {"writeArticle": GraphQLField(BlogArticle)}
)


BlogSubscription = GraphQLObjectType(
    "Subscription",
    {
        "articleSubscribe": GraphQLField(
            args={"id": GraphQLArgument(GraphQLString)}, type_=BlogArticle
        )
    },
)

ObjectType = GraphQLObjectType("Object", {})
InterfaceType = GraphQLInterfaceType("Interface")
UnionType = GraphQLUnionType("Union", [ObjectType], resolve_type=lambda: None)
EnumType = GraphQLEnumType("Enum", {"foo": GraphQLEnumValue()})
InputObjectType = GraphQLInputObjectType("InputObject", {})
ScalarType = GraphQLScalarType(
    "Scalar",
    serialize=lambda: None,
    parse_value=lambda: None,
    parse_literal=lambda: None,
)


def schema_with_field_type(type_: GraphQLOutputType) -> GraphQLSchema:
    return GraphQLSchema(
        query=GraphQLObjectType("Query", {"field": GraphQLField(type_)}), types=[type_]
    )


def describe_type_system_example():
    def defines_a_query_only_schema():
        BlogSchema = GraphQLSchema(BlogQuery)

        assert BlogSchema.query_type == BlogQuery

        article_field = BlogQuery.fields["article"]
        assert article_field.type == BlogArticle
        assert article_field.type.name == "Article"

        article_field_type = article_field.type
        assert isinstance(article_field_type, GraphQLObjectType)

        title_field = article_field_type.fields["title"]
        assert title_field.type == GraphQLString
        assert title_field.type.name == "String"

        author_field = article_field_type.fields["author"]

        author_field_type = author_field.type
        assert isinstance(author_field_type, GraphQLObjectType)
        recent_article_field = author_field_type.fields["recentArticle"]

        assert recent_article_field.type == BlogArticle

        feed_field = BlogQuery.fields["feed"]
        assert feed_field.type.of_type == BlogArticle

    def defines_a_mutation_schema():
        BlogSchema = GraphQLSchema(query=BlogQuery, mutation=BlogMutation)

        assert BlogSchema.mutation_type == BlogMutation

        write_mutation = BlogMutation.fields["writeArticle"]
        assert write_mutation.type == BlogArticle
        assert write_mutation.type.name == "Article"

    def defines_a_subscription_schema():
        BlogSchema = GraphQLSchema(query=BlogQuery, subscription=BlogSubscription)

        assert BlogSchema.subscription_type == BlogSubscription

        subscription = BlogSubscription.fields["articleSubscribe"]
        assert subscription.type == BlogArticle
        assert subscription.type.name == "Article"

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

    def includes_nested_input_objects_in_the_map():
        NestedInputObject = GraphQLInputObjectType(
            "NestedInputObject", {"value": GraphQLInputField(GraphQLString)}
        )
        SomeInputObject = GraphQLInputObjectType(
            "SomeInputObject", {"nested": GraphQLInputField(NestedInputObject)}
        )
        SomeMutation = GraphQLObjectType(
            "SomeMutation",
            {
                "mutateSomething": GraphQLField(
                    BlogArticle, {"input": GraphQLArgument(SomeInputObject)}
                )
            },
        )
        SomeSubscription = GraphQLObjectType(
            "SomeSubscription",
            {
                "subscribeToSomething": GraphQLField(
                    BlogArticle, {"input": GraphQLArgument(SomeInputObject)}
                )
            },
        )
        schema = GraphQLSchema(
            query=BlogQuery, mutation=SomeMutation, subscription=SomeSubscription
        )
        assert schema.type_map["NestedInputObject"] is NestedInputObject

    def includes_interface_possible_types_in_the_type_map():
        SomeInterface = GraphQLInterfaceType(
            "SomeInterface", {"f": GraphQLField(GraphQLInt)}
        )
        SomeSubtype = GraphQLObjectType(
            "SomeSubtype", {"f": GraphQLField(GraphQLInt)}, interfaces=[SomeInterface]
        )
        schema = GraphQLSchema(
            query=GraphQLObjectType("Query", {"iface": GraphQLField(SomeInterface)}),
            types=[SomeSubtype],
        )
        assert schema.type_map["SomeSubtype"] is SomeSubtype

    def includes_interfaces_thunk_subtypes_in_the_type_map():
        SomeInterface = GraphQLInterfaceType(
            "SomeInterface", {"f": GraphQLField(GraphQLInt)}
        )
        SomeSubtype = GraphQLObjectType(
            "SomeSubtype",
            {"f": GraphQLField(GraphQLInt)},
            interfaces=lambda: [SomeInterface],
        )
        schema = GraphQLSchema(
            query=GraphQLObjectType("Query", {"iface": GraphQLField(SomeInterface)}),
            types=[SomeSubtype],
        )
        assert schema.type_map["SomeSubtype"] is SomeSubtype

    def stringifies_simple_types():
        assert str(GraphQLInt) == "Int"
        assert str(BlogArticle) == "Article"
        assert str(InterfaceType) == "Interface"
        assert str(UnionType) == "Union"
        assert str(EnumType) == "Enum"
        assert str(InputObjectType) == "InputObject"
        assert str(GraphQLNonNull(GraphQLInt)) == "Int!"
        assert str(GraphQLList(GraphQLInt)) == "[Int]"
        assert str(GraphQLNonNull(GraphQLList(GraphQLInt))) == "[Int]!"
        assert str(GraphQLList(GraphQLNonNull(GraphQLInt))) == "[Int!]"
        assert str(GraphQLList(GraphQLList(GraphQLInt))) == "[[Int]]"

    def identifies_input_types():
        expected = (
            (GraphQLInt, True),
            (ObjectType, False),
            (InterfaceType, False),
            (UnionType, False),
            (EnumType, True),
            (InputObjectType, True),
        )

        for type_, answer in expected:
            assert is_input_type(type_) is answer
            assert is_input_type(GraphQLList(type_)) is answer
            assert is_input_type(GraphQLNonNull(type_)) is answer

    def identifies_output_types():
        expected = (
            (GraphQLInt, True),
            (ObjectType, True),
            (InterfaceType, True),
            (UnionType, True),
            (EnumType, True),
            (InputObjectType, False),
        )

        for type_, answer in expected:
            assert is_output_type(type_) is answer
            assert is_output_type(GraphQLList(type_)) is answer
            assert is_output_type(GraphQLNonNull(type_)) is answer

    def prohibits_nesting_nonnull_inside_nonnull():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLNonNull(GraphQLNonNull(GraphQLInt))
        msg = str(exc_info.value)
        assert msg == (
            "Can only create NonNull of a Nullable GraphQLType but got: Int!."
        )

    def allows_a_thunk_for_union_member_types():
        union = GraphQLUnionType("ThunkUnion", lambda: [ObjectType])

        types = union.types
        assert len(types) == 1
        assert types[0] is ObjectType

    def does_not_mutate_passed_field_definitions():
        fields = {
            "field1": GraphQLField(GraphQLString),
            "field2": GraphQLField(
                GraphQLString, args={"id": GraphQLArgument(GraphQLString)}
            ),
        }

        TestObject1 = GraphQLObjectType("Test1", fields)
        TestObject2 = GraphQLObjectType("Test2", fields)

        assert TestObject1.fields == TestObject2.fields
        assert fields == {
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


def describe_field_config_must_be_a_dict():
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

    def accepts_an_object_type_with_output_type_as_field():
        # this is a shortcut syntax for simple fields
        obj_type = GraphQLObjectType("SomeObject", {"f": GraphQLString})
        field = obj_type.fields["f"]
        assert isinstance(field, GraphQLField)
        assert field.type is GraphQLString

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


def describe_field_args_must_be_a_dict():
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

    def does_not_accept_is_deprecated_as_argument():
        kwargs = dict(is_deprecated=True)
        with raises(TypeError) as exc_info:
            GraphQLObjectType(
                "OldObject", {"field": GraphQLField(GraphQLString, **kwargs)}
            )
        msg = str(exc_info.value)
        assert "got an unexpected keyword argument 'is_deprecated'" in msg


def describe_object_interfaces_must_be_a_sequence():
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


def describe_type_system_object_fields_must_have_valid_resolve_values():
    @fixture
    def schema_with_object_with_field_resolver(resolve_value):
        BadResolverType = GraphQLObjectType(
            "BadResolver",
            {"bad_field": GraphQLField(GraphQLString, resolve=resolve_value)},
        )
        return GraphQLSchema(
            GraphQLObjectType("Query", {"f": GraphQLField(BadResolverType)})
        )

    def accepts_a_lambda_as_an_object_field_resolver():
        schema_with_object_with_field_resolver(lambda _obj, _info: {})

    def rejects_an_empty_object_field_resolver():
        with raises(TypeError) as exc_info:
            schema_with_object_with_field_resolver({})
        msg = str(exc_info.value)
        assert msg == "Field resolver must be a function if provided,  but got: {}."

    def rejects_a_constant_scalar_value_resolver():
        with raises(TypeError) as exc_info:
            schema_with_object_with_field_resolver(0)
        msg = str(exc_info.value)
        assert msg == "Field resolver must be a function if provided,  but got: 0."


def describe_type_system_interface_types_must_be_resolvable():
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


def describe_type_system_union_types_must_be_resolvable():

    ObjectWithIsTypeOf = GraphQLObjectType(
        "ObjectWithIsTypeOf", {"f": GraphQLField(GraphQLString)}
    )

    def accepts_a_union_type_defining_resolve_type():
        schema_with_field_type(GraphQLUnionType("SomeUnion", [ObjectType]))

    def accepts_a_union_of_object_types_defining_is_type_of():
        schema_with_field_type(GraphQLUnionType("SomeUnion", [ObjectWithIsTypeOf]))

    def rejects_an_interface_type_with_an_incorrect_type_for_resolve_type():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            schema_with_field_type(
                GraphQLUnionType("SomeUnion", [ObjectWithIsTypeOf], resolve_type={})
            )
        msg = str(exc_info.value)
        assert msg == (
            "SomeUnion must provide 'resolve_type' as a function, but got: {}."
        )


def describe_type_system_scalar_types_must_be_serializable():
    def accepts_a_scalar_type_defining_serialize():
        schema_with_field_type(GraphQLScalarType("SomeScalar", lambda: None))

    def rejects_a_scalar_type_not_defining_serialize():
        with raises(TypeError) as exc_info:
            # noinspection PyArgumentList
            schema_with_field_type(GraphQLScalarType("SomeScalar"))
        msg = str(exc_info.value)
        assert "missing 1 required positional argument: 'serialize'" in msg
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

    def accepts_a_scalar_type_defining_parse_value_and_parse_literal():
        schema_with_field_type(
            GraphQLScalarType(
                "SomeScalar",
                serialize=lambda: None,
                parse_value=lambda: None,
                parse_literal=lambda: None,
            )
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


def describe_type_system_object_types_must_be_assertable():
    def accepts_an_object_type_with_an_is_type_of_function():
        schema_with_field_type(
            GraphQLObjectType("AnotherObject", {"f": GraphQLField(GraphQLString)})
        )

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


def describe_union_types_must_be_list():
    def accepts_a_union_type_with_list_types():
        schema_with_field_type(GraphQLUnionType("SomeUnion", [ObjectType]))

    def accepts_a_union_type_with_function_returning_a_list_of_types():
        schema_with_field_type(GraphQLUnionType("SomeUnion", lambda: [ObjectType]))

    def rejects_a_union_type_without_types():
        with raises(TypeError) as exc_info:
            # noinspection PyArgumentList
            schema_with_field_type(GraphQLUnionType("SomeUnion"))
        msg = str(exc_info.value)
        assert "missing 1 required positional argument: 'types'" in msg
        schema_with_field_type(GraphQLUnionType("SomeUnion", None))

    def rejects_a_union_type_with_incorrectly_typed_types():
        with raises(TypeError) as exc_info:
            schema_with_field_type(GraphQLUnionType("SomeUnion", {"type": ObjectType}))
        msg = str(exc_info.value)
        assert msg == (
            "SomeUnion types must be a list/tuple"
            " or a function which returns a list/tuple."
        )


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
        input_obj_type = GraphQLInputObjectType("SomeInputObject", {"f": GraphQLString})
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
        with raises(TypeError) as exc_info:
            # noinspection PyArgumentList
            GraphQLInputObjectType(
                "SomeInputObject",
                {"f": GraphQLInputField(GraphQLString, resolve=lambda: 0)},
            )
        msg = str(exc_info.value)
        assert "got an unexpected keyword argument 'resolve'" in msg
        input_obj_type = GraphQLInputObjectType(
            "SomeInputObject", {"f": GraphQLField(GraphQLString, resolve=lambda: 0)}
        )
        with raises(TypeError) as exc_info:
            if input_obj_type.fields:
                pass
        msg = str(exc_info.value)
        assert msg == (
            "SomeInputObject fields must be GraphQLInputField or input type objects."
        )

    def rejects_an_input_object_type_with_resolver_constant():
        with raises(TypeError) as exc_info:
            # noinspection PyArgumentList
            GraphQLInputObjectType(
                "SomeInputObject", {"f": GraphQLInputField(GraphQLString, resolve={})}
            )
        msg = str(exc_info.value)
        assert "got an unexpected keyword argument 'resolve'" in msg


def describe_type_system_enum_types_must_be_well_defined():
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

    def does_not_allow_is_deprecated():
        with raises(TypeError) as exc_info:
            # noinspection PyArgumentList
            GraphQLEnumType("SomeEnum", {"FOO": GraphQLEnumValue(is_deprecated=True)})
        msg = str(exc_info.value)
        assert "got an unexpected keyword argument 'is_deprecated'" in msg


def describe_type_system_list_must_accept_only_types():

    types = [
        GraphQLString,
        ScalarType,
        ObjectType,
        UnionType,
        InterfaceType,
        EnumType,
        InputObjectType,
        GraphQLList(GraphQLString),
        GraphQLNonNull(GraphQLString),
    ]

    not_types = [{}, dict, str, object, None]

    @mark.parametrize("type_", types)
    def accepts_a_type_as_item_type_of_list(type_):
        assert GraphQLList(type_)

    @mark.parametrize("type_", not_types)
    def rejects_a_non_type_as_item_type_of_list(type_):
        with raises(TypeError) as exc_info:
            assert GraphQLList(type_)
        msg = str(exc_info.value)
        assert msg == (
            "Can only create a wrapper for a GraphQLType," f" but got: {type_}."
        )


def describe_type_system_non_null_must_only_accept_non_nullable_types():

    nullable_types = [
        GraphQLString,
        ScalarType,
        ObjectType,
        UnionType,
        InterfaceType,
        EnumType,
        InputObjectType,
        GraphQLList(GraphQLString),
        GraphQLList(GraphQLNonNull(GraphQLString)),
    ]

    not_nullable_types = [GraphQLNonNull(GraphQLString), {}, dict, str, object, None]

    @mark.parametrize("type_", nullable_types)
    def accepts_a_type_as_nullable_type_of_non_null(type_):
        assert GraphQLNonNull(type_)

    @mark.parametrize("type_", not_nullable_types)
    def rejects_a_non_type_as_nullable_type_of_non_null(type_):
        with raises(TypeError) as exc_info:
            assert GraphQLNonNull(type_)
        msg = str(exc_info.value)
        assert (
            msg
            == (
                "Can only create NonNull of a Nullable GraphQLType"
                f" but got: {type_}."
            )
            if isinstance(type_, GraphQLNonNull)
            else "Can only create a wrapper for a GraphQLType," f" but got: {type_}."
        )


def describe_type_system_a_schema_must_contain_uniquely_named_types():
    def rejects_a_schema_which_redefines_a_built_in_type():
        FakeString = GraphQLScalarType("String", serialize=lambda: None)

        QueryType = GraphQLObjectType(
            "Query",
            {"normal": GraphQLField(GraphQLString), "fake": GraphQLField(FakeString)},
        )

        with raises(TypeError) as exc_info:
            GraphQLSchema(QueryType)
        msg = str(exc_info.value)
        assert msg == (
            "Schema must contain unique named types"
            f" but contains multiple types named 'String'."
        )

    def rejects_a_schema_which_defines_an_object_twice():
        A = GraphQLObjectType("SameName", {"f": GraphQLField(GraphQLString)})
        B = GraphQLObjectType("SameName", {"f": GraphQLField(GraphQLString)})

        QueryType = GraphQLObjectType("Query", {"a": A, "b": B})

        with raises(TypeError) as exc_info:
            GraphQLSchema(QueryType)
        msg = str(exc_info.value)
        assert msg == (
            "Schema must contain unique named types"
            f" but contains multiple types named 'SameName'."
        )

    def rejects_a_schema_with_same_named_objects_implementing_an_interface():
        AnotherInterface = GraphQLInterfaceType(
            "AnotherInterface", {"f": GraphQLField(GraphQLString)}
        )

        FirstBadObject = GraphQLObjectType(
            "BadObject",
            {"f": GraphQLField(GraphQLString)},
            interfaces=[AnotherInterface],
        )

        SecondBadObject = GraphQLObjectType(
            "BadObject",
            {"f": GraphQLField(GraphQLString)},
            interfaces=[AnotherInterface],
        )

        QueryType = GraphQLObjectType(
            "Query", {"iface": GraphQLField(AnotherInterface)}
        )

        with raises(TypeError) as exc_info:
            GraphQLSchema(QueryType, types=[FirstBadObject, SecondBadObject])
        msg = str(exc_info.value)
        assert msg == (
            "Schema must contain unique named types"
            f" but contains multiple types named 'BadObject'."
        )
