"""User registry demo.

This is an additional end-to-end test and demo for running the basic GraphQL
operations on a simulated user registry database backend.
"""

from asyncio import sleep, wait
from collections import defaultdict
from enum import Enum
from inspect import isawaitable
from typing import Any, Dict, List, NamedTuple, Optional

try:
    from asyncio import create_task
except ImportError:  # Python < 3.7
    create_task = None  # type: ignore

from pytest import fixture, mark

from graphql import (
    graphql,
    parse,
    subscribe,
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLField,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from graphql.pyutils import SimplePubSub, SimplePubSubIterator
from graphql.subscription.map_async_iterator import MapAsyncIterator


class User(NamedTuple):
    """A simple user object class."""

    firstName: str
    lastName: str
    tweets: Optional[int]
    id: Optional[str] = None
    verified: bool = False


class MutationEnum(Enum):
    """Mutation event type"""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class UserRegistry:
    """Simulation of a user registry with asynchronous database backend access."""

    def __init__(self, **users):
        self._registry: Dict[str, User] = users
        self._pubsub = defaultdict(SimplePubSub)

    async def get(self, id_: str) -> Optional[User]:
        """Get a user object from the registry"""
        await sleep(0)
        return self._registry.get(id_)

    async def create(self, **kwargs) -> User:
        """Create a user object in the registry"""
        await sleep(0)
        id_ = str(len(self._registry))
        user = User(id=id_, **kwargs)
        self._registry[id_] = user
        self.emit_event(MutationEnum.CREATED, user)
        return user

    async def update(self, id_: str, **kwargs) -> User:
        """Update a user object in the registry"""
        await sleep(0)
        # noinspection PyProtectedMember
        user = self._registry[id_]._replace(**kwargs)
        self._registry[id_] = user
        self.emit_event(MutationEnum.UPDATED, user)
        return user

    async def delete(self, id_: str) -> User:
        """Delete a user object in the registry"""
        await sleep(0)
        user = self._registry.pop(id_)
        self.emit_event(MutationEnum.DELETED, user)
        return user

    def emit_event(self, mutation: MutationEnum, user: User) -> None:
        """Emit mutation events for the given object and its class"""
        payload = {"user": user, "mutation": mutation.value}
        self._pubsub[None].emit(payload)  # notify all user subscriptions
        self._pubsub[user.id].emit(payload)  # notify single user subscriptions

    def event_iterator(self, id_: Optional[str]) -> SimplePubSubIterator:
        return self._pubsub[id_].get_subscriber()


mutation_type = GraphQLEnumType("MutationType", MutationEnum)

user_type = GraphQLObjectType(
    "UserType",
    {
        "id": GraphQLField(GraphQLNonNull(GraphQLID)),
        "firstName": GraphQLField(GraphQLNonNull(GraphQLString)),
        "lastName": GraphQLField(GraphQLNonNull(GraphQLString)),
        "tweets": GraphQLField(GraphQLInt),
        "verified": GraphQLField(GraphQLNonNull(GraphQLBoolean)),
    },
)

user_input_type = GraphQLInputObjectType(
    "UserInputType",
    {
        "firstName": GraphQLInputField(GraphQLNonNull(GraphQLString)),
        "lastName": GraphQLInputField(GraphQLNonNull(GraphQLString)),
        "tweets": GraphQLInputField(GraphQLInt),
        "verified": GraphQLInputField(GraphQLBoolean),
    },
)

subscription_user_type = GraphQLObjectType(
    "SubscriptionUserType",
    {"mutation": GraphQLField(mutation_type), "user": GraphQLField(user_type)},
)


async def resolve_user(_root, info, **args):
    """Resolver function for fetching a user object"""
    return await info.context["registry"].get(args["id"])


async def resolve_create_user(_root, info, data):
    """Resolver function for creating a user object"""
    user = await info.context["registry"].create(**data)
    return user


# noinspection PyShadowingBuiltins
async def resolve_update_user(_root, info, id, data):
    """Resolver function for updating a user object"""
    user = await info.context["registry"].update(id, **data)
    return user


# noinspection PyShadowingBuiltins
async def resolve_delete_user(_root, info, id):
    """Resolver function for deleting a user object"""
    user = await info.context["registry"].get(id)
    await info.context["registry"].delete(user.id)
    return True


# noinspection PyShadowingBuiltins
async def subscribe_user(_root, info, id=None):
    """Subscribe to mutations of a specific user object or all user objects"""
    async_iterator = info.context["registry"].event_iterator(id)
    async for event in async_iterator:
        yield await event if isawaitable(event) else event


# noinspection PyShadowingBuiltins,PyUnusedLocal
async def resolve_subscription_user(event, info, id):
    """Resolver function for user subscriptions"""
    user = event["user"]
    mutation = MutationEnum(event["mutation"]).value
    return {"user": user, "mutation": mutation}


schema = GraphQLSchema(
    query=GraphQLObjectType(
        "RootQueryType",
        {
            "User": GraphQLField(
                user_type, args={"id": GraphQLArgument(GraphQLID)}, resolve=resolve_user
            )
        },
    ),
    mutation=GraphQLObjectType(
        "RootMutationType",
        {
            "createUser": GraphQLField(
                user_type,
                args={"data": GraphQLArgument(GraphQLNonNull(user_input_type))},
                resolve=resolve_create_user,
            ),
            "deleteUser": GraphQLField(
                GraphQLBoolean,
                args={"id": GraphQLArgument(GraphQLNonNull(GraphQLID))},
                resolve=resolve_delete_user,
            ),
            "updateUser": GraphQLField(
                user_type,
                args={
                    "id": GraphQLArgument(GraphQLNonNull(GraphQLID)),
                    "data": GraphQLArgument(GraphQLNonNull(user_input_type)),
                },
                resolve=resolve_update_user,
            ),
        },
    ),
    subscription=GraphQLObjectType(
        "RootSubscriptionType",
        {
            "subscribeUser": GraphQLField(
                subscription_user_type,
                args={"id": GraphQLArgument(GraphQLID)},
                subscribe=subscribe_user,
                resolve=resolve_subscription_user,
            )
        },
    ),
)


@fixture
def context():
    return {"registry": UserRegistry()}


def describe_query():
    @mark.asyncio
    async def query_user(context):
        user = await context["registry"].create(
            firstName="John", lastName="Doe", tweets=42, verified=True
        )

        query = """
            query ($userId: ID!) {
                User(id: $userId) {
                    id, firstName, lastName, tweets, verified
                }
            }
            """

        variables = {"userId": user.id}
        result = await graphql(
            schema, query, context_value=context, variable_values=variables
        )

        assert not result.errors
        assert result.data == {
            "User": {
                "id": user.id,
                "firstName": user.firstName,
                "lastName": user.lastName,
                "tweets": user.tweets,
                "verified": user.verified,
            }
        }


def describe_mutation():
    @mark.asyncio
    async def create_user(context):
        received = {}

        def subscriber(event_name):
            def receive(msg):
                received[event_name] = msg

            return receive

        # noinspection PyProtectedMember
        pubsub = context["registry"]._pubsub
        pubsub[None].subscribers.add(subscriber("User"))
        pubsub["0"].subscribers.add(subscriber("User 0"))

        query = """
            mutation ($userData: UserInputType!) {
                createUser(data: $userData) {
                    id, firstName, lastName, tweets, verified
                }
            }
            """
        user_data = dict(firstName="John", lastName="Doe", tweets=42, verified=True)
        variables = {"userData": user_data}
        result = await graphql(
            schema, query, context_value=context, variable_values=variables
        )

        user = await context["registry"].get("0")
        assert user == User(id="0", **user_data)  # type: ignore

        assert result.errors is None
        assert result.data == {
            "createUser": {
                "id": user.id,
                "firstName": user.firstName,
                "lastName": user.lastName,
                "tweets": user.tweets,
                "verified": user.verified,
            }
        }

        assert received == {
            "User": {"user": user, "mutation": MutationEnum.CREATED.value},
            "User 0": {"user": user, "mutation": MutationEnum.CREATED.value},
        }

    @mark.asyncio
    async def update_user(context):
        received = {}

        def subscriber(event_name):
            def receive(msg):
                received[event_name] = msg

            return receive

        # noinspection PyProtectedMember
        pubsub = context["registry"]._pubsub
        pubsub[None].subscribers.add(subscriber("User"))
        pubsub["0"].subscribers.add(subscriber("User 0"))

        user = await context["registry"].create(
            firstName="John", lastName="Doe", tweets=42, verified=True
        )
        user_data = {
            "firstName": "Jane",
            "lastName": "Roe",
            "tweets": 210,
            "verified": False,
        }

        query = """
            mutation ($userId: ID!, $userData: UserInputType!) {
                updateUser(id: $userId, data: $userData) {
                    id, firstName, lastName, tweets, verified
                }
            }"""

        variables = {"userId": user.id, "userData": user_data}
        result = await graphql(
            schema, query, context_value=context, variable_values=variables
        )

        user = await context["registry"].get("0")
        assert user == User(id="0", **user_data)  # type: ignore

        assert result.errors is None
        assert result.data == {
            "updateUser": {
                "id": user.id,
                "firstName": user.firstName,
                "lastName": user.lastName,
                "tweets": user.tweets,
                "verified": user.verified,
            }
        }

        assert received == {
            "User": {"user": user, "mutation": MutationEnum.UPDATED.value},
            "User 0": {"user": user, "mutation": MutationEnum.UPDATED.value},
        }

    @mark.asyncio
    async def delete_user(context):
        received = {}

        def subscriber(name):
            def receive(msg):
                received[name] = msg

            return receive

        # noinspection PyProtectedMember
        pubsub = context["registry"]._pubsub
        pubsub[None].subscribers.add(subscriber("User"))
        pubsub["0"].subscribers.add(subscriber("User 0"))

        user = await context["registry"].create(
            firstName="John", lastName="Doe", tweets=42, verified=True
        )

        query = """
            mutation ($userId: ID!) {
                deleteUser(id: $userId)
            }
            """

        variables = {"userId": user.id}
        result = await graphql(
            schema, query, context_value=context, variable_values=variables
        )

        assert result.errors is None
        assert result.data == {"deleteUser": True}

        assert await context["registry"].get(user.id) is None

        assert received == {
            "User": {"user": user, "mutation": MutationEnum.DELETED.value},
            "User 0": {"user": user, "mutation": MutationEnum.DELETED.value},
        }


def describe_subscription():
    @mark.asyncio
    async def subscribe_to_user_mutations(context):
        query = """
            subscription ($userId: ID!) {
                subscribeUser(id: $userId) {
                    mutation
                    user { id, firstName, lastName, tweets, verified }
                }
            }
            """

        variables = {"userId": "0"}
        subscription_one = await subscribe(
            schema, parse(query), context_value=context, variable_values=variables
        )
        assert isinstance(subscription_one, MapAsyncIterator)

        query = """
            subscription {
                subscribeUser(id: null) {
                    mutation
                    user { id, firstName, lastName, tweets, verified }
                }
            }
            """

        subscription_all = await subscribe(schema, parse(query), context_value=context)
        assert isinstance(subscription_all, MapAsyncIterator)

        received_one = []
        received_all = []

        async def mutate_users():
            await sleep(0)  # make sure subscribers are running
            await graphql(
                schema,
                """
                mutation {createUser(data: {
                    firstName: "John"
                    lastName: "Doe"
                    tweets: 42
                    verified: true}) { id }
                }""",
                context_value=context,
            )
            await graphql(
                schema,
                """
                mutation {createUser(data: {
                    firstName: "James"
                    lastName: "Doe"
                    tweets: 4
                    verified: false}) { id }
                }""",
                context_value=context,
            )
            await graphql(
                schema,
                """
                mutation {updateUser(id: 0, data: {
                    firstName: "Jane"
                    lastName: "Roe"
                    tweets: 210
                    verified: false}) { id }
                }""",
                context_value=context,
            )
            await graphql(
                schema,
                """
                mutation {updateUser(id: 1, data: {
                    firstName: "Janette"
                    lastName: "Roe"
                    tweets: 20
                    verified: true}) { id }
                }""",
                context_value=context,
            )
            await graphql(
                schema,
                """
                mutation {deleteUser(id: "0")}
                """,
                context_value=context,
            )
            await graphql(
                schema,
                """
                mutation {deleteUser(id: "1")}
                """,
                context_value=context,
            )

        async def receive_one():
            async for result in subscription_one:  # type: ignore
                received_one.append(result)
                if len(received_one) == 3:  # pragma: no cover else
                    break

        async def receive_all():
            async for result in subscription_all:  # type: ignore
                received_all.append(result)
                if len(received_all) == 6:  # pragma: no cover else
                    break

        tasks = [
            create_task(task()) if create_task else task()
            for task in (mutate_users, receive_one, receive_all)
        ]
        done, pending = await wait(tasks, timeout=1)
        assert not pending

        expected_data: List[Dict[str, Any]] = [
            {
                "mutation": "CREATED",
                "user": {
                    "id": "0",
                    "firstName": "John",
                    "lastName": "Doe",
                    "tweets": 42,
                    "verified": True,
                },
            },
            {
                "mutation": "CREATED",
                "user": {
                    "id": "1",
                    "firstName": "James",
                    "lastName": "Doe",
                    "tweets": 4,
                    "verified": False,
                },
            },
            {
                "mutation": "UPDATED",
                "user": {
                    "id": "0",
                    "firstName": "Jane",
                    "lastName": "Roe",
                    "tweets": 210,
                    "verified": False,
                },
            },
            {
                "mutation": "UPDATED",
                "user": {
                    "id": "1",
                    "firstName": "Janette",
                    "lastName": "Roe",
                    "tweets": 20,
                    "verified": True,
                },
            },
            {
                "mutation": "DELETED",
                "user": {
                    "id": "0",
                    "firstName": "Jane",
                    "lastName": "Roe",
                    "tweets": 210,
                    "verified": False,
                },
            },
            {
                "mutation": "DELETED",
                "user": {
                    "id": "1",
                    "firstName": "Janette",
                    "lastName": "Roe",
                    "tweets": 20,
                    "verified": True,
                },
            },
        ]

        assert received_one == [
            ({"subscribeUser": data}, None)
            for data in expected_data
            if data["user"]["id"] == "0"
        ]
        assert received_all == [
            ({"subscribeUser": data}, None) for data in expected_data
        ]

        await sleep(0)
