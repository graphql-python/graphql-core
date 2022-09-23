from asyncio import Future, get_running_loop
from unittest.mock import Mock

from graphql import (
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLString,
    GraphQLArgument,
    GraphQLList,
    graphql,
)
from graphql.pyutils import is_collection

from pytest import mark


class DataLoader:
    def __init__(self, batch_load_fn):
        self._batch_load_fn = batch_load_fn
        self._cache = {}
        self._queue = []

    def load(self, key):
        try:
            return self._cache[key]
        except KeyError:
            future = Future()
            needs_dispatch = not self._queue
            self._queue.append((key, future))

            if needs_dispatch:
                get_running_loop().call_soon(self.dispatch_queue)
            self._cache[key] = future
            return future

    def clear(self, key):
        self._cache.pop(key, None)

    def dispatch_queue(self):
        queue = self._queue
        self._queue = []

        keys = [item[0] for item in queue]
        values = self._batch_load_fn(keys)
        if not is_collection(values) or len(keys) != len(values):
            raise ValueError("The batch loader does not return an expected result")

        try:
            for (key, future), value in zip(queue, values):
                if isinstance(value, Exception):
                    future.set_exception(value)
                else:
                    future.set_result(value)
        except Exception as error:
            for key, future in queue:
                self.clear(key)
                future.set_exception(error)


@mark.asyncio
async def test_lazy_execution():
    NAMES = {
        "1": "Sarah",
        "2": "Lucy",
        "3": "Geoff",
        "5": "Dave",
    }

    def load_fn(keys):
        return [NAMES[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = DataLoader(mock_load_fn)

    def resolve_name(root, info, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "name": GraphQLField(
                    GraphQLString,
                    args={
                        "key": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_name,
                )
            },
        )
    )

    result = await graphql(
        schema,
        """
        query {
            name1: name(key: "1")
            name2: name(key: "2")
        }
        """,
    )

    assert not result.errors
    assert result.data == {"name1": "Sarah", "name2": "Lucy"}
    assert mock_load_fn.call_count == 1


@mark.asyncio
async def test_nested_lazy_execution():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": {
            "name": "Sarah",
            "bestFriend": None,
        },
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = DataLoader(mock_load_fn)

    def resolve_user(root, info, id):
        return dataloader.load(id)

    def resolve_best_friend(user, info):
        return dataloader.load(user["bestFriend"])

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "user": GraphQLField(
                    user,
                    args={
                        "id": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_user,
                )
            },
        )
    )

    result = await graphql(
        schema,
        """
        query {
            user1: user(id: "1") {
                name
                bestFriend {
                    name
                }
            }
            user2: user(id: "3") {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    assert not result.errors
    assert result.data == {
        "user1": {
            "name": "Laura",
            "bestFriend": {
                "name": "Sarah",
            },
        },
        "user2": {
            "name": "Dave",
            "bestFriend": {
                "name": "Sarah",
            },
        },
    }
    assert mock_load_fn.call_count == 2


@mark.asyncio
async def test_lazy_execution_list():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": {
            "name": "Sarah",
            "bestFriend": None,
        },
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = DataLoader(mock_load_fn)

    def resolve_users(root, info):
        return [dataloader.load(id) for id in USERS.keys()]

    def resolve_best_friend(user, info):
        if user["bestFriend"]:
            return dataloader.load(user["bestFriend"])
        return None

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "users": GraphQLField(
                    GraphQLList(user),
                    resolve=resolve_users,
                )
            },
        )
    )

    result = await graphql(
        schema,
        """
        query {
            users {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    assert not result.errors
    assert result.data == {
        "users": [
            {
                "name": "Laura",
                "bestFriend": {
                    "name": "Sarah",
                },
            },
            {
                "name": "Sarah",
                "bestFriend": None,
            },
            {
                "name": "Dave",
                "bestFriend": {
                    "name": "Sarah",
                },
            },
        ],
    }
    assert mock_load_fn.call_count == 1


def test_lazy_execution_errors():
    raise NotImplementedError()
