from graphql.error import GraphQLError, located_error


def describe_located_error():
    def passes_graphql_error_through():
        path = ["path", 3, "to", "field"]
        # noinspection PyArgumentEqualDefault
        e = GraphQLError("msg", None, None, None, path)
        assert located_error(e, [], []) == e

    def passes_graphql_error_ish_through():
        e = Exception("I am an ordinary exception")
        e.locations = []
        e.path = []
        e.nodes = []
        e.source = None
        e.positions = []
        assert located_error(e, [], []) == e

    def does_not_pass_through_elasticsearch_like_errors():
        e = Exception("I am from elasticsearch")
        e.path = "/something/feed/_search"
        assert located_error(e, [], []) != e
