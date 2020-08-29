Building a Type Schema
----------------------

.. currentmodule:: graphql.type

Using the classes in the :mod:`graphql.type` sub-package as building blocks, you can
build a complete GraphQL type schema.

Let's take the following schema as an example, which will allow us to query our favorite
heroes from the Star Wars trilogy::

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

We have been using the so called GraphQL schema definition language (SDL) here to
describe the schema. While it is also possible to build a schema directly from this
notation using GraphQL-core 3, let's first create that schema manually by assembling
the types defined here using Python classes, adding resolver functions written in Python
for querying the data.

First, we need to import all the building blocks from the :mod:`graphql.type`
sub-package. Note that you don't need to import from the sub-packages, since nearly
everything is also available directly in the top :mod:`graphql` package::

    from graphql import (
        GraphQLArgument, GraphQLEnumType, GraphQLEnumValue,
        GraphQLField, GraphQLInterfaceType, GraphQLList, GraphQLNonNull,
        GraphQLObjectType, GraphQLSchema, GraphQLString)

Next, we need to build the enum type ``Episode``::

    episode_enum = GraphQLEnumType('Episode', {
        'NEWHOPE': GraphQLEnumValue(4, description='Released in 1977.'),
        'EMPIRE': GraphQLEnumValue(5, description='Released in 1980.'),
        'JEDI': GraphQLEnumValue(6, description='Released in 1983.')
        }, description='One of the films in the Star Wars Trilogy')

If you don't need the descriptions for the enum values, you can also define the enum
type like this using an underlying Python ``Enum`` type::

    from enum import Enum

    class EpisodeEnum(Enum):
        NEWHOPE = 4
        EMPIRE = 5
        JEDI = 6

    episode_enum = GraphQLEnumType(
        'Episode', EpisodeEnum,
        description='One of the films in the Star Wars Trilogy')

You can also use a Python dictionary instead of a Python ``Enum`` type to define the
GraphQL enum type::

    episode_enum = GraphQLEnumType(
        'Episode', {'NEWHOPE': 4, 'EMPIRE': 5, 'JEDI': 6},
        description='One of the films in the Star Wars Trilogy')

Our schema also contains a ``Character`` interface. Here is how we build it::

    character_interface = GraphQLInterfaceType('Character', lambda: {
        'id': GraphQLField(
            GraphQLNonNull(GraphQLString),
            description='The id of the character.'),
        'name': GraphQLField(
            GraphQLString,
            description='The name of the character.'),
        'friends': GraphQLField(
            GraphQLList(character_interface),
            description='The friends of the character,'
                        ' or an empty list if they have none.'),
        'appearsIn': GraphQLField(
            GraphQLList(episode_enum),
            description='Which movies they appear in.'),
        'secretBackstory': GraphQLField(
            GraphQLString,
            description='All secrets about their past.')},
        resolve_type=get_character_type,
        description='A character in the Star Wars Trilogy')

Note that we did not pass the dictionary of fields to the ``GraphQLInterfaceType``
directly, but using a lambda function (a so-called "thunk"). This is necessary because
the fields are referring back to the character interface that we are just defining.
Whenever you have such recursive definitions in GraphQL-core, you need to use thunks.
Otherwise, you can pass everything directly.

Characters in the Star Wars trilogy are either humans or droids. So we define a
``Human`` and a ``Droid`` type, which both implement the ``Character`` interface::

    human_type = GraphQLObjectType('Human', lambda: {
        'id': GraphQLField(
            GraphQLNonNull(GraphQLString),
            description='The id of the human.'),
        'name': GraphQLField(
            GraphQLString,
            description='The name of the human.'),
        'friends': GraphQLField(
            GraphQLList(character_interface),
            description='The friends of the human,'
                        ' or an empty list if they have none.',
            resolve=get_friends),
        'appearsIn': GraphQLField(
            GraphQLList(episode_enum),
            description='Which movies they appear in.'),
        'homePlanet': GraphQLField(
            GraphQLString,
            description='The home planet of the human, or null if unknown.'),
        'secretBackstory': GraphQLField(
            GraphQLString,
            resolve=get_secret_backstory,
            description='Where are they from'
                        ' and how they came to be who they are.')},
        interfaces=[character_interface],
        description='A humanoid creature in the Star Wars universe.')

    droid_type = GraphQLObjectType('Droid', lambda: {
        'id': GraphQLField(
            GraphQLNonNull(GraphQLString),
            description='The id of the droid.'),
        'name': GraphQLField(
            GraphQLString,
            description='The name of the droid.'),
        'friends': GraphQLField(
            GraphQLList(character_interface),
            description='The friends of the droid,'
                        ' or an empty list if they have none.',
            resolve=get_friends,
        ),
        'appearsIn': GraphQLField(
            GraphQLList(episode_enum),
            description='Which movies they appear in.'),
        'secretBackstory': GraphQLField(
            GraphQLString,
            resolve=get_secret_backstory,
            description='Construction date and the name of the designer.'),
        'primaryFunction': GraphQLField(
            GraphQLString,
            description='The primary function of the droid.')
        },
        interfaces=[character_interface],
        description='A mechanical creature in the Star Wars universe.')

Now that we have defined all used result types, we can construct the ``Query`` type for
our schema::

    query_type = GraphQLObjectType('Query', lambda: {
        'hero': GraphQLField(character_interface, args={
            'episode': GraphQLArgument(episode_enum, description=(
                'If omitted, returns the hero of the whole saga.'
                ' If provided, returns the hero of that particular episode.'))},
            resolve=get_hero),
        'human': GraphQLField(human_type, args={
            'id': GraphQLArgument(
                GraphQLNonNull(GraphQLString), description='id of the human')},
            resolve=get_human),
        'droid': GraphQLField(droid_type, args={
            'id': GraphQLArgument(
                GraphQLNonNull(GraphQLString), description='id of the droid')},
            resolve=get_droid)})


Using our query type we can define our schema::

    schema = GraphQLSchema(query_type)

Note that you can also pass a mutation type and a subscription type as additional
arguments to the :class:`GraphQLSchema`.
