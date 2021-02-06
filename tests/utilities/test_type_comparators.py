from graphql.type import (
    GraphQLField,
    GraphQLFloat,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
)
from graphql.utilities import is_equal_type, is_type_sub_type_of


def describe_type_comparators():
    def describe_is_equal_type():
        def same_references_are_equal():
            assert is_equal_type(GraphQLString, GraphQLString) is True

        def int_and_float_are_not_equal():
            assert is_equal_type(GraphQLInt, GraphQLFloat) is False

        def lists_of_same_type_are_equal():
            assert (
                is_equal_type(GraphQLList(GraphQLInt), GraphQLList(GraphQLInt)) is True
            )

        def lists_is_not_equal_to_item():
            assert is_equal_type(GraphQLList(GraphQLInt), GraphQLInt) is False

        def nonnull_of_same_type_are_equal():
            assert (
                is_equal_type(GraphQLNonNull(GraphQLInt), GraphQLNonNull(GraphQLInt))
                is True
            )

        def nonnull_is_not_equal_to_nullable():
            assert is_equal_type(GraphQLNonNull(GraphQLInt), GraphQLInt) is False

    def describe_is_type_sub_type_of():
        def _test_schema(field_type: GraphQLOutputType = GraphQLString):
            return GraphQLSchema(
                query=GraphQLObjectType("Query", {"field": GraphQLField(field_type)})
            )

        def same_reference_is_subtype():
            assert (
                is_type_sub_type_of(_test_schema(), GraphQLString, GraphQLString)
                is True
            )

        def int_is_not_subtype_of_float():
            assert (
                is_type_sub_type_of(_test_schema(), GraphQLInt, GraphQLFloat) is False
            )

        def non_null_is_subtype_of_nullable():
            assert (
                is_type_sub_type_of(
                    _test_schema(), GraphQLNonNull(GraphQLInt), GraphQLInt
                )
                is True
            )

        def nullable_is_not_subtype_of_non_null():
            assert (
                is_type_sub_type_of(
                    _test_schema(), GraphQLInt, GraphQLNonNull(GraphQLInt)
                )
                is False
            )

        def item_is_not_subtype_of_list():
            assert not is_type_sub_type_of(
                _test_schema(), GraphQLInt, GraphQLList(GraphQLInt)
            )

        def list_is_not_subtype_of_item():
            assert not is_type_sub_type_of(
                _test_schema(), GraphQLList(GraphQLInt), GraphQLInt
            )

        def member_is_subtype_of_union():
            member = GraphQLObjectType("Object", {"field": GraphQLField(GraphQLString)})
            union = GraphQLUnionType("Union", [member])
            schema = _test_schema(union)
            assert is_type_sub_type_of(schema, member, union)

        def implementing_object_is_subtype_of_interface():
            iface = GraphQLInterfaceType(
                "Interface", {"field": GraphQLField(GraphQLString)}
            )
            impl = GraphQLObjectType(
                "Object",
                {"field": GraphQLField(GraphQLString)},
                [iface],
            )
            schema = _test_schema(impl)
            assert is_type_sub_type_of(schema, impl, iface)

        def implementing_interface_is_subtype_of_interface():
            iface = GraphQLInterfaceType(
                "Interface", {"field": GraphQLField(GraphQLString)}
            )
            iface2 = GraphQLInterfaceType(
                "Interface2", {"field": GraphQLField(GraphQLString)}, [iface]
            )
            impl = GraphQLObjectType(
                "Object",
                {"field": GraphQLField(GraphQLString)},
                [iface2, iface],
            )
            schema = _test_schema(impl)
            assert is_type_sub_type_of(schema, iface2, iface)
