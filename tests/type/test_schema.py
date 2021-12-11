from copy import deepcopy

from pytest import raises

from graphql.language import (
    DirectiveLocation,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
)
from graphql.pyutils import FrozenList
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLDirective,
    GraphQLField,
    GraphQLFieldMap,
    GraphQLInputObjectType,
    GraphQLInputField,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    GraphQLType,
    specified_directives,
)
from graphql.utilities import build_schema, lexicographic_sort_schema, print_schema

from ..utils import dedent


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

        schema = GraphQLSchema(
            BlogQuery,
            BlogMutation,
            BlogSubscription,
            description="Sample schema",
        )

        kwargs = schema.to_kwargs()
        types = kwargs.pop("types")
        assert types == list(schema.type_map.values())
        assert kwargs == {
            "query": BlogQuery,
            "mutation": BlogMutation,
            "subscription": BlogSubscription,
            "directives": specified_directives,
            "description": "Sample schema",
            "extensions": {},
            "ast_node": None,
            "extension_ast_nodes": [],
            "assume_valid": False,
        }

        assert print_schema(schema) == dedent(
            '''
            """Sample schema"""
            schema {
              query: Query
              mutation: Mutation
              subscription: Subscription
            }

            type Query {
              article(id: String): Article
              feed: [Article]
            }

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

            type Subscription {
              articleSubscribe(id: String): Article
            }
            '''
        )

    def freezes_the_specified_directives():
        directives = [GraphQLDirective("SomeDirective", [])]
        schema = GraphQLSchema(directives=directives)
        assert isinstance(schema.directives, FrozenList)
        assert schema.directives == directives
        directives = schema.directives
        schema = GraphQLSchema(directives=directives)
        assert schema.directives is directives

    def rejects_a_schema_with_incorrectly_typed_description():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            GraphQLSchema(description=[])  # type: ignore
        assert str(exc_info.value) == "Schema description must be a string."

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

            assert schema.is_sub_type(SomeInterface, SomeSubtype) is True

        def includes_interfaces_thunk_subtypes_in_the_type_map():
            AnotherInterface = GraphQLInterfaceType("AnotherInterface", {})
            SomeInterface = GraphQLInterfaceType(
                "SomeInterface", {}, interfaces=lambda: [AnotherInterface]
            )
            SomeSubtype = GraphQLObjectType(
                "SomeSubtype", {}, interfaces=lambda: [SomeInterface]
            )
            schema = GraphQLSchema(
                types=[SomeSubtype],
            )
            assert schema.type_map["SomeInterface"] is SomeInterface
            assert schema.type_map["AnotherInterface"] is AnotherInterface
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

    def preserves_the_order_of_user_provided_types():
        a_type = GraphQLObjectType(
            "A", {"sub": GraphQLField(GraphQLScalarType("ASub"))}
        )
        z_type = GraphQLObjectType(
            "Z", {"sub": GraphQLField(GraphQLScalarType("ZSub"))}
        )
        query_type = GraphQLObjectType(
            "Query",
            {
                "a": GraphQLField(a_type),
                "z": GraphQLField(z_type),
                "sub": GraphQLField(GraphQLScalarType("QuerySub")),
            },
        )
        schema = GraphQLSchema(query_type, types=[z_type, query_type, a_type])

        type_names = list(schema.type_map)
        assert type_names == [
            "Z",
            "ZSub",
            "Query",
            "QuerySub",
            "A",
            "ASub",
            "Boolean",
            "String",
            "__Schema",
            "__Type",
            "__TypeKind",
            "__Field",
            "__InputValue",
            "__EnumValue",
            "__Directive",
            "__DirectiveLocation",
        ]

        # Also check that this order is stable
        copy_schema = GraphQLSchema(**schema.to_kwargs())
        assert list(copy_schema.type_map) == type_names

    def describe_validity():
        def describe_when_not_assumed_valid():
            def configures_the_schema_to_still_needing_validation():
                # noinspection PyProtectedMember
                assert GraphQLSchema(assume_valid=False).validation_errors is None

            def checks_the_configuration_for_mistakes():
                def query():
                    pass

                with raises(Exception):
                    # noinspection PyTypeChecker
                    GraphQLSchema(query)  # type: ignore
                with raises(Exception):
                    GraphQLSchema(types={})
                with raises(Exception):
                    GraphQLSchema(directives={})

            def check_that_query_mutation_and_subscription_are_graphql_types():
                directive = GraphQLDirective("foo", [])
                with raises(TypeError) as exc_info:
                    # noinspection PyTypeChecker
                    GraphQLSchema(query=directive)  # type: ignore
                assert str(exc_info.value) == "Expected query to be a GraphQL type."
                with raises(TypeError) as exc_info:
                    # noinspection PyTypeChecker
                    GraphQLSchema(mutation=directive)  # type: ignore
                assert str(exc_info.value) == (
                    "Expected mutation to be a GraphQL type."
                )
                with raises(TypeError) as exc_info:
                    # noinspection PyTypeChecker
                    GraphQLSchema(subscription=directive)  # type: ignore
                assert str(exc_info.value) == (
                    "Expected subscription to be a GraphQL type."
                )

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
                " but contains multiple types named 'String'."
            )

        def rejects_a_schema_when_a_provided_type_has_no_name():
            query = GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)})
            types = [GraphQLType(), query, GraphQLType()]

            with raises(TypeError) as exc_info:
                GraphQLSchema(query, types=types)  # type: ignore
            msg = str(exc_info.value)
            assert msg == (
                "One of the provided types for building the Schema is missing a name."
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
                " but contains multiple types named 'SameName'."
            )

        def rejects_a_schema_which_defines_fields_with_conflicting_types():
            fields: GraphQLFieldMap = {}
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
                " but contains multiple types named 'SameName'."
            )

        def describe_when_assumed_valid():
            def configures_the_schema_to_have_no_errors():
                # noinspection PyProtectedMember
                assert GraphQLSchema(assume_valid=True).validation_errors == []

    def describe_ast_nodes():
        def accepts_a_scalar_type_with_ast_node_and_extension_ast_nodes():
            ast_node = SchemaDefinitionNode()
            extension_ast_nodes = [SchemaExtensionNode()]
            schema = GraphQLSchema(
                GraphQLObjectType("Query", {}),
                ast_node=ast_node,
                extension_ast_nodes=extension_ast_nodes,
            )
            assert schema.ast_node is ast_node
            assert isinstance(schema.extension_ast_nodes, FrozenList)
            assert schema.extension_ast_nodes == extension_ast_nodes
            extension_ast_nodes = schema.extension_ast_nodes
            schema = GraphQLSchema(
                GraphQLObjectType("Query", {}),
                ast_node=None,
                extension_ast_nodes=extension_ast_nodes,
            )
            assert schema.ast_node is None
            assert schema.extension_ast_nodes is extension_ast_nodes

        def rejects_a_schema_with_an_incorrect_ast_node():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLSchema(
                    GraphQLObjectType("Query", {}),
                    ast_node=TypeDefinitionNode(),  # type: ignore
                )
            msg = str(exc_info.value)
            assert msg == "Schema AST node must be a SchemaDefinitionNode."

        def rejects_a_scalar_type_with_incorrect_extension_ast_nodes():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                GraphQLSchema(
                    GraphQLObjectType("Query", {}),
                    extension_ast_nodes=[TypeExtensionNode()],  # type: ignore
                )
            assert str(exc_info.value) == (
                "Schema extension AST nodes must be specified"
                " as a collection of SchemaExtensionNode instances."
            )

    def can_deep_copy_a_schema():
        source = """
            schema {
              query: Farm
              mutation: Work
            }

            type Cow {
              id: ID!
              name: String
              moos: Boolean
            }

            type Pig {
              id: ID!
              name: String
              oink: Boolean
            }

            union Animal = Cow | Pig

            enum Food {
              CORN
              FRUIT
            }

            input Feed {
              amount: Float
              type: Food
            }

            type Farm {
              animals: [Animal!]!
            }

            type Work {
              feed(feed: Feed): Boolean
            }
        """
        schema = build_schema(source)
        schema_copy = deepcopy(schema)

        for name in ("Cow", "Pig", "Animal", "Food", "Feed", "Farm", "Work"):
            assert schema.get_type(name) is not schema_copy.get_type(name)

        assert print_schema(lexicographic_sort_schema(schema)) == print_schema(
            lexicographic_sort_schema(schema_copy)
        )
