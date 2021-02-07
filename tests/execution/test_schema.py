from graphql.execution import execute_sync
from graphql.language import parse
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLField,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)


def describe_execute_handles_execution_with_a_complex_schema():
    def executes_using_a_schema():
        class Article:

            # noinspection PyShadowingBuiltins
            def __init__(self, id: int):
                self.id = id
                self.isPublished = True
                self.author = JohnSmith()
                self.title = f"My Article {id}"
                self.body = "This is a post"
                self.hidden = "This data is not exposed in the schema"
                self.keywords = ["foo", "bar", 1, True, None]

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
                    resolve=lambda obj, info, width, height: obj.pic(
                        info, width, height
                    ),
                ),
                "recentArticle": GraphQLField(BlogArticle),
            },
        )

        BlogArticle = GraphQLObjectType(
            "Article",
            {
                "id": GraphQLField(GraphQLNonNull(GraphQLString)),
                "isPublished": GraphQLField(GraphQLBoolean),
                "author": GraphQLField(BlogAuthor),
                "title": GraphQLField(GraphQLString),
                "body": GraphQLField(GraphQLString),
                "keywords": GraphQLField(GraphQLList(GraphQLString)),
            },
        )

        # noinspection PyShadowingBuiltins
        BlogQuery = GraphQLObjectType(
            "Query",
            {
                "article": GraphQLField(
                    BlogArticle,
                    args={"id": GraphQLArgument(GraphQLID)},
                    resolve=lambda _obj, _info, id: Article(id),
                ),
                "feed": GraphQLField(
                    GraphQLList(BlogArticle),
                    resolve=lambda *_args: [Article(n + 1) for n in range(10)],
                ),
            },
        )

        BlogSchema = GraphQLSchema(BlogQuery)

        # noinspection PyPep8Naming,PyMethodMayBeStatic
        class Author:
            def pic(self, info_, width: int, height: int) -> "Pic":
                return Pic(123, width, height)

            @property
            def recentArticle(self) -> Article:
                return Article(1)

        class JohnSmith(Author):
            id = 123
            name = "John Smith"

        class Pic:
            def __init__(self, uid: int, width: int, height: int):
                self.url = f"cdn://{uid}"
                self.width = f"{width}"
                self.height = f"{height}"

        document = parse(
            """
            {
              feed {
                id,
                title
              },
              article(id: "1") {
                ...articleFields,
                author {
                  id,
                  name,
                  pic(width: 640, height: 480) {
                    url,
                    width,
                    height
                  },
                  recentArticle {
                    ...articleFields,
                    keywords
                  }
                }
              }
            }

            fragment articleFields on Article {
              id,
              isPublished,
              title,
              body,
              hidden,
              notDefined
            }
            """
        )

        # Note: this is intentionally not validating to ensure appropriate
        # behavior occurs when executing an invalid query.
        assert execute_sync(schema=BlogSchema, document=document) == (
            {
                "feed": [
                    {"id": "1", "title": "My Article 1"},
                    {"id": "2", "title": "My Article 2"},
                    {"id": "3", "title": "My Article 3"},
                    {"id": "4", "title": "My Article 4"},
                    {"id": "5", "title": "My Article 5"},
                    {"id": "6", "title": "My Article 6"},
                    {"id": "7", "title": "My Article 7"},
                    {"id": "8", "title": "My Article 8"},
                    {"id": "9", "title": "My Article 9"},
                    {"id": "10", "title": "My Article 10"},
                ],
                "article": {
                    "id": "1",
                    "isPublished": True,
                    "title": "My Article 1",
                    "body": "This is a post",
                    "author": {
                        "id": "123",
                        "name": "John Smith",
                        "pic": {"url": "cdn://123", "width": 640, "height": 480},
                        "recentArticle": {
                            "id": "1",
                            "isPublished": True,
                            "title": "My Article 1",
                            "body": "This is a post",
                            "keywords": ["foo", "bar", "1", "true", None],
                        },
                    },
                },
            },
            None,
        )
