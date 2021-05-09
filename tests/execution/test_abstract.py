from collections import defaultdict
from inspect import isawaitable
from typing import Any, NamedTuple, Optional

from pytest import mark

from graphql.execution import execute, execute_sync, ExecutionResult
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
from graphql.utilities import build_schema


def sync_and_async(spec):
    """Decorator for running a test synchronously and asynchronously."""
    return mark.asyncio(
        mark.parametrize("sync", (True, False), ids=("sync", "async"))(spec)
    )


def access_variants(spec):
    """Decorator for tests with dict and object access, including inheritance."""
    return mark.asyncio(
        mark.parametrize("access", ("dict", "object", "inheritance"))(spec)
    )


async def execute_query(
    sync: bool, schema: GraphQLSchema, query: str, root_value: Any = None
) -> ExecutionResult:
    """Execute the query against the given schema synchronously or asynchronously."""
    assert isinstance(sync, bool)
    assert isinstance(schema, GraphQLSchema)
    assert isinstance(query, str)
    document = parse(query)
    result = (execute_sync if sync else execute)(
        schema, document, root_value
    )  # type: ignore
    if not sync and isawaitable(result):
        result = await result
    assert isinstance(result, ExecutionResult)
    return result


def get_is_type_of(type_, sync=True):
    """Get a sync or async is_type_of function for the given type."""
    if sync:

        def is_type_of(obj, _info):
            return isinstance(obj, type_)

    else:

        async def is_type_of(obj, _info):
            return isinstance(obj, type_)

    return is_type_of


def get_type_resolver(types, sync=True):
    """Get a sync or async type resolver for the given type map."""
    if sync:

        def resolve(obj, _info, _type):
            return resolve_thunk(types)[obj.__class__]

    else:

        async def resolve(obj, _info, _type):
            return resolve_thunk(types)[obj.__class__]

    return resolve


def get_type_error(sync=True):
    """Get a sync or async is_type_of or type resolver function that raises an error."""
    error = RuntimeError("We are testing this error")
    if sync:

        def type_error(*_args):
            raise error

    else:

        async def type_error(*_args):
            raise error

    return type_error


def resolve_thunk(thunk):
    return thunk() if callable(thunk) else thunk


class Dog(NamedTuple):

    name: str
    woofs: bool


class Cat(NamedTuple):

    name: str
    meows: bool


class Human(NamedTuple):

    name: str


def describe_execute_handles_synchronous_execution_of_abstract_types():
    @sync_and_async
    async def is_type_of_used_to_resolve_runtime_type_for_interface(sync):
        pet_type = GraphQLInterfaceType("Pet", {"name": GraphQLField(GraphQLString)})

        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
            is_type_of=get_is_type_of(Dog, sync),
        )

        cat_type = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
            is_type_of=get_is_type_of(Cat, sync),
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                        ],
                    )
                },
            ),
            types=[cat_type, dog_type],
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

        assert await execute_query(sync, schema, query) == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    @sync_and_async
    async def is_type_of_can_throw(sync):
        pet_type = GraphQLInterfaceType("Pet", {"name": GraphQLField(GraphQLString)})

        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
            is_type_of=get_type_error(sync),
        )

        cat_type = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
            is_type_of=None,
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                        ],
                    )
                },
            ),
            types=[dog_type, cat_type],
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

        assert await execute_query(sync, schema, query) == (
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

    @sync_and_async
    async def is_type_of_with_no_suitable_type(sync):
        pet_type = GraphQLInterfaceType("Pet", {"name": GraphQLField(GraphQLString)})

        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
            is_type_of=get_is_type_of(Cat, sync),
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
                        resolve=lambda *_args: [Dog("Odie", True)],
                    )
                },
            ),
            types=[dog_type],
        )

        query = """
            {
              pets {
                name
                ... on Dog {
                  woofs
                }
              }
            }
            """

        message = (
            "Abstract type 'Pet' must resolve to an Object type at runtime"
            " for field 'Query.pets' with value ('Odie', True), received 'None'."
            " Either the 'Pet' type should provide a 'resolve_type' function"
            " or each possible type should provide an 'is_type_of' function."
        )
        assert await execute_query(sync, schema, query) == (
            {"pets": [None]},
            [{"message": message, "locations": [(3, 15)], "path": ["pets", 0]}],
        )

    @sync_and_async
    async def is_type_of_used_to_resolve_runtime_type_for_union(sync):
        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            is_type_of=get_is_type_of(Dog, sync),
        )

        cat_type = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            is_type_of=get_is_type_of(Cat, sync),
        )

        pet_type = GraphQLUnionType("Pet", [cat_type, dog_type])

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
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

        assert await execute_query(sync, schema, query) == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    @sync_and_async
    async def resolve_type_on_interface_yields_useful_error(sync):
        cat_type: GraphQLObjectType
        dog_type: GraphQLObjectType
        human_type: GraphQLObjectType

        pet_type = GraphQLInterfaceType(
            "Pet",
            {"name": GraphQLField(GraphQLString)},
            resolve_type=get_type_resolver(
                lambda: {Dog: dog_type, Cat: cat_type, Human: human_type}, sync
            ),
        )

        human_type = GraphQLObjectType("Human", {"name": GraphQLField(GraphQLString)})

        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
        )

        cat_type = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                            Human("Jon"),
                        ],
                    )
                },
            ),
            types=[cat_type, dog_type],
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

        assert await execute_query(sync, schema, query) == (
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
                    "locations": [{"line": 3, "column": 15}],
                    "path": ["pets", 2],
                }
            ],
        )

    @sync_and_async
    async def resolve_type_on_union_yields_useful_error(sync):
        human_type = GraphQLObjectType("Human", {"name": GraphQLField(GraphQLString)})

        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
        )

        cat_type = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
        )

        pet_type = GraphQLUnionType(
            "Pet",
            [dog_type, cat_type],
            resolve_type=get_type_resolver(
                {Dog: dog_type, Cat: cat_type, Human: human_type}, sync
            ),
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
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

        assert await execute_query(sync, schema, query) == (
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
                    "locations": [{"line": 3, "column": 15}],
                    "path": ["pets", 2],
                }
            ],
        )

    @sync_and_async
    async def returning_invalid_value_from_resolve_type_yields_useful_error(sync):
        foo_interface = GraphQLInterfaceType(
            "FooInterface",
            {"bar": GraphQLField(GraphQLString)},
            # this type resolver always returns an empty list instead of a type
            resolve_type=get_type_resolver(defaultdict(list), sync),
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

        assert await execute_query(sync, schema, "{ foo { bar } }") == (
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

    @sync_and_async
    async def missing_both_resolve_type_and_is_type_of_yields_useful_error(sync):
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
                {
                    "foo": GraphQLField(
                        foo_interface,
                        resolve=lambda *_: "dummy",
                    )
                },
            ),
            types=[foo_object],
        )

        assert await execute_query(sync, schema, "{ foo { bar } }") == (
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

    @sync_and_async
    async def resolve_type_allows_resolving_with_type_name(sync):
        pet_type = GraphQLInterfaceType(
            "Pet",
            {"name": GraphQLField(GraphQLString)},
            resolve_type=get_type_resolver({Dog: "Dog", Cat: "Cat"}, sync),
        )

        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
        )

        cat_type = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
                        resolve=lambda *_: [Dog("Odie", True), Cat("Garfield", False)],
                    )
                },
            ),
            types=[cat_type, dog_type],
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

        assert await execute_query(sync, schema, query) == (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

    @sync_and_async
    async def resolve_type_can_throw(sync):
        pet_type = GraphQLInterfaceType(
            "Pet",
            {"name": GraphQLField(GraphQLString)},
            resolve_type=get_type_error(sync),
        )

        dog_type = GraphQLObjectType(
            "Dog",
            {
                "name": GraphQLField(GraphQLString),
                "woofs": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
        )

        cat_type = GraphQLObjectType(
            "Cat",
            {
                "name": GraphQLField(GraphQLString),
                "meows": GraphQLField(GraphQLBoolean),
            },
            interfaces=[pet_type],
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "pets": GraphQLField(
                        GraphQLList(pet_type),
                        resolve=lambda *_args: [
                            Dog("Odie", True),
                            Cat("Garfield", False),
                        ],
                    )
                },
            ),
            types=[dog_type, cat_type],
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

        assert await execute_query(sync, schema, query) == (
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

    def describe_using_typename_on_source_object():

        expected = (
            {
                "pets": [
                    {"name": "Odie", "woofs": True},
                    {"name": "Garfield", "meows": False},
                ]
            },
            None,
        )

        # noinspection PyShadowingNames
        def _root_value(access: str) -> Any:
            if access == "dict":
                return {
                    "pets": [
                        {"__typename": "Dog", "name": "Odie", "woofs": True},
                        {"__typename": "Cat", "name": "Garfield", "meows": False},
                    ],
                }

            if access == "object":

                class DogObject:
                    __typename = "Dog"
                    name = "Odie"
                    woofs = True

                class CatObject:
                    __typename = "Cat"
                    name = "Garfield"
                    meows = False

                class RootValueAsObject:
                    pets = [DogObject(), CatObject()]

                return RootValueAsObject()

            if access == "inheritance":

                class Pet:
                    __typename = "Pet"
                    name: Optional[str] = None

                class DogPet(Pet):
                    __typename = "Dog"
                    woofs: Optional[bool] = None

                class Odie(DogPet):
                    name = "Odie"
                    woofs = True

                class CatPet(Pet):
                    __typename = "Cat"
                    meows: Optional[bool] = None

                class Tabby(CatPet):
                    pass

                class Garfield(Tabby):
                    name = "Garfield"
                    meows = False

                class RootValueWithInheritance:
                    pets = [Odie(), Garfield()]

                return RootValueWithInheritance()

            assert False, f"Unknown access variant: {access}"  # pragma: no cover

        def describe_union_type():

            schema = build_schema(
                """
                type Query {
                  pets: [Pet]
                }

                union Pet = Cat | Dog

                type Cat {
                  name: String
                  meows: Boolean
                }

                type Dog {
                  name: String
                  woofs: Boolean
                }
                """
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

            @sync_and_async
            @access_variants
            async def resolve(sync, access):
                root_value = _root_value(access)
                assert await execute_query(sync, schema, query, root_value) == expected

        def describe_interface_type():
            schema = build_schema(
                """
                type Query {
                  pets: [Pet]
                }

                interface Pet {
                  name: String
                  }

                type Cat implements Pet {
                  name: String
                  meows: Boolean
                }

                type Dog implements Pet {
                  name: String
                  woofs: Boolean
                }
                """
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

            @sync_and_async
            @access_variants
            async def resolve(sync, access):
                root_value = _root_value(access)
                assert await execute_query(sync, schema, query, root_value) == expected
