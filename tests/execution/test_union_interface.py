from typing import NamedTuple, Union, List

from graphql.execution import execute
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


class Dog(NamedTuple):

    name: str
    barks: bool


class Cat(NamedTuple):

    name: str
    meows: bool


class Person(NamedTuple):  # type: ignore

    name: str
    pets: List[Union[Dog, Cat]]
    friends: List[Union[Dog, Cat, "Person"]]


NamedType = GraphQLInterfaceType("Named", {"name": GraphQLField(GraphQLString)})

DogType = GraphQLObjectType(
    "Dog",
    {"name": GraphQLField(GraphQLString), "barks": GraphQLField(GraphQLBoolean)},
    interfaces=[NamedType],
    is_type_of=lambda value, info: isinstance(value, Dog),
)

CatType = GraphQLObjectType(
    "Cat",
    {"name": GraphQLField(GraphQLString), "meows": GraphQLField(GraphQLBoolean)},
    interfaces=[NamedType],
    is_type_of=lambda value, info: isinstance(value, Cat),
)


def resolve_pet_type(value, _info, _type):
    if isinstance(value, Dog):
        return DogType
    if isinstance(value, Cat):
        return CatType


PetType = GraphQLUnionType("Pet", [DogType, CatType], resolve_type=resolve_pet_type)

PersonType = GraphQLObjectType(
    "Person",
    {
        "name": GraphQLField(GraphQLString),
        "pets": GraphQLField(GraphQLList(PetType)),
        "friends": GraphQLField(GraphQLList(NamedType)),
    },
    interfaces=[NamedType],
    is_type_of=lambda value, _info: isinstance(value, Person),
)

schema = GraphQLSchema(PersonType, types=[PetType])

garfield = Cat("Garfield", False)
odie = Dog("Odie", True)
liz = Person("Liz", [], [])
john = Person("John", [garfield, odie], [liz, odie])


def describe_execute_union_and_intersection_types():
    def can_introspect_on_union_and_intersection_types():
        ast = parse(
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

        assert execute(schema, ast) == (
            {
                "Named": {
                    "kind": "INTERFACE",
                    "name": "Named",
                    "fields": [{"name": "name"}],
                    "interfaces": None,
                    "possibleTypes": [
                        {"name": "Person"},
                        {"name": "Dog"},
                        {"name": "Cat"},
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
        ast = parse(
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

        assert execute(schema, ast, john) == (
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
        ast = parse(
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

        assert execute(schema, ast, john) == (
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
        ast = parse(
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

        assert execute(schema, ast, john) == (
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
        ast = parse(
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
              }
            }
            """
        )

        assert execute(schema, ast, john) == (
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
        ast = parse(
            """
            {
              __typename
              name
              pets { ...PetFields }
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
            """
        )

        assert execute(schema, ast, john) == (
            {
                "__typename": "Person",
                "name": "John",
                "pets": [
                    {"__typename": "Cat", "name": "Garfield", "meows": False},
                    {"__typename": "Dog", "name": "Odie", "barks": True},
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

        def resolve_type(_obj, info, _type):
            encountered["context"] = info.context
            encountered["schema"] = info.schema
            encountered["root_value"] = info.root_value
            return PersonType2

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

        john2 = Person("John", [], [liz])

        context = {"authToken": "123abc"}

        ast = parse("{ name, friends { name } }")

        assert execute(schema2, ast, john2, context) == (
            {"name": "John", "friends": [{"name": "Liz"}]},
            None,
        )

        assert encountered == {
            "schema": schema2,
            "root_value": john2,
            "context": context,
        }
