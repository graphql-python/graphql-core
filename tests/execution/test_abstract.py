from typing import NamedTuple

from graphql import graphql_sync
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


def get_is_type_of(type_):
    def is_type_of(obj, _info):
        return isinstance(obj, type_)

    return is_type_of


def get_type_resolver(types):
    def resolve(obj, _info, _type):
        return resolve_thunk(types)[obj.__class__]

    return resolve


def resolve_thunk(thunk):
    return thunk() if callable(thunk) else thunk


def describe_execute_handles_synchronous_execution_of_abstract_types():
    def is_type_of_used_to_resolve_runtime_type_for_interface():
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

        result = graphql_sync(schema, query)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    def is_type_of_used_to_resolve_runtime_type_for_union():
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

        result = graphql_sync(schema, query)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    def resolve_type_on_interface_yields_useful_error():
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

        result = graphql_sync(schema, query)
        assert result.data == {
            "pets": [
                {"name": "Odie", "woofs": True},
                {"name": "Garfield", "meows": False},
                None,
            ]
        }

        assert result.errors
        assert len(result.errors) == 1
        assert format_error(result.errors[0]) == {
            "message": "Runtime Object type 'Human'"
            " is not a possible type for 'Pet'.",
            "locations": [{"line": 3, "column": 15}],
            "path": ["pets", 2],
        }

    def resolve_type_on_union_yields_useful_error():
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

        result = graphql_sync(schema, query)
        assert result.data == {
            "pets": [
                {"name": "Odie", "woofs": True},
                {"name": "Garfield", "meows": False},
                None,
            ]
        }

        assert result.errors
        assert len(result.errors) == 1
        assert format_error(result.errors[0]) == {
            "message": "Runtime Object type 'Human'"
            " is not a possible type for 'Pet'.",
            "locations": [{"line": 3, "column": 15}],
            "path": ["pets", 2],
        }

    def returning_invalid_value_from_resolve_type_yields_useful_error():
        foo_interface = GraphQLInterfaceType(
            "FooInterface",
            {"bar": GraphQLField(GraphQLString)},
            resolve_type=lambda *_args: [],  # type: ignore
        )

        foo_object = GraphQLObjectType(
            "FooObject",
            {"bar": GraphQLField(GraphQLString)},
            interfaces=[foo_interface],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {"foo": GraphQLField(foo_interface, resolve=lambda *_args: "dummy")},
            ),
            types=[foo_object],
        )

        result = graphql_sync(schema, "{ foo { bar } }")

        assert result == (
            {"foo": None},
            [
                {
                    "message": "Abstract type 'FooInterface' must resolve to an"
                    " Object type at runtime for field 'Query.foo' with value 'dummy',"
                    " received '[]'. Either the 'FooInterface' type should provide"
                    " a 'resolve_type' function or each possible type"
                    " should provide an 'is_type_of' function.",
                    "locations": [(1, 3)],
                    "path": ["foo"],
                }
            ],
        )

    def missing_both_resolve_type_and_is_type_of_yields_useful_error():
        foo_interface = GraphQLInterfaceType(
            "FooInterface", {"bar": GraphQLField(GraphQLString)}
        )

        foo_object = GraphQLObjectType(
            "FooObject",
            {"bar": GraphQLField(GraphQLString)},
            interfaces=[foo_interface],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {"foo": GraphQLField(foo_interface, resolve=lambda *_args: "dummy")},
            ),
            types=[foo_object],
        )

        result = graphql_sync(schema, "{ foo { bar } }")

        assert result == (
            {"foo": None},
            [
                {
                    "message": "Abstract type 'FooInterface' must resolve to an"
                    " Object type at runtime for field 'Query.foo' with value 'dummy',"
                    " received 'None'. Either the 'FooInterface' type should provide"
                    " a 'resolve_type' function or each possible type"
                    " should provide an 'is_type_of' function.",
                    "locations": [(1, 3)],
                    "path": ["foo"],
                }
            ],
        )

    def resolve_type_allows_resolving_with_type_name():
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
            }"""

        result = graphql_sync(schema, query)
        assert result == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )
