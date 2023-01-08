from copy import deepcopy

from pytest import raises

from graphql.language import (
    DirectiveLocation,
    SchemaDefinitionNode,
    SchemaExtensionNode,
)
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLDirective,
    GraphQLField,
    GraphQLFieldMap,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    GraphQLType,
    GraphQLUnionType,
    SchemaMetaFieldDef,
    TypeMetaFieldDef,
    TypeNameMetaFieldDef,
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
        assert types == tuple(schema.type_map.values())
        assert kwargs == {
            "query": BlogQuery,
            "mutation": BlogMutation,
            "subscription": BlogSubscription,
            "directives": specified_directives,
            "description": "Sample schema",
            "extensions": {},
            "ast_node": None,
            "extension_ast_nodes": (),
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
        directives_list = [GraphQLDirective("SomeDirective", [])]
        schema = GraphQLSchema(directives=directives_list)
        assert isinstance(schema.directives, tuple)
        assert schema.directives == tuple(directives_list)
        directives_tuple = schema.directives
        schema = GraphQLSchema(directives=directives_tuple)
        assert schema.directives is directives_tuple

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

    def describe_get_field():
        pet_type = GraphQLInterfaceType("Pet", {"name": GraphQLField(GraphQLString)})
        cat_type = GraphQLObjectType(
            "Cat", {"name": GraphQLField(GraphQLString)}, [pet_type]
        )
        dog_type = GraphQLObjectType(
            "Dog", {"name": GraphQLField(GraphQLString)}, [pet_type]
        )
        cat_or_dog = GraphQLUnionType("CatOrDog", [cat_type, dog_type])
        query_type = GraphQLObjectType("Query", {"catOrDog": GraphQLField(cat_or_dog)})
        mutation_type = GraphQLObjectType("Mutation", {})
        subscription_type = GraphQLObjectType("Subscription", {})
        schema = GraphQLSchema(query_type, mutation_type, subscription_type)

        _get_field = schema.get_field

        def returns_known_field():
            assert _get_field(pet_type, "name") == pet_type.fields["name"]
            assert _get_field(cat_type, "name") == cat_type.fields["name"]

            assert _get_field(query_type, "catOrDog") == query_type.fields["catOrDog"]

        def returns_none_for_unknown_fields():
            assert _get_field(cat_or_dog, "name") is None

            assert _get_field(query_type, "unknown") is None
            assert _get_field(pet_type, "unknown") is None
            assert _get_field(cat_type, "unknown") is None
            assert _get_field(cat_or_dog, "unknown") is None

        def handles_introspection_fields():
            assert _get_field(query_type, "__typename") == TypeNameMetaFieldDef
            assert _get_field(mutation_type, "__typename") == TypeNameMetaFieldDef
            assert _get_field(subscription_type, "__typename") == TypeNameMetaFieldDef

            assert _get_field(pet_type, "__typename") is TypeNameMetaFieldDef
            assert _get_field(cat_type, "__typename") is TypeNameMetaFieldDef
            assert _get_field(dog_type, "__typename") is TypeNameMetaFieldDef
            assert _get_field(cat_or_dog, "__typename") is TypeNameMetaFieldDef

            assert _get_field(query_type, "__type") is TypeMetaFieldDef
            assert _get_field(query_type, "__schema") is SchemaMetaFieldDef

        def returns_non_for_introspection_fields_in_wrong_location():
            assert _get_field(pet_type, "__type") is None
            assert _get_field(dog_type, "__type") is None
            assert _get_field(mutation_type, "__type") is None
            assert _get_field(subscription_type, "__type") is None

            assert _get_field(pet_type, "__schema") is None
            assert _get_field(dog_type, "__schema") is None
            assert _get_field(mutation_type, "__schema") is None
            assert _get_field(subscription_type, "__schema") is None

    def describe_validity():
        def describe_when_not_assumed_valid():
            def configures_the_schema_to_still_needing_validation():
                # noinspection PyProtectedMember
                assert GraphQLSchema(assume_valid=False).validation_errors is None

    def describe_a_schema_must_contain_uniquely_named_types():
        def rejects_a_schema_which_redefines_a_built_in_type():
            # temporarily allow redefinition of the String scalar type
            reserved_types = GraphQLNamedType.reserved_types
            GraphQLScalarType.reserved_types = {}
            try:
                # create a redefined String scalar type
                FakeString = GraphQLScalarType("String")
            finally:
                # protect from redefinition again
                GraphQLScalarType.reserved_types = reserved_types

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
            assert schema.extension_ast_nodes == tuple(extension_ast_nodes)

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
