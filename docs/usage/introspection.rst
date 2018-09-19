Using an Introspection Query
----------------------------

A third way of building a schema is using an introspection query on an existing server.
This is what GraphiQL uses to get information about the schema on the remote server. You
can create an introspection query using GraphQL-core-next with::

    from graphql import get_introspection_query

    query = get_introspection_query(descriptions=True)

This will also yield the descriptions of the introspected schema fields. You can also
create a query that omits the descriptions with::

    query = get_introspection_query(descriptions=False)

In practice you would run this query against a remote server, but we can also run it
against the schema we have just built above::

    introspection_query_result = graphql_sync(schema, query)

The ``data`` attribute of the introspection query result now gives us a dictionary,
which constitutes a third way of describing a GraphQL schema::

    {'__schema': {
        'queryType': {'name': 'Query'},
        'mutationType': None, 'subscriptionType': None,
        'types': [
            {'kind': 'OBJECT', 'name': 'Query', 'description': None,
             'fields': [{
                'name': 'hero', 'description': None,
                'args': [{'name': 'episode', 'description': ... }],
                ... }, ... ], ... },
            ... ],
        ... }
    }

This result contains all the information that is available in the SDL description of the
schema, i.e. it does not contain the resolve functions and information on the
server-side values of the enum types.

You can convert the introspection result into ``GraphQLSchema`` with GraphQL-core-next
by using the :func:`graphql.utilities.build_client_schema` function::

    from graphql import build_client_schema

    client_schema = build_client_schema(introspection_query_result.data)


It is also possible to convert the result to SDL with GraphQL-core-next by using the
:func:`graphql.utilities.print_schema` function::

    from graphql import print_schema

    sdl = print_schema(client_schema)
    print(sdl)

This prints the SDL representation of the schema that we started with.

As you see, it is easy to convert between the three forms of representing a GraphQL
schema in GraphQL-core-next.
