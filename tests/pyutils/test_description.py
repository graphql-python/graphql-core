from contextlib import contextmanager
from typing import cast

from pytest import raises  # type: ignore

from graphql import graphql_sync
from graphql.type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLObjectType,
    GraphQLNamedType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.pyutils import (
    Description,
    is_description,
    register_description,
    unregister_description,
)
from graphql.utilities import get_introspection_query


class LazyString:
    def __init__(self, text: object):
        self.text = text

    def __str__(self) -> str:
        return str(self.text)


lazy_string = cast(str, LazyString("Why am I so lazy?"))


@contextmanager
def registered(base: type):
    register_description(base)
    try:
        yield None
    finally:
        unregister_description(LazyString)


def describe_description():
    def by_default_strings_are_accepted():
        is_description("")
        is_description("text")

    def by_default_non_strings_are_not_accepted():
        assert not is_description(None)
        assert not is_description(b"bytes")
        assert not is_description(0)
        assert not is_description(42)
        assert not is_description(("tuple",))
        assert not is_description(["list"])

    def after_registration_lazy_strings_are_accepted():
        with registered(LazyString):
            assert is_description("not lazy")
            assert is_description(lazy_string)
            assert not is_description(42)

    def can_register_and_unregister():
        try:
            assert Description.bases is str
            register_description(str)
            assert Description.bases is str
            register_description(int)
            assert Description.bases == (str, int)
            register_description(int)
            assert Description.bases == (str, int)
            register_description(float)
            assert Description.bases == (str, int, float)
            unregister_description(int)
            assert Description.bases == (str, float)
            unregister_description(float)
            assert Description.bases is str
            unregister_description(str)
            assert Description.bases is object
            register_description(str)
            assert Description.bases is str
            register_description(object)
            assert Description.bases is object
            Description.bases = (str,)
            unregister_description(str)
            assert Description.bases is object
            unregister_description(str)
            assert Description.bases is object
        finally:
            Description.bases = str

    def can_only_register_types():
        with raises(TypeError, match="Only types can be registered\\."):
            # noinspection PyTypeChecker
            register_description("foo")  # type: ignore

    def can_only_unregister_types():
        with raises(TypeError, match="Only types can be unregistered\\."):
            # noinspection PyTypeChecker
            unregister_description("foo")  # type: ignore

    def describe_graphql_types():
        def graphql_named_type():
            named_type = GraphQLNamedType(name="Foo", description="not lazy")
            assert named_type.name == "Foo"
            assert named_type.description == "not lazy"
            with raises(TypeError, match="The name must be a string\\."):
                GraphQLNamedType(name=lazy_string)
            with raises(TypeError, match="The description must be a string\\."):
                GraphQLNamedType(name="Foo", description=lazy_string)
            with registered(LazyString):
                named_type = GraphQLNamedType(name="Foo", description=lazy_string)
                assert named_type.description is lazy_string
                assert str(named_type.description).endswith("lazy?")
                with raises(TypeError, match="The name must be a string\\."):
                    GraphQLNamedType(name=lazy_string)

        def graphql_field():
            field = GraphQLField(GraphQLString, description="not lazy")
            assert field.description == "not lazy"
            field = GraphQLField(GraphQLString, deprecation_reason="not lazy")
            assert field.deprecation_reason == "not lazy"
            with raises(TypeError, match="The description must be a string\\."):
                GraphQLField(GraphQLString, description=lazy_string)
            with raises(TypeError, match="The deprecation reason must be a string\\."):
                GraphQLField(GraphQLString, deprecation_reason=lazy_string)
            with registered(LazyString):
                field = GraphQLField(
                    GraphQLString,
                    description=lazy_string,
                    deprecation_reason=lazy_string,
                )
                assert field.description is lazy_string
                assert str(field.description).endswith("lazy?")
                assert field.deprecation_reason is lazy_string
                assert str(field.deprecation_reason).endswith("lazy?")

        def graphql_argument():
            arg = GraphQLArgument(GraphQLString, description="not lazy")
            assert arg.description == "not lazy"
            with raises(TypeError, match="Argument description must be a string\\."):
                GraphQLArgument(GraphQLString, description=lazy_string)
            with registered(LazyString):
                arg = GraphQLArgument(GraphQLString, description=lazy_string)
                assert arg.description is lazy_string
                assert str(arg.description).endswith("lazy?")

        def graphql_enum_value():
            value = GraphQLEnumValue(description="not lazy")
            assert value.description == "not lazy"
            value = GraphQLEnumValue(deprecation_reason="not lazy")
            assert value.deprecation_reason == "not lazy"
            with raises(
                TypeError, match="The description of the enum value must be a string\\."
            ):
                GraphQLEnumValue(description=lazy_string)
            with raises(
                TypeError,
                match="The deprecation reason for the enum value must be a string\\.",
            ):
                GraphQLEnumValue(deprecation_reason=lazy_string)
            with registered(LazyString):
                value = GraphQLEnumValue(
                    description=lazy_string, deprecation_reason=lazy_string
                )
                assert value.description is lazy_string
                assert str(value.description).endswith("lazy?")
                assert value.deprecation_reason is lazy_string
                assert str(value.deprecation_reason).endswith("lazy?")

        def graphql_input_field():
            field = GraphQLInputField(GraphQLString, description="not lazy")
            assert field.description == "not lazy"
            with raises(TypeError, match="Input field description must be a string\\."):
                GraphQLInputField(GraphQLString, description=lazy_string)
            with registered(LazyString):
                field = GraphQLInputField(GraphQLString, description=lazy_string)
                assert field.description is lazy_string
                assert str(field.description).endswith("lazy?")

        def graphql_directive():
            directive = GraphQLDirective("Foo", [], description="not lazy")
            assert directive.name == "Foo"
            assert directive.description == "not lazy"
            with raises(TypeError, match="The directive name must be a string\\."):
                GraphQLDirective(lazy_string, [])
            with raises(TypeError, match="Foo description must be a string\\."):
                GraphQLDirective("Foo", [], description=lazy_string)
            with registered(LazyString):
                directive = GraphQLDirective("Foo", [], description=lazy_string)
                assert directive.description is lazy_string
                assert str(directive.description).endswith("lazy?")
                with raises(TypeError, match="The directive name must be a string\\."):
                    GraphQLDirective(lazy_string, [])

    def introspection():
        class Lazy:
            def __init__(self, text: str):
                self.text = text
                self.evaluated = False

            def __str__(self) -> str:
                self.evaluated = True
                return self.text

        description = Lazy("a lazy description")
        deprecation_reason = Lazy("a lazy reason")

        with registered(Lazy):
            field = GraphQLField(
                GraphQLString,
                description=cast(str, description),
                deprecation_reason=cast(str, deprecation_reason),
            )

        schema = GraphQLSchema(GraphQLObjectType("Query", {"lazyField": field}))

        query = get_introspection_query(descriptions=True)
        assert not description.evaluated
        assert not deprecation_reason.evaluated
        result = graphql_sync(schema, query)
        assert description.evaluated
        assert deprecation_reason.evaluated
        assert result.data
        introspected_query = result.data["__schema"]["types"][0]
        assert introspected_query["name"] == "Query"
        introspected_field = introspected_query["fields"][0]
        assert introspected_field["name"] == "lazyField"
        assert introspected_field["description"] == "a lazy description"
        assert introspected_field["deprecationReason"] == "a lazy reason"
