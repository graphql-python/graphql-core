from typing import NamedTuple

from pytest import mark  # type: ignore

from graphql import graphql
from graphql.error import format_error
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
    woofs: bool


class Cat(NamedTuple):

    name: str
    meows: bool


class Human(NamedTuple):

    name: str


async def is_type_of_error(*_args):
    raise RuntimeError("We are testing this error")


def get_is_type_of(type_):
    async def is_type_of(obj, _info):
        return isinstance(obj, type_)

    return is_type_of


def get_type_resolver(types):
    async def resolve(obj, _info, _type):
        return resolve_thunk(types).get(obj.__class__)

    return resolve


def resolve_thunk(thunk):
    return thunk() if callable(thunk) else thunk


def describe_execute_handles_asynchronous_execution_of_abstract_types():
    @mark.asyncio
    async def is_type_of_used_to_resolve_runtime_type_for_interface():
        PetType = GraphQLInterfaceType("Pet", {"name": GraphQLField(GraphQLString)})

        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
            is_type_of=get_is_type_of(Dog),
        )

        CatType = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
            is_type_of=get_is_type_of(Cat),
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(PetType),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                        ],
                    )
                },
            ),
            types=[CatType, DogType],
        )

        query = """
            {
              pets {
                name
                ... on Dog {
                  woofs
                }
                ... on Cat {
                  meows
                }
              }
            }
            """

        result = await graphql(schema, query)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    @mark.asyncio
    async def is_type_of_with_async_error():
        PetType = GraphQLInterfaceType("Pet", {"name": GraphQLField(GraphQLString)})

        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
            is_type_of=is_type_of_error,
        )

        CatType = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
            is_type_of=get_is_type_of(Cat),
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(PetType),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                        ],
                    )
                },
            ),
            types=[CatType, DogType],
        )

        query = """
            {
              pets {
                name
                ... on Dog {
                  woofs
                }
                ... on Cat {
                  meows
                }
              }
            }
            """

        result = await graphql(schema, query)
        # Note: we get two errors, because first all types are resolved
        # and only then they are checked sequentially
        assert result.data == {"pets": [None, None]}
        assert list(map(format_error, result.errors)) == [
            {
                "message": "We are testing this error",
                "locations": [(3, 15)],
                "path": ["pets", 0],
            },
            {
                "message": "We are testing this error",
                "locations": [(3, 15)],
                "path": ["pets", 1],
            },
        ]

    @mark.asyncio
    async def is_type_of_used_to_resolve_runtime_type_for_union():
        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            is_type_of=get_is_type_of(Dog),
        )

        CatType = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            is_type_of=get_is_type_of(Cat),
        )

        PetType = GraphQLUnionType("Pet", [CatType, DogType])

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(PetType),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                        ],
                    )
                },
            )
        )

        query = """
            {
              pets {
                ... on Dog {
                  name
                  woofs
                }
                ... on Cat {
                  name
                  meows
                }
              }
            }
            """

        result = await graphql(schema, query)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    @mark.asyncio
    async def resolve_type_on_interface_yields_useful_error():
        CatType: GraphQLObjectType
        DogType: GraphQLObjectType
        HumanType: GraphQLObjectType

        PetType = GraphQLInterfaceType(
            "Pet",
            {"name": GraphQLField(GraphQLString)},
            resolve_type=get_type_resolver(
                lambda: {Dog: DogType, Cat: CatType, Human: HumanType}
            ),
        )

        HumanType = GraphQLObjectType("Human", {"name": GraphQLField(GraphQLString)})

        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
        )

        CatType = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(PetType),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                            Human("Jon"),
                        ],
                    )
                },
            ),
            types=[CatType, DogType],
        )

        query = """
            {
              pets {
                name
                ... on Dog {
                  woofs
                }
                ... on Cat {
                  meows
                }
              }
            }
            """

        result = await graphql(schema, query)
        assert result.data == {
            "pets": [
                {"name": "Odie", "woofs": True},
                {"name": "Garfield", "meows": False},
                None,
            ]
        }

        assert len(result.errors) == 1
        assert format_error(result.errors[0]) == {
            "message": "Runtime Object type 'Human'"
            " is not a possible type for 'Pet'.",
            "locations": [(3, 15)],
            "path": ["pets", 2],
        }

    @mark.asyncio
    async def resolve_type_on_union_yields_useful_error():
        HumanType = GraphQLObjectType("Human", {"name": GraphQLField(GraphQLString)})

        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
        )

        CatType = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
        )

        PetType = GraphQLUnionType(
            "Pet",
            [DogType, CatType],
            resolve_type=get_type_resolver(
                {Dog: DogType, Cat: CatType, Human: HumanType}
            ),
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(PetType),
                        resolve=lambda *_: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                            Human("Jon"),
                        ],
                    )
                },
            )
        )

        query = """
            {
              pets {
                ... on Dog {
                  name
                  woofs
                }
                ... on Cat {
                  name
                  meows
                }
              }
            }
            """

        result = await graphql(schema, query)
        assert result.data == {
            "pets": [
                {"name": "Odie", "woofs": True},
                {"name": "Garfield", "meows": False},
                None,
            ]
        }

        assert len(result.errors) == 1
        assert format_error(result.errors[0]) == {
            "message": "Runtime Object type 'Human'"
            " is not a possible type for 'Pet'.",
            "locations": [(3, 15)],
            "path": ["pets", 2],
        }

    @mark.asyncio
    async def resolve_type_allows_resolving_with_type_name():
        PetType = GraphQLInterfaceType(
            "Pet",
            {"name": GraphQLField(GraphQLString)},
            resolve_type=get_type_resolver({Dog: "Dog", Cat: "Cat"}),
        )

        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
        )

        CatType = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(PetType),
                        resolve=lambda *_: [Dog("Odie", True), Cat("Garfield", False)],
                    )
                },
            ),
            types=[CatType, DogType],
        )

        query = """{
          pets {
            name
            ... on Dog {
              woofs
            }
            ... on Cat {
              meows
            }
          }
        }"""

        result = await graphql(schema, query)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    @mark.asyncio
    async def resolve_type_can_be_caught():
        PetType = GraphQLInterfaceType(
            "Pet", {"name": GraphQLField(GraphQLString)}, resolve_type=is_type_of_error
        )

        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
        )

        CatType = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[PetType],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(PetType),
                        resolve=lambda *_: [Dog("Odie", True), Cat("Garfield", False)],
                    )
                },
            ),
            types=[CatType, DogType],
        )

        query = """{
          pets {
            name
            ... on Dog {
              woofs
            }
            ... on Cat {
              meows
            }
          }
        }"""

        result = await graphql(schema, query)
        assert result == (
            {"pets": [None, None]},
            [
                {
                    "message": "We are testing this error",
                    "locations": [(2, 11)],
                    "path": ["pets", 0],
                },
                {
                    "message": "We are testing this error",
                    "locations": [(2, 11)],
                    "path": ["pets", 1],
                },
            ],
        )
