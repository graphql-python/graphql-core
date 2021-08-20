Executing Queries
-----------------

.. currentmodule:: graphql.execution

Now that we have defined the schema and breathed life into it with our resolver
functions, we can execute arbitrary query against the schema.

The :mod:`graphql` package provides the :func:`graphql.graphql` function to execute
queries. This is the main feature of GraphQL-core.

Note however that this function is actually a coroutine intended to be used in
asynchronous code running in an event loop.

Here is one way to use it::

    import asyncio
    from graphql import graphql

    async def query_artoo():
        result = await graphql(schema, """
        {
          droid(id: "2001") {
            name
            primaryFunction
          }
        }
        """)
        print(result)

    asyncio.run(query_artoo())

In our query, we asked for the droid with the id 2001, which is R2-D2, and its primary
function, Astromech. When everything has been implemented correctly as shown above, you
should get the expected result::

    ExecutionResult(
        data={'droid': {'name': 'R2-D2', 'primaryFunction': 'Astromech'}},
        errors=None)

The :class:`ExecutionResult` has a ``data`` attribute with the actual result, and an
``errors`` attribute with a list of errors if there were any.

If all your resolvers work synchronously, as in our case, you can also use the
:func:`graphql.graphql_sync` function to query the result in ordinary synchronous code::

    from graphql import graphql_sync

    result = graphql_sync(schema, """
      query FetchHuman($id: String!) {
        human(id: $id) {
          name
          homePlanet
        }
      }
      """, variable_values={'id': '1000'})
    print(result)

Here we asked for the human with the id 1000, Luke Skywalker, and his home planet,
Tatooine. So the output of the code above is::

    ExecutionResult(
        data={'human': {'name': 'Luke Skywalker', 'homePlanet': 'Tatooine'}},
        errors=None)

Let's see what happens when we make a mistake in the query, by querying a non-existing
``homeTown`` field::

    result = graphql_sync(schema, """
        {
          human(id: "1000") {
            name
            homePlace
          }
        }
        """)
    print(result)

You will get the following result as output::

    ExecutionResult(data=None, errors=[GraphQLError(
        "Cannot query field 'homePlace' on type 'Human'. Did you mean 'homePlanet'?",
        locations=[SourceLocation(line=5, column=9)])])

This is very helpful. Not only do we get the exact location of the mistake in the query,
but also a suggestion for correcting the bad field name.

GraphQL also allows to request the meta field ``__typename``. We can use this to verify
that the hero of "The Empire Strikes Back" episode is Luke Skywalker and that he is in
fact a human::

    result = graphql_sync(schema, """
        {
          hero(episode: EMPIRE) {
            __typename
            name
          }
        }
        """)
    print(result)

This gives the following output::

    ExecutionResult(
        data={'hero': {'__typename': 'Human', 'name': 'Luke Skywalker'}},
        errors=None)

Finally, let's see what happens when we try to access the secret backstory of our hero::

    result = graphql_sync(schema, """
        {
          hero(episode: EMPIRE) {
            name
            secretBackstory
          }
        }
        """)
    print(result)

While we get the name of the hero, the secret backstory fields remains empty, since its
resolver function raises an error. However, we get the error that has been raised by the
resolver in the ``errors`` attribute of the result::

    ExecutionResult(
        data={'hero': {'name': 'Luke Skywalker', 'secretBackstory': None}},
        errors=[GraphQLError('secretBackstory is secret.',
                locations=[SourceLocation(line=5, column=9)],
                path=['hero', 'secretBackstory'])])

