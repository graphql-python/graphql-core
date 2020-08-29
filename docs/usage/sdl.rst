Using the Schema Definition Language
------------------------------------

.. currentmodule:: graphql.type

Above we defined the GraphQL schema as Python code, using the :class:`GraphQLSchema`
class and other classes representing the various GraphQL types.

GraphQL-core 3 also provides a language-agnostic way of defining a GraphQL schema
using the GraphQL schema definition language (SDL) which is also part of the GraphQL
specification. To do this, we simply feed the SDL as a string to the
:func:`~graphql.utilities.build_schema` function in :mod:`graphql.utilities`::

    from graphql import build_schema

    schema = build_schema("""

        enum Episode { NEWHOPE, EMPIRE, JEDI }

        interface Character {
          id: String!
          name: String
          friends: [Character]
          appearsIn: [Episode]
        }

        type Human implements Character {
          id: String!
          name: String
          friends: [Character]
          appearsIn: [Episode]
          homePlanet: String
        }

        type Droid implements Character {
          id: String!
          name: String
          friends: [Character]
          appearsIn: [Episode]
          primaryFunction: String
        }

        type Query {
          hero(episode: Episode): Character
          human(id: String!): Human
          droid(id: String!): Droid
        }
        """)

The result is a :class:`GraphQLSchema` object just like the one we defined above, except
for the resolver functions which cannot be defined in the SDL.

We would need to manually attach these functions to the schema, like so::

    schema.query_type.fields['hero'].resolve = get_hero
    schema.get_type('Character').resolve_type = get_character_type

Another problem is that the SDL does not define the server side values of the
``Episode`` enum type which are returned by the resolver functions and which are
different from the names used for the episode.

So we would also need to manually define these values, like so::

    for name, value in schema.get_type('Episode').values.items():
        value.value = EpisodeEnum[name].value

This would allow us to query the schema built from SDL just like the manually assembled
schema::

    from graphql import graphql_sync

    result = graphql_sync(schema, """
        {
          hero(episode: EMPIRE) {
            name
            appearsIn
          }
        }
        """)
    print(result)

And we would get the expected result::

    ExecutionResult(
        data={'hero': {'name': 'Luke Skywalker',
                       'appearsIn': ['NEWHOPE', 'EMPIRE', 'JEDI']}},
        errors=None)
