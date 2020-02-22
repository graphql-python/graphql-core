from typing import NamedTuple

from pytest import mark  # type: ignore

from graphql import graphql
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
        return resolve_thunk(types)[obj.__class__]

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

        source = """
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

        result = await graphql(schema=schema, source=source)
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

        source = """
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

        result = await graphql(schema=schema, source=source)
        # Note: we get two errors, because first all types are resolved
        # and only then they are checked sequentially
        assert result == (
            {"pets": [None, None]},
            [
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
            ],
        )

    @mark.asyncio
    async def is_type_of_with_no_suitable_type():
        PetType = GraphQLInterfaceType("Pet", {"name": GraphQLField(GraphQLString)})

        DogType = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
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
                        resolve=lambda *_args: [Dog("Odie", True)],
                    )
                },
            ),
            types=[DogType],
        )

        source = """
            {
              pets {
                name
                ... on Dog {
                  woofs
                }
              }
            }
            """

        result = await graphql(schema=schema, source=source)
        msg = (
            "Abstract type 'Pet' must resolve to an Object type at runtime"
            " for field 'Query.pets' with value ('Odie', True), received 'None'."
            " Either the 'Pet' type should provide a 'resolve_type' function"
            " or each possible type should provide an 'is_type_of' function."
        )
        assert result == (
            {"pets": [None]},
            [{"message": msg, "locations": [(3, 15)], "path": ["pets", 0]}],
        )

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

        source = """
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

        result = await graphql(schema=schema, source=source)
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

        source = """
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

        result = await graphql(schema=schema, source=source)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                    None,
                ]
            },
            [
                {
                    "message": "Runtime Object type 'Human'"
                    " is not a possible type for 'Pet'.",
                    "locations": [(3, 15)],
                    "path": ["pets", 2],
                }
            ],
        )

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

        source = """
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

        result = await graphql(schema=schema, source=source)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                    None,
                ]
            },
            [
                {
                    "message": "Runtime Object type 'Human'"
                    " is not a possible type for 'Pet'.",
                    "locations": [(3, 15)],
                    "path": ["pets", 2],
                }
            ],
        )

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

        source = """{
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

        result = await graphql(schema=schema, source=source)
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

        source = """{
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

        result = await graphql(schema=schema, source=source)
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
