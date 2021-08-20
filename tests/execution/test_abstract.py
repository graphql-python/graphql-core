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


class Dog(NamedTuple):

    name: str
    woofs: bool


class Cat(NamedTuple):

    name: str
    meows: bool


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
        # added in GraphQL-core to improve coverage
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
            " for field 'Query.pets'."
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

    def resolve_type_on_interface_yields_useful_error():
        schema = build_schema(
            """
            type Query {
              pet: Pet
            }

            interface Pet {
              name: String
            }

            type Cat implements Pet {
              name: String
            }

            type Dog implements Pet {
              name: String
            }
            """
        )

        document = parse(
            """
            {
              pet {
                name
              }
            }
            """
        )

        def expect_error(for_type_name: Any, message: str) -> None:
            root_value = {"pet": {"__typename": for_type_name}}
            result = execute_sync(schema, document, root_value)
            expected = (
                {"pet": None},
                [{"message": message, "locations": [(3, 15)], "path": ["pet"]}],
            )
            assert result == expected

        expect_error(
            None,
            "Abstract type 'Pet' must resolve"
            " to an Object type at runtime for field 'Query.pet'."
            " Either the 'Pet' type should provide a 'resolve_type' function"
            " or each possible type should provide an 'is_type_of' function.",
        )

        expect_error(
            "Human",
            "Abstract type 'Pet' was resolved to a type 'Human'"
            " that does not exist inside the schema.",
        )

        expect_error(
            "String", "Abstract type 'Pet' was resolved to a non-object type 'String'."
        )

        expect_error(
            "__Schema",
            "Runtime Object type '__Schema' is not a possible type for 'Pet'.",
        )

        # workaround since we can't inject resolve_type into SDL
        schema.get_type("Pet").resolve_type = lambda *_args: []  # type: ignore

        expect_error(
            None,
            "Abstract type 'Pet' must resolve"
            " to an Object type at runtime for field 'Query.pet'"
            " with value {'__typename': None}, received '[]'.",
        )
