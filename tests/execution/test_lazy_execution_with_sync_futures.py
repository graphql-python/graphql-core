from typing import (
    Any,
    AsyncIterable,
    Callable,
    Dict,
    Optional,
    List,
    Iterable,
    Union,
    cast,
)

from functools import partial

from unittest.mock import Mock

from graphql import (
    ExecutionContext,
    FieldNode,
    GraphQLError,
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLOutputType,
    GraphQLResolveInfo,
    GraphQLString,
    GraphQLArgument,
    GraphQLList,
    OperationDefinitionNode,
    graphql_sync,
    located_error,
)
from graphql.pyutils import (
    is_collection,
    is_iterable,
    Path,
    AwaitableOrValue,
    Undefined,
)

from graphql.execution.execute import get_field_def
from graphql.execution.values import get_argument_values

from pytest import raises

_PENDING = "PENDING"
_FINISHED = "FINISHED"


class InvalidStateError(Exception):
    """The operation is not allowed in this state."""


class Future:

    _state = _PENDING
    _result: Optional[Any] = None
    _exception: Optional[Exception] = None
    _callbacks: List[Callable]
    _cancel_message = None

    deferred_callback: Callable = None

    def __init__(self):
        self._callbacks = []

    def done(self) -> bool:
        return self._state != _PENDING

    def result(self):
        self._assert_state(_FINISHED)
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self):
        self._assert_state(_FINISHED)
        return self._exception

    def add_done_callback(self, fn: Callable) -> None:
        self._assert_state(_PENDING)
        self._callbacks.append(fn)

    def set_result(self, result: Any) -> None:
        self._assert_state(_PENDING)
        self._result = result
        self._finish()

    def set_exception(self, exception: Exception) -> None:
        self._assert_state(_PENDING)
        if isinstance(exception, type):
            exception = exception()
        self._exception = exception
        self._finish()

    def _assert_state(self, state: str) -> None:
        if self._state != state:
            raise InvalidStateError(f"Future is not {state}")

    def _finish(self):
        self._state = _FINISHED
        callbacks = self._callbacks
        if not callbacks:
            return
        self._callbacks = []
        for callback in callbacks:
            callback()


def test_future():  # TODO: Future should be fully tested later

    f = Future()
    assert not f.done()
    with raises(InvalidStateError):
        f.result()
    f.set_result(42)
    assert f.result() == 42
    assert f.done()


class DeferredExecutionContext(ExecutionContext):
    """Execution for working with synchronous Futures.

    This execution context can handle synchronous Futures as resolved values.
    Deferred callbacks set in these Futures are called after the operation
    is executed and before the result is returned.
    """

    _deferred_callbacks: List[Callable]

    def execute_operation(
        self, operation: OperationDefinitionNode, root_value: Any
    ) -> Optional[AwaitableOrValue[Any]]:
        self._deferred_callbacks = []
        result = super().execute_operation(operation, root_value)

        callbacks = self._deferred_callbacks
        while callbacks:
            callbacks.pop(0)()

        if isinstance(result, Future):
            if not result.done():
                raise RuntimeError("GraphQL deferred execution failed to complete.")
            return result.result()

        return result

    def execute_fields_serially(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Optional[Path],
        fields: Dict[str, List[FieldNode]],
    ) -> AwaitableOrValue[Dict[str, Any]]:
        results: AwaitableOrValue[Dict[str, Any]] = {}

        unresolved = 0
        for response_name, field_nodes in fields.items():
            field_path = Path(path, response_name, parent_type.name)
            result = self.execute_field(
                parent_type, source_value, field_nodes, field_path
            )
            if isinstance(result, Future):
                if result.done():
                    result = result.result()
                    if result is not Undefined:
                        results[response_name] = result
                else:

                    # noinspection PyShadowingNames, PyBroadException
                    def process_result(response_name: str, result: Future) -> None:
                        nonlocal unresolved
                        awaited_result = result.result()
                        if awaited_result is not Undefined:
                            results[response_name] = awaited_result
                        unresolved -= 1
                        if not unresolved:
                            future.set_result(results)

                    unresolved += 1
                    result.add_done_callback(
                        partial(process_result, response_name, result)
                    )
            elif result is not Undefined:
                results[response_name] = result

        if not unresolved:
            return results

        future = Future()
        return future

    execute_fields = execute_fields_serially

    def execute_field(
        self,
        parent_type: GraphQLObjectType,
        source: Any,
        field_nodes: List[FieldNode],
        path: Path,
    ) -> AwaitableOrValue[Any]:
        field_def = get_field_def(self.schema, parent_type, field_nodes[0])
        if not field_def:
            return Undefined
        return_type = field_def.type
        resolve_fn = field_def.resolve or self.field_resolver
        if self.middleware_manager:
            resolve_fn = self.middleware_manager.get_field_resolver(resolve_fn)
        info = self.build_resolve_info(field_def, field_nodes, parent_type, path)
        try:
            args = get_argument_values(field_def, field_nodes[0], self.variable_values)
            result = resolve_fn(source, info, **args)

            if isinstance(result, Future):

                if result.done():
                    completed = self.complete_value(
                        return_type, field_nodes, info, path, result.result()
                    )

                else:

                    callback = result.deferred_callback
                    if callback:
                        self._deferred_callbacks.append(callback)

                    # noinspection PyShadowingNames
                    def process_result():
                        try:
                            completed = self.complete_value(
                                return_type, field_nodes, info, path, result.result()
                            )
                            if isinstance(completed, Future):

                                # noinspection PyShadowingNames
                                def process_completed():
                                    try:
                                        future.set_result(completed.result())
                                    except Exception as raw_error:
                                        error = located_error(
                                            raw_error, field_nodes, path.as_list()
                                        )
                                        self.handle_field_error(error, return_type)
                                        future.set_result(None)

                                if completed.done():
                                    process_completed()
                                else:
                                    completed.add_done_callback(process_completed)
                            else:
                                future.set_result(completed)
                        except Exception as raw_error:
                            error = located_error(
                                raw_error, field_nodes, path.as_list()
                            )
                            self.handle_field_error(error, return_type)
                            future.set_result(None)

                    future = Future()
                    result.add_done_callback(process_result)
                    return future

            else:
                completed = self.complete_value(
                    return_type, field_nodes, info, path, result
                )

            if isinstance(completed, Future):

                # noinspection PyShadowingNames
                def process_completed():
                    try:
                        future.set_result(completed.result())
                    except Exception as raw_error:
                        error = located_error(raw_error, field_nodes, path.as_list())
                        self.handle_field_error(error, return_type)
                        future.set_result(None)

                if completed.done():
                    return process_completed()

                future = Future()
                completed.add_done_callback(process_completed)
                return future

            return completed
        except Exception as raw_error:
            error = located_error(raw_error, field_nodes, path.as_list())
            self.handle_field_error(error, return_type)
            return None

    def complete_list_value(
        self,
        return_type: GraphQLList[GraphQLOutputType],
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        result: Union[AsyncIterable[Any], Iterable[Any]],
    ) -> AwaitableOrValue[List[Any]]:
        if not is_iterable(result):
            if isinstance(result, Future):

                def process_result():
                    return self.complete_list_value(
                        return_type, field_nodes, info, path, result.result()
                    )

                if result.done():
                    return process_result()
                future = Future()
                result.add_done_callback(process_result)
                return future

            raise GraphQLError(
                "Expected Iterable, but did not find one for field"
                f" '{info.parent_type.name}.{info.field_name}'."
            )
        result = cast(Iterable[Any], result)

        item_type = return_type.of_type
        results: List[Any] = [None] * len(result)

        unresolved = 0

        for index, item in enumerate(result):
            item_path = path.add_key(index, None)

            try:
                if isinstance(item, Future):

                    if item.done():
                        completed = self.complete_value(
                            item_type, field_nodes, info, item_path, item.result()
                        )
                    else:
                        callback = item.deferred_callback
                        if callback:
                            self._deferred_callbacks.append(callback)

                        # noinspection PyShadowingNames
                        def process_item(
                            index: int, item: Future, item_path: Path
                        ) -> None:
                            nonlocal unresolved
                            try:
                                completed = self.complete_value(
                                    item_type,
                                    field_nodes,
                                    info,
                                    item_path,
                                    item.result(),
                                )
                                if isinstance(completed, Future):
                                    if completed.done():
                                        results[index] = completed.result()
                                    else:

                                        # noinspection PyShadowingNames
                                        def process_completed(
                                            index: int,
                                            completed: Future,
                                            item_path: Path,
                                        ) -> None:
                                            try:
                                                results[index] = completed.result()
                                            except Exception as raw_error:
                                                error = located_error(
                                                    raw_error,
                                                    field_nodes,
                                                    item_path.as_list(),
                                                )
                                                self.handle_field_error(
                                                    error, item_type
                                                )

                                        completed.add_done_callback(
                                            partial(
                                                process_completed,
                                                index,
                                                completed,
                                                item_path,
                                            )
                                        )
                                else:
                                    results[index] = completed
                            except Exception as raw_error:
                                error = located_error(
                                    raw_error, field_nodes, item_path.as_list()
                                )
                                self.handle_field_error(error, item_type)
                            unresolved -= 1
                            if not unresolved:
                                future.set_result(results)

                        unresolved += 1
                        item.add_done_callback(
                            partial(process_item, index, item, item_path)
                        )
                        continue
                else:
                    completed = self.complete_value(
                        item_type, field_nodes, info, item_path, item
                    )

                if isinstance(completed, Future):

                    if completed.done():
                        results[index] = completed.result()
                    else:
                        callback = completed.deferred_callback
                        if callback:
                            self._deferred_callbacks.append(callback)

                        # noinspection PyShadowingNames
                        def process_completed(
                            index: int, completed: Future, item_path: Path
                        ) -> None:
                            nonlocal unresolved
                            try:
                                results[index] = completed.result()
                            except Exception as raw_error:
                                error = located_error(
                                    raw_error, field_nodes, item_path.as_list()
                                )
                                self.handle_field_error(error, item_type)
                            unresolved -= 1
                            if not unresolved:
                                future.set_result(results)

                        unresolved += 1
                        completed.add_callback(
                            partial(process_completed, index, completed, item_path)
                        )
                else:
                    results[index] = completed
            except Exception as raw_error:
                error = located_error(raw_error, field_nodes, item_path.as_list())
                self.handle_field_error(error, item_type)

        if not unresolved:
            return results

        future = Future()
        return future


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
                future.deferred_callback = self.dispatch_queue
            self._cache[key] = future
            return future

    def clear(self, key):
        self._cache.pop(key, None)

    def dispatch_queue(self):
        queue = self._queue
        if not queue:
            return
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
                if not future.done():
                    future.set_exception(error)


graphql_sync_deferred = partial(
    graphql_sync, execution_context_class=DeferredExecutionContext
)


def test_deferred_execution():
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

    result = graphql_sync_deferred(
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


def test_nested_deferred_execution():
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

    result = graphql_sync_deferred(
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


def test_deferred_execution_list():
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
        return [dataloader.load(id) for id in USERS]

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

    result = graphql_sync_deferred(
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

    if result.errors:
        raise result.errors[0].original_error
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


def test_deferred_execution_errors():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": ValueError("Sarah has left"),
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
        return [dataloader.load(id) for id in USERS]

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

    result = graphql_sync_deferred(
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

    assert result.errors == [
        {"message": "Sarah has left", "locations": [(3, 13)], "path": ["users", 1]},
        {
            "message": "Sarah has left",
            "locations": [(5, 17)],
            "path": ["users", 0, "bestFriend"],
        },
        {
            "message": "Sarah has left",
            "locations": [(5, 17)],
            "path": ["users", 2, "bestFriend"],
        },
    ]
    assert result.data == {
        "users": [
            {
                "name": "Laura",
                "bestFriend": None,
            },
            None,
            {
                "name": "Dave",
                "bestFriend": None,
            },
        ],
    }
    assert mock_load_fn.call_count == 1
