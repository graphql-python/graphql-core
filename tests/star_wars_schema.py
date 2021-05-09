"""Star Wars GraphQL schema

This is designed to be an end-to-end test, demonstrating the full GraphQL stack.

We will create a GraphQL schema that describes the major characters in the original
Star Wars trilogy.

NOTE: This may contain spoilers for the original Star Wars trilogy.

Using our shorthand to describe type systems, the type system for our Star Wars example
is::

    enum Episode { NEW_HOPE, EMPIRE, JEDI }

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
"""

from graphql.type import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from tests.star_wars_data import (
    get_droid,
    get_friends,
    get_hero,
    get_human,
    get_secret_backstory,
)

__all__ = ["star_wars_schema"]

# We begin by setting up our schema.

# The original trilogy consists of three movies.
#
# This implements the following type system shorthand:
#   enum Episode { NEW_HOPE, EMPIRE, JEDI }

episode_enum = GraphQLEnumType(
    "Episode",
    {
        "NEW_HOPE": GraphQLEnumValue(4, description="Released in 1977."),
        "EMPIRE": GraphQLEnumValue(5, description="Released in 1980."),
        "JEDI": GraphQLEnumValue(6, description="Released in 1983."),
    },
    description="One of the films in the Star Wars Trilogy",
)

# Characters in the Star Wars trilogy are either humans or droids.
#
# This implements the following type system shorthand:
#   interface Character {
#     id: String!
#     name: String
#     friends: [Character]
#     appearsIn: [Episode]
#     secretBackstory: String

human_type: GraphQLObjectType
droid_type: GraphQLObjectType

character_interface: GraphQLInterfaceType = GraphQLInterfaceType(
    "Character",
    lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the character."
        ),
        "name": GraphQLField(GraphQLString, description="The name of the character."),
        "friends": GraphQLField(
            GraphQLList(character_interface),
            description="The friends of the character,"
            " or an empty list if they have none.",
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum), description="Which movies they appear in."
        ),
        "secretBackstory": GraphQLField(
            GraphQLString, description="All secrets about their past."
        ),
    },
    resolve_type=lambda character, _info, _type: {
        "Human": human_type.name,
        "Droid": droid_type.name,
    }[character.type],
    description="A character in the Star Wars Trilogy",
)

# We define our human type, which implements the character interface.
#
# This implements the following type system shorthand:
#   type Human : Character {
#     id: String!
#     name: String
#     friends: [Character]
#     appearsIn: [Episode]
#     secretBackstory: String
#   }

human_type = GraphQLObjectType(
    "Human",
    lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the human."
        ),
        "name": GraphQLField(GraphQLString, description="The name of the human."),
        "friends": GraphQLField(
            GraphQLList(character_interface),
            description="The friends of the human,"
            " or an empty list if they have none.",
            resolve=lambda human, _info: get_friends(human),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum), description="Which movies they appear in."
        ),
        "homePlanet": GraphQLField(
            GraphQLString,
            description="The home planet of the human, or null if unknown.",
        ),
        "secretBackstory": GraphQLField(
            GraphQLString,
            resolve=lambda human, _info: get_secret_backstory(human),
            description="Where are they from and how they came to be who they are.",
        ),
    },
    interfaces=[character_interface],
    description="A humanoid creature in the Star Wars universe.",
)

# The other type of character in Star Wars is a droid.
#
# This implements the following type system shorthand:
#   type Droid : Character {
#     id: String!
#     name: String
#     friends: [Character]
#     appearsIn: [Episode]
#     secretBackstory: String
#     primaryFunction: String
#   }

droid_type = GraphQLObjectType(
    "Droid",
    lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the droid."
        ),
        "name": GraphQLField(GraphQLString, description="The name of the droid."),
        "friends": GraphQLField(
            GraphQLList(character_interface),
            description="The friends of the droid,"
            " or an empty list if they have none.",
            resolve=lambda droid, _info: get_friends(droid),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum), description="Which movies they appear in."
        ),
        "secretBackstory": GraphQLField(
            GraphQLString,
            resolve=lambda droid, _info: get_secret_backstory(droid),
            description="Construction date and the name of the designer.",
        ),
        "primaryFunction": GraphQLField(
            GraphQLString, description="The primary function of the droid."
        ),
    },
    interfaces=[character_interface],
    description="A mechanical creature in the Star Wars universe.",
)

# This is the type that will be the root of our query, and the
# entry point into our schema. It gives us the ability to fetch
# objects by their IDs, as well as to fetch the undisputed hero
# of the Star Wars trilogy, R2-D2, directly.
#
# This implements the following type system shorthand:
#   type Query {
#     hero(episode: Episode): Character
#     human(id: String!): Human
#     droid(id: String!): Droid
#   }

# noinspection PyShadowingBuiltins
query_type = GraphQLObjectType(
    "Query",
    lambda: {
        "hero": GraphQLField(
            character_interface,
            args={
                "episode": GraphQLArgument(
                    episode_enum,
                    description=(
                        "If omitted, returns the hero of the whole saga."
                        " If provided, returns the hero of that particular episode."
                    ),
                )
            },
            resolve=lambda _source, _info, episode=None: get_hero(episode),
        ),
        "human": GraphQLField(
            human_type,
            args={
                "id": GraphQLArgument(
                    GraphQLNonNull(GraphQLString), description="id of the human"
                )
            },
            resolve=lambda _source, _info, id: get_human(id),
        ),
        "droid": GraphQLField(
            droid_type,
            args={
                "id": GraphQLArgument(
                    GraphQLNonNull(GraphQLString), description="id of the droid"
                )
            },
            resolve=lambda _source, _info, id: get_droid(id),
        ),
    },
)

# Finally, we construct our schema (whose starting query type is the query
# type we defined above) and export it.

star_wars_schema = GraphQLSchema(query_type, types=[human_type, droid_type])
