from __future__ import annotations

from graphql.execution import execute_sync
from graphql.language import parse
from graphql.type import (
    GraphQLBoolean,
    GraphQLField,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
)


class Dog:
    name: str
    barks: bool
    mother: Dog | None
    father: Dog | None
    progeny: list[Dog]

    def __init__(self, name: str, barks: bool):
        self.name = name
        self.barks = barks
        self.mother = None
        self.father = None
        self.progeny = []


class Cat:
    name: str
    meows: bool
    mother: Cat | None
    father: Cat | None
    progeny: list[Cat]

    def __init__(self, name: str, meows: bool):
        self.name = name
        self.meows = meows
        self.mother = None
        self.father = None
        self.progeny = []


class Person:
    name: str
    pets: list[Dog | Cat] | None
    friends: list[Dog | Cat | Person] | None

    def __init__(
        self,
        name: str,
        pets: list[Dog | Cat] | None = None,
        friends: list[Dog | Cat | Person] | None = None,
    ):
        self.name = name
        self.pets = pets
        self.friends = friends


NamedType = GraphQLInterfaceType("Named", {"name": GraphQLField(GraphQLString)})

LifeType = GraphQLInterfaceType(
    "Life",
    lambda: {"progeny": GraphQLField(GraphQLList(LifeType))},  # type: ignore
)

MammalType = GraphQLInterfaceType(
    "Mammal",
    lambda: {
        "progeny": GraphQLField(GraphQLList(MammalType)),  # type: ignore
        "mother": GraphQLField(MammalType),  # type: ignore
        "father": GraphQLField(MammalType),  # type: ignore
    },
    interfaces=[LifeType],
)

DogType = GraphQLObjectType(
    "Dog",
    lambda: {
        "name": GraphQLField(GraphQLString),
        "barks": GraphQLField(GraphQLBoolean),
        "progeny": GraphQLField(GraphQLList(DogType)),  # type: ignore
        "mother": GraphQLField(DogType),  # type: ignore
        "father": GraphQLField(DogType),  # type: ignore
    },
    interfaces=[MammalType, LifeType, NamedType],
    is_type_of=lambda value, _info: isinstance(value, Dog),
)

CatType = GraphQLObjectType(
    "Cat",
    lambda: {
        "name": GraphQLField(GraphQLString),
        "meows": GraphQLField(GraphQLBoolean),
        "progeny": GraphQLField(GraphQLList(CatType)),  # type: ignore
        "mother": GraphQLField(CatType),  # type: ignore
        "father": GraphQLField(CatType),  # type: ignore
    },
    interfaces=[MammalType, LifeType, NamedType],
    is_type_of=lambda value, _info: isinstance(value, Cat),
)


def resolve_pet_type(value, _info, _type):
    if isinstance(value, Dog):
        return DogType.name
    if isinstance(value, Cat):
        return CatType.name

    # Not reachable. All possible types have been considered.
    assert False, "Unexpected pet type"  # pragma: no cover


PetType = GraphQLUnionType("Pet", [DogType, CatType], resolve_type=resolve_pet_type)

PersonType = GraphQLObjectType(
    "Person",
    lambda: {
        "name": GraphQLField(GraphQLString),
        "pets": GraphQLField(GraphQLList(PetType)),
        "friends": GraphQLField(GraphQLList(NamedType)),
        "progeny": GraphQLField(GraphQLList(PersonType)),  # type: ignore
        "mother": GraphQLField(PersonType),  # type: ignore
        "father": GraphQLField(PersonType),  # type: ignore
    },
    interfaces=[NamedType, MammalType, LifeType],
    is_type_of=lambda value, _info: isinstance(value, Person),
)

schema = GraphQLSchema(PersonType, types=[PetType])

garfield = Cat("Garfield", False)
garfield.mother = Cat("Garfield's Mom", False)
garfield.mother.progeny = [garfield]

odie = Dog("Odie", True)
odie.mother = Dog("Odie's Mom", True)
odie.mother.progeny = [odie]

liz = Person("Liz", [], [])
john = Person("John", [garfield, odie], [liz, odie])


def describe_execute_union_and_intersection_types():
    def can_introspect_on_union_and_intersection_types():
        document = parse(
            """
            {
              Named: __type(name: "Named") {
                kind
                name
                fields { name }
                interfaces { name }
                possibleTypes { name }
                enumValues { name }
                inputFields { name }
              }
              Mammal: __type(name: "Mammal") {
                kind
                name
                fields { name }
                interfaces { name }
                possibleTypes { name }
                enumValues { name }
                inputFields { name }
              }
              Pet: __type(name: "Pet") {
                kind
                name
                fields { name }
                interfaces { name }
                possibleTypes { name }
                enumValues { name }
                inputFields { name }
              }
            }
            """
        )

        assert execute_sync(schema=schema, document=document) == (
            {
                "Named": {
                    "kind": "INTERFACE",
                    "name": "Named",
                    "fields": [{"name": "name"}],
                    "interfaces": [],
                    "possibleTypes": [
                        {"name": "Dog"},
                        {"name": "Cat"},
                        {"name": "Person"},
                    ],
                    "enumValues": None,
                    "inputFields": None,
                },
                "Mammal": {
                    "kind": "INTERFACE",
                    "name": "Mammal",
                    "fields": [
                        {"name": "progeny"},
                        {"name": "mother"},
                        {"name": "father"},
                    ],
                    "interfaces": [{"name": "Life"}],
                    "possibleTypes": [
                        {"name": "Dog"},
                        {"name": "Cat"},
                        {"name": "Person"},
                    ],
                    "enumValues": None,
                    "inputFields": None,
                },
                "Pet": {
                    "kind": "UNION",
                    "name": "Pet",
                    "fields": None,
                    "interfaces": None,
                    "possibleTypes": [{"name": "Dog"}, {"name": "Cat"}],
                    "enumValues": None,
                    "inputFields": None,
                },
            },
            None,
        )

    def executes_using_union_types():
        # NOTE: This is an *invalid* query, but it should be *executable*.
        document = parse(
            """
            {
              __typename
              name
              pets {
                __typename
                name
                barks
                meows
              }
            }
            """
        )

        assert execute_sync(schema=schema, document=document, root_value=john) == (
            {
                "__typename": "Person",
                "name": "John",
                "pets": [
                    {"__typename": "Cat", "name": "Garfield", "meows": False},
                    {"__typename": "Dog", "name": "Odie", "barks": True},
                ],
            },
            None,
        )

    def executes_union_types_with_inline_fragment():
        # This is the valid version of the query in the above test.
        document = parse(
            """
            {
              __typename
              name
              pets {
                __typename
                ... on Dog {
                  name
                  barks
                }
                ... on Cat {
                  name
                  meows
                }
              }
            }
            """
        )

        assert execute_sync(schema=schema, document=document, root_value=john) == (
            {
                "__typename": "Person",
                "name": "John",
                "pets": [
                    {"__typename": "Cat", "name": "Garfield", "meows": False},
                    {"__typename": "Dog", "name": "Odie", "barks": True},
                ],
            },
            None,
        )

    def executes_using_interface_types():
        # NOTE: This is an *invalid* query, but it should be a *executable*.
        document = parse(
            """
            {
              __typename
              name
              friends {
                __typename
                name
                barks
                meows
              }
            }
            """
        )

        assert execute_sync(schema=schema, document=document, root_value=john) == (
            {
                "__typename": "Person",
                "name": "John",
                "friends": [
                    {"__typename": "Person", "name": "Liz"},
                    {"__typename": "Dog", "name": "Odie", "barks": True},
                ],
            },
            None,
        )

    def executes_interface_types_with_inline_fragment():
        # This is the valid version of the query in the above test.
        document = parse(
            """
            {
              __typename
              name
              friends {
                __typename
                name
                ... on Dog {
                  barks
                }
                ... on Cat {
                  meows
                }

                ... on Mammal {
                  mother {
                    __typename
                    ... on Dog {
                      name
                      barks
                    }
                    ... on Cat {
                      name
                      meows
                    }
                  }
                }
              }
            }
            """
        )

        assert execute_sync(schema=schema, document=document, root_value=john) == (
            {
                "__typename": "Person",
                "name": "John",
                "friends": [
                    {"__typename": "Person", "name": "Liz", "mother": None},
                    {
                        "__typename": "Dog",
                        "name": "Odie",
                        "barks": True,
                        "mother": {
                            "__typename": "Dog",
                            "name": "Odie's Mom",
                            "barks": True,
                        },
                    },
                ],
            },
            None,
        )

    def executes_interface_types_with_named_fragments():
        document = parse(
            """
            {
              __typename
              name
              friends {
                __typename
                name
                ...DogBarks
                ...CatMeows
              }
            }

            fragment  DogBarks on Dog {
              barks
            }

            fragment  CatMeows on Cat {
              meows
            }
            """
        )

        assert execute_sync(schema=schema, document=document, root_value=john) == (
            {
                "__typename": "Person",
                "name": "John",
                "friends": [
                    {"__typename": "Person", "name": "Liz"},
                    {"__typename": "Dog", "name": "Odie", "barks": True},
                ],
            },
            None,
        )

    def allows_fragment_conditions_to_be_abstract_types():
        document = parse(
            """
            {
              __typename
              name
              pets {
                ...PetFields,
                ...on Mammal {
                  mother {
                    ...ProgenyFields
                  }
                }
              }
              friends { ...FriendFields }
            }

            fragment PetFields on Pet {
              __typename
              ... on Dog {
                name
                barks
              }
              ... on Cat {
                name
                meows
              }
            }

            fragment FriendFields on Named {
              __typename
              name
              ... on Dog {
                barks
              }
              ... on Cat {
                meows
              }
            }

            fragment ProgenyFields on Life {
              progeny {
                __typename
              }
            }
            """
        )

        assert execute_sync(schema=schema, document=document, root_value=john) == (
            {
                "__typename": "Person",
                "name": "John",
                "pets": [
                    {
                        "__typename": "Cat",
                        "name": "Garfield",
                        "meows": False,
                        "mother": {"progeny": [{"__typename": "Cat"}]},
                    },
                    {
                        "__typename": "Dog",
                        "name": "Odie",
                        "barks": True,
                        "mother": {"progeny": [{"__typename": "Dog"}]},
                    },
                ],
                "friends": [
                    {"__typename": "Person", "name": "Liz"},
                    {"__typename": "Dog", "name": "Odie", "barks": True},
                ],
            },
            None,
        )

    def gets_execution_info_in_resolver():
        encountered = {}

        def resolve_type(_source, info, _type):
            encountered["context"] = info.context
            encountered["schema"] = info.schema
            encountered["root_value"] = info.root_value
            return PersonType2.name

        NamedType2 = GraphQLInterfaceType(
            "Named", {"name": GraphQLField(GraphQLString)}, resolve_type=resolve_type
        )

        PersonType2 = GraphQLObjectType(
            "Person",
            {
                "name": GraphQLField(GraphQLString),
                "friends": GraphQLField(GraphQLList(NamedType2)),
            },
            interfaces=[NamedType2],
        )

        schema2 = GraphQLSchema(PersonType2)
        document = parse("{ name, friends { name } }")
        root_value = Person("John", [], [liz])
        context_value = {"authToken": "123abc"}

        assert execute_sync(
            schema=schema2,
            document=document,
            root_value=root_value,
            context_value=context_value,
        ) == (
            {"name": "John", "friends": [{"name": "Liz"}]},
            None,
        )

        assert encountered == {
            "schema": schema2,
            "root_value": root_value,
            "context": context_value,
        }
