from pytest import raises  # type: ignore

from graphql.language import DirectiveLocation, TypeDefinitionNode, TypeExtensionNode
from graphql.pyutils import dedent
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLDirective,
    GraphQLField,
    GraphQLInputObjectType,
    GraphQLInputField,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import print_schema


def describe_type_system_schema():
    def define_sample_schema():
        BlogImage = GraphQLObjectType(
            "Image",
            {
                "url": GraphQLField(GraphQLString),
                "width": GraphQLField(GraphQLInt),
                "height": GraphQLField(GraphQLInt),
            },
        )

        BlogArticle: GraphQLObjectType

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

        schema = GraphQLSchema(BlogQuery, BlogMutation, BlogSubscription)

        kwargs = schema.to_kwargs()
        types = kwargs.pop("types")
        assert types == list(schema.type_map.values())
        assert kwargs == {
            "query": BlogQuery,
            "mutation": BlogMutation,
            "subscription": BlogSubscription,
            "directives": None,
            "ast_node": None,
            "extension_ast_nodes": None,
            "assume_valid": False,
        }

        assert print_schema(schema) == dedent(
            """
            type Article {
              id: String
              isPublished: Boolean
              author: Author
              title: String
              body: String
            }

            type Author {
              id: String
              name: String
              pic(width: Int, height: Int): Image
              recentArticle: Article
            }

            type Image {
              url: String
              width: Int
              height: Int
            }

            type Mutation {
              writeArticle: Article
            }

            type Query {
              article(id: String): Article
              feed: [Article]
            }

            type Subscription {
              articleSubscribe(id: String): Article
            }
            """
        )

    def describe_type_map():
        def includes_interface_possible_types_in_the_type_map():
            SomeInterface = GraphQLInterfaceType("SomeInterface", {})
            SomeSubtype = GraphQLObjectType(
                "SomeSubtype", {}, interfaces=[SomeInterface]
            )
            schema = GraphQLSchema(
                query=GraphQLObjectType(
                    "Query", {"iface": GraphQLField(SomeInterface)}
                ),
                types=[SomeSubtype],
            )
            assert schema.type_map["SomeInterface"] is SomeInterface
            assert schema.type_map["SomeSubtype"] is SomeSubtype

        def includes_interfaces_thunk_subtypes_in_the_type_map():
            SomeInterface = GraphQLInterfaceType("SomeInterface", {})
            SomeSubtype = GraphQLObjectType(
                "SomeSubtype", {}, interfaces=lambda: [SomeInterface]
            )
            schema = GraphQLSchema(
                query=GraphQLObjectType(
                    "Query", {"iface": GraphQLField(SomeInterface)}
                ),
                types=[SomeSubtype],
            )
            assert schema.type_map["SomeInterface"] is SomeInterface
            assert schema.type_map["SomeSubtype"] is SomeSubtype

        def includes_nested_input_objects_in_the_map():
            NestedInputObject = GraphQLInputObjectType("NestedInputObject", {})
            SomeInputObject = GraphQLInputObjectType(
                "SomeInputObject", {"nested": GraphQLInputField(NestedInputObject)}
            )

            schema = GraphQLSchema(
                GraphQLObjectType(
                    "Query",
                    {
                        "something": GraphQLField(
                            GraphQLString, {"input": GraphQLArgument(SomeInputObject)}
                        )
                    },
                )
            )
            assert schema.type_map["SomeInputObject"] is SomeInputObject
            assert schema.type_map["NestedInputObject"] is NestedInputObject

        def includes_input_types_only_used_in_directives():
            directive = GraphQLDirective(
                name="dir",
                locations=[DirectiveLocation.OBJECT],
                args={
                    "arg": GraphQLArgument(
                        GraphQLInputObjectType(
                            "Foo", {"field": GraphQLInputField(GraphQLString)}
                        )
                    ),
                    "argList": GraphQLArgument(
                        GraphQLList(
                            GraphQLInputObjectType(
                                "Bar", {"field": GraphQLInputField(GraphQLString)}
                            )
                        )
                    ),
                },
            )
            schema = GraphQLSchema(directives=[directive])
            assert "Foo" in schema.type_map
            assert "Bar" in schema.type_map

    def describe_type_map_reducer():
        def allows_overriding_the_type_map_reducers():
            foo_type = GraphQLObjectType("Foo", {"bar": GraphQLField(GraphQLString)})
            query_type = GraphQLObjectType("Query", {"foo": GraphQLField(foo_type)})
            baz_directive = GraphQLDirective("Baz", [])

            log_types = []
            log_directives = []

            class CustomGraphQLSchema(GraphQLSchema):
                def type_map_reducer(self, map_, type_):
                    log_types.append(type_)
                    return super().type_map_reducer(map_, type_)

                def type_map_directive_reducer(self, map_, directive):
                    log_directives.append(directive)
                    return super().type_map_directive_reducer(map_, directive)

            schema = CustomGraphQLSchema(query_type, directives=[baz_directive])
            assert schema.type_map["Query"] == query_type
            assert schema.type_map["Foo"] == foo_type
            assert schema.directives == [baz_directive]
            assert query_type in log_types
            assert foo_type in log_types
            assert GraphQLString in log_types
            assert log_directives == [baz_directive]

    def describe_validity():
        def describe_when_not_assumed_valid():
            def configures_the_schema_to_still_needing_validation():
                # noinspection PyProtectedMember
                assert GraphQLSchema(assume_valid=False).validation_errors is None

            def checks_the_configuration_for_mistakes():
                with raises(Exception):
                    # noinspection PyTypeChecker
                    GraphQLSchema(lambda: None)
                with raises(Exception):
                    GraphQLSchema(types={})
                with raises(Exception):
                    GraphQLSchema(directives={})

    def describe_a_schema_must_contain_uniquely_named_types():
        def rejects_a_schema_which_redefines_a_built_in_type():
            FakeString = GraphQLScalarType("String")

            QueryType = GraphQLObjectType(
                "Query",
                {
                    "normal": GraphQLField(GraphQLString),
                    "fake": GraphQLField(FakeString),
                },
            )

            with raises(TypeError) as exc_info:
                GraphQLSchema(QueryType)
            msg = str(exc_info.value)
            assert msg == (
                "Schema must contain uniquely named types"
                f" but contains multiple types named 'String'."
            )

        def rejects_a_schema_which_defines_an_object_twice():
            types = [
                GraphQLObjectType("SameName", {}),
                GraphQLObjectType("SameName", {}),
            ]

            with raises(TypeError) as exc_info:
                GraphQLSchema(types=types)
            msg = str(exc_info.value)
            assert msg == (
                "Schema must contain uniquely named types"
                f" but contains multiple types named 'SameName'."
            )

        def rejects_a_schema_which_defines_fields_with_conflicting_types():
            fields = {}
            QueryType = GraphQLObjectType(
                "Query",
                {
                    "a": GraphQLField(GraphQLObjectType("SameName", fields)),
                    "b": GraphQLField(GraphQLObjectType("SameName", fields)),
                },
            )

            with raises(TypeError) as exc_info:
                GraphQLSchema(QueryType)
            msg = str(exc_info.value)
            assert msg == (
                "Schema must contain uniquely named types"
                f" but contains multiple types named 'SameName'."
            )

        def describe_when_assumed_valid():
            def configures_the_schema_to_have_no_errors():
                # noinspection PyProtectedMember
                assert GraphQLSchema(assume_valid=True).validation_errors == []

    def describe_ast_nodes():
        def rejects_a_schema_with_an_incorrect_ast_node():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLSchema(
                    GraphQLObjectType("Query", {}), ast_node=TypeDefinitionNode()
                )
            msg = str(exc_info.value)
            assert msg == "Schema AST node must be a SchemaDefinitionNode."

        def rejects_a_scalar_type_with_incorrect_extension_ast_nodes():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLSchema(
                    GraphQLObjectType("Query", {}),
                    extension_ast_nodes=[TypeExtensionNode()],
                )
            assert str(exc_info.value) == (
                "Schema extension AST nodes must be specified"
                " as a sequence of SchemaExtensionNode instances."
            )
