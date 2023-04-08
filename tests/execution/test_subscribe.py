import asyncio
from typing import Any, AsyncIterable, Callable, Dict, List, Optional, TypeVar, Union

from pytest import mark, raises

from graphql.execution import (
    ExecutionResult,
    MapAsyncIterable,
    create_source_event_stream,
    subscribe,
)
from graphql.language import DocumentNode, parse
from graphql.pyutils import AwaitableOrValue, SimplePubSub, is_awaitable
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from ..utils.assert_equal_awaitables_or_values import assert_equal_awaitables_or_values


try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict

try:
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator):
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


T = TypeVar("T")

Email = TypedDict(
    "Email",
    {
        "from": str,
        "subject": str,
        "message": str,
        "unread": bool,
    },
)

EmailType = GraphQLObjectType(
    "Email",
    {
        "from": GraphQLField(GraphQLString),
        "subject": GraphQLField(GraphQLString),
        "message": GraphQLField(GraphQLString),
        "unread": GraphQLField(GraphQLBoolean),
    },
)

InboxType = GraphQLObjectType(
    "Inbox",
    {
        "total": GraphQLField(
            GraphQLInt, resolve=lambda inbox, _info: len(inbox["emails"])
        ),
        "unread": GraphQLField(
            GraphQLInt,
            resolve=lambda inbox, _info: sum(
                1 for email in inbox["emails"] if email["unread"]
            ),
        ),
        "emails": GraphQLField(GraphQLList(EmailType)),
    },
)

QueryType = GraphQLObjectType("Query", {"inbox": GraphQLField(InboxType)})

EmailEventType = GraphQLObjectType(
    "EmailEvent", {"email": GraphQLField(EmailType), "inbox": GraphQLField(InboxType)}
)


email_schema = GraphQLSchema(
    query=QueryType,
    subscription=GraphQLObjectType(
        "Subscription",
        {
            "importantEmail": GraphQLField(
                EmailEventType,
                args={"priority": GraphQLArgument(GraphQLInt)},
            )
        },
    ),
)


def create_subscription(pubsub: SimplePubSub):
    document = parse(
        """
        subscription ($priority: Int = 0) {
          importantEmail(priority: $priority) {
            email {
              from
              subject
            }
            inbox {
              unread
              total
            }
          }
        }
        """
    )

    emails: List[Email] = [
        {
            "from": "joe@graphql.org",
            "subject": "Hello",
            "message": "Hello World",
            "unread": False,
        }
    ]

    def transform(new_email):
        emails.append(new_email)

        return {"importantEmail": {"email": new_email, "inbox": data["inbox"]}}

    data: Dict[str, Any] = {
        "inbox": {"emails": emails},
        "importantEmail": pubsub.get_subscriber(transform),
    }

    return subscribe(email_schema, document, data)


DummyQueryType = GraphQLObjectType("Query", {"dummy": GraphQLField(GraphQLString)})


def subscribe_with_bad_fn(
    subscribe_fn: Callable,
) -> AwaitableOrValue[Union[ExecutionResult, AsyncIterable[Any]]]:
    schema = GraphQLSchema(
        query=DummyQueryType,
        subscription=GraphQLObjectType(
            "Subscription",
            {"foo": GraphQLField(GraphQLString, subscribe=subscribe_fn)},
        ),
    )
    document = parse("subscription { foo }")
    return subscribe_with_bad_args(schema, document)


def subscribe_with_bad_args(
    schema: GraphQLSchema,
    document: DocumentNode,
    variable_values: Optional[Dict[str, Any]] = None,
):
    return assert_equal_awaitables_or_values(
        subscribe(schema, document, variable_values=variable_values),
        create_source_event_stream(schema, document, variable_values=variable_values),
    )


# Check all error cases when initializing the subscription.
def describe_subscription_initialization_phase():
    @mark.asyncio
    async def accepts_positional_arguments():
        document = parse(
            """
            subscription {
              importantEmail
            }
            """
        )

        async def empty_async_iterable(_info):
            for value in ():  # type: ignore
                yield value  # pragma: no cover

        ai = subscribe(email_schema, document, {"importantEmail": empty_async_iterable})

        with raises(StopAsyncIteration):
            await anext(ai)
        await ai.aclose()  # type: ignore

    @mark.asyncio
    async def accepts_multiple_subscription_fields_defined_in_schema():
        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "foo": GraphQLField(GraphQLString),
                    "bar": GraphQLField(GraphQLString),
                },
            ),
        )

        async def foo_generator(_info):
            yield {"foo": "FooValue"}

        subscription = subscribe(
            schema, parse("subscription { foo }"), {"foo": foo_generator}
        )
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == ({"foo": "FooValue"}, None)

        await subscription.aclose()

    @mark.asyncio
    async def accepts_type_definition_with_sync_subscribe_function():
        async def foo_generator(_obj, _info):
            yield {"foo": "FooValue"}

        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {"foo": GraphQLField(GraphQLString, subscribe=foo_generator)},
            ),
        )

        subscription = subscribe(schema, parse("subscription { foo }"))
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == ({"foo": "FooValue"}, None)

        await subscription.aclose()

    @mark.asyncio
    async def accepts_type_definition_with_async_subscribe_function():
        async def foo_generator(_obj, _info):
            await asyncio.sleep(0)
            yield {"foo": "FooValue"}

        async def subscribe_fn(obj, info):
            await asyncio.sleep(0)
            return foo_generator(obj, info)

        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {"foo": GraphQLField(GraphQLString, subscribe=subscribe_fn)},
            ),
        )

        awaitable = subscribe(schema, parse("subscription { foo }"))
        assert is_awaitable(awaitable)

        subscription = await awaitable
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == ({"foo": "FooValue"}, None)

        await subscription.aclose()

    @mark.asyncio
    async def should_only_resolve_the_first_field_of_invalid_multi_field():
        did_resolve = {"foo": False, "bar": False}

        async def subscribe_foo(_obj, _info):
            did_resolve["foo"] = True
            yield {"foo": "FooValue"}

        async def subscribe_bar(_obj, _info):  # pragma: no cover
            did_resolve["bar"] = True
            yield {"bar": "BarValue"}

        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "foo": GraphQLField(GraphQLString, subscribe=subscribe_foo),
                    "bar": GraphQLField(GraphQLString, subscribe=subscribe_bar),
                },
            ),
        )

        subscription = subscribe(schema, parse("subscription { foo bar }"))
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == (
            {"foo": "FooValue", "bar": None},
            None,
        )

        assert did_resolve == {"foo": True, "bar": False}

        await subscription.aclose()

    @mark.asyncio
    async def resolves_to_an_error_if_schema_does_not_support_subscriptions():
        schema = GraphQLSchema(query=DummyQueryType)
        document = parse("subscription { unknownField }")

        result = subscribe_with_bad_args(schema, document)

        assert result == (
            None,
            [
                {
                    "message": "Schema is not configured to execute"
                    " subscription operation.",
                    "locations": [(1, 1)],
                }
            ],
        )

    @mark.asyncio
    async def resolves_to_an_error_for_unknown_subscription_field():
        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription", {"foo": GraphQLField(GraphQLString)}
            ),
        )
        document = parse("subscription { unknownField }")

        result = subscribe_with_bad_args(schema, document)
        assert result == (
            None,
            [
                {
                    "message": "The subscription field 'unknownField' is not defined.",
                    "locations": [(1, 16)],
                }
            ],
        )

    @mark.asyncio
    async def should_pass_through_unexpected_errors_thrown_in_subscribe():
        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription", {"foo": GraphQLField(GraphQLString)}
            ),
        )
        with raises(AttributeError):
            subscribe_with_bad_args(schema=schema, document={})  # type: ignore

    @mark.asyncio
    @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    async def throws_an_error_if_subscribe_does_not_return_an_iterator():
        expected_result = (
            None,
            [
                {
                    "message": "Subscription field must return AsyncIterable."
                    " Received: 'test'.",
                    "locations": [(1, 16)],
                    "path": ["foo"],
                }
            ],
        )

        def sync_fn(_obj, _info):
            return "test"

        assert subscribe_with_bad_fn(sync_fn) == expected_result

        async def async_fn(obj, info):
            return sync_fn(obj, info)

        result = subscribe_with_bad_fn(async_fn)
        assert is_awaitable(result)
        assert await result == expected_result

    @mark.asyncio
    async def resolves_to_an_error_for_subscription_resolver_errors():
        expected_result = (
            None,
            [
                {
                    "message": "test error",
                    "locations": [(1, 16)],
                    "path": ["foo"],
                }
            ],
        )

        # Returning an error
        def return_error(*_args):
            return TypeError("test error")

        assert subscribe_with_bad_fn(return_error) == expected_result

        # Throwing an error
        def throw_error(*_args):
            raise TypeError("test error")

        assert subscribe_with_bad_fn(throw_error) == expected_result

        # Resolving to an error
        async def resolve_to_error(*args):
            return return_error(*args)

        result = subscribe_with_bad_fn(resolve_to_error)
        assert is_awaitable(result)
        assert await result == expected_result

        # Rejecting with an error

        async def reject_with_error(*args):
            return throw_error(*args)

        result = subscribe_with_bad_fn(reject_with_error)
        assert is_awaitable(result)
        assert await result == expected_result

    @mark.asyncio
    async def resolves_to_an_error_if_variables_were_wrong_type():
        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "foo": GraphQLField(
                        GraphQLString, {"arg": GraphQLArgument(GraphQLInt)}
                    )
                },
            ),
        )

        variable_values = {"arg": "meow"}
        document = parse(
            """
            subscription ($arg: Int) {
              foo(arg: $arg)
            }
            """
        )

        # If we receive variables that cannot be coerced correctly, subscribe() will
        # resolve to an ExecutionResult that contains an informative error description.
        result = subscribe_with_bad_args(
            schema, document, variable_values=variable_values
        )

        assert result == (
            None,
            [
                {
                    "message": "Variable '$arg' got invalid value 'meow';"
                    " Int cannot represent non-integer value: 'meow'",
                    "locations": [(2, 27)],
                }
            ],
        )

        assert result.errors[0].original_error is None


# Once a subscription returns a valid AsyncIterator, it can still yield errors.
def describe_subscription_publish_phase():
    @mark.asyncio
    async def produces_a_payload_for_multiple_subscribe_in_same_subscription():
        pubsub = SimplePubSub()

        subscription = create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterable)

        second_subscription = create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterable)

        payload1 = anext(subscription)
        payload2 = anext(second_subscription)

        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Alright",
                    "message": "Tests are good",
                    "unread": True,
                }
            )
            is True
        )

        expected_payload = {
            "importantEmail": {
                "email": {"from": "yuzhi@graphql.org", "subject": "Alright"},
                "inbox": {"unread": 1, "total": 2},
            }
        }

        assert await payload1 == (expected_payload, None)
        assert await payload2 == (expected_payload, None)

    @mark.asyncio
    async def produces_a_payload_per_subscription_event():
        pubsub = SimplePubSub()
        subscription = create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterable)

        # Wait for the next subscription payload.
        payload = anext(subscription)

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Alright",
                    "message": "Tests are good",
                    "unread": True,
                }
            )
            is True
        )

        # The previously waited on payload now has a value.
        assert await payload == (
            {
                "importantEmail": {
                    "email": {"from": "yuzhi@graphql.org", "subject": "Alright"},
                    "inbox": {"unread": 1, "total": 2},
                }
            },
            None,
        )

        # Another new email arrives, before anext(subscription) is called.
        assert (
            pubsub.emit(
                {
                    "from": "hyo@graphql.org",
                    "subject": "Tools",
                    "message": "I <3 making things",
                    "unread": True,
                }
            )
            is True
        )

        # The next waited on payload will have a value.
        assert await anext(subscription) == (
            {
                "importantEmail": {
                    "email": {"from": "hyo@graphql.org", "subject": "Tools"},
                    "inbox": {"unread": 2, "total": 3},
                }
            },
            None,
        )

        # The client decides to disconnect.
        # noinspection PyUnresolvedReferences
        await subscription.aclose()

        # Which may result in disconnecting upstream services as well.
        assert (
            pubsub.emit(
                {
                    "from": "adam@graphql.org",
                    "subject": "Important",
                    "message": "Read me please",
                    "unread": True,
                }
            )
            is False
        )  # No more listeners.

        # Awaiting subscription after closing it results in completed results.
        with raises(StopAsyncIteration):
            assert await anext(subscription)

    @mark.asyncio
    async def produces_a_payload_when_there_are_multiple_events():
        pubsub = SimplePubSub()
        subscription = create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterable)

        payload = anext(subscription)

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Alright",
                    "message": "Tests are good",
                    "unread": True,
                }
            )
            is True
        )

        assert await payload == (
            {
                "importantEmail": {
                    "email": {"from": "yuzhi@graphql.org", "subject": "Alright"},
                    "inbox": {"unread": 1, "total": 2},
                }
            },
            None,
        )

        payload = anext(subscription)

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Alright 2",
                    "message": "Tests are good 2",
                    "unread": True,
                }
            )
            is True
        )

        assert await payload == (
            {
                "importantEmail": {
                    "email": {"from": "yuzhi@graphql.org", "subject": "Alright 2"},
                    "inbox": {"unread": 2, "total": 3},
                }
            },
            None,
        )

    @mark.asyncio
    async def should_not_trigger_when_subscription_is_already_done():
        pubsub = SimplePubSub()
        subscription = create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterable)

        payload = anext(subscription)

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Alright",
                    "message": "Tests are good",
                    "unread": True,
                }
            )
            is True
        )

        assert await payload == (
            {
                "importantEmail": {
                    "email": {"from": "yuzhi@graphql.org", "subject": "Alright"},
                    "inbox": {"unread": 1, "total": 2},
                }
            },
            None,
        )

        payload = anext(subscription)
        await subscription.aclose()

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Alright 2",
                    "message": "Tests are good 2",
                    "unread": True,
                }
            )
            is False
        )

        with raises(StopAsyncIteration):
            await payload

    @mark.asyncio
    async def should_not_trigger_when_subscription_is_thrown():
        pubsub = SimplePubSub()
        subscription = create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterable)

        payload = anext(subscription)

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Alright",
                    "message": "Tests are good",
                    "unread": True,
                }
            )
            is True
        )

        assert await payload == (
            {
                "importantEmail": {
                    "email": {"from": "yuzhi@graphql.org", "subject": "Alright"},
                    "inbox": {"unread": 1, "total": 2},
                }
            },
            None,
        )

        payload = anext(subscription)

        # Throw error
        with raises(RuntimeError) as exc_info:
            await subscription.athrow(RuntimeError("ouch"))
        assert str(exc_info.value) == "ouch"

        with raises(StopAsyncIteration):
            await payload

    @mark.asyncio
    async def event_order_is_correct_for_multiple_publishes():
        pubsub = SimplePubSub()
        subscription = create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterable)

        payload = anext(subscription)

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Message",
                    "message": "Tests are good",
                    "unread": True,
                }
            )
            is True
        )

        # A new email arrives!
        assert (
            pubsub.emit(
                {
                    "from": "yuzhi@graphql.org",
                    "subject": "Message 2",
                    "message": "Tests are good 2",
                    "unread": True,
                }
            )
            is True
        )

        assert await payload == (
            {
                "importantEmail": {
                    "email": {"from": "yuzhi@graphql.org", "subject": "Message"},
                    "inbox": {"unread": 2, "total": 3},
                }
            },
            None,
        )

        payload = anext(subscription)

        assert await payload == (
            {
                "importantEmail": {
                    "email": {"from": "yuzhi@graphql.org", "subject": "Message 2"},
                    "inbox": {"unread": 2, "total": 3},
                }
            },
            None,
        )

    @mark.asyncio
    async def should_handle_error_during_execution_of_source_event():
        async def generate_messages(_obj, _info):
            yield "Hello"
            yield "Goodbye"
            yield "Bonjour"

        def resolve_message(message, _info):
            if message == "Goodbye":
                raise RuntimeError("Never leave.")
            return message

        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "newMessage": GraphQLField(
                        GraphQLString,
                        subscribe=generate_messages,
                        resolve=resolve_message,
                    )
                },
            ),
        )

        document = parse("subscription { newMessage }")
        subscription = subscribe(schema, document)
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == ({"newMessage": "Hello"}, None)

        # An error in execution is presented as such.
        assert await anext(subscription) == (
            {"newMessage": None},
            [
                {
                    "message": "Never leave.",
                    "locations": [(1, 16)],
                    "path": ["newMessage"],
                }
            ],
        )

        # However that does not close the response event stream.
        # Subsequent events are still executed.
        assert await anext(subscription) == ({"newMessage": "Bonjour"}, None)

    @mark.asyncio
    async def should_pass_through_error_thrown_in_source_event_stream():
        async def generate_messages(_obj, _info):
            yield "Hello"
            raise RuntimeError("test error")

        def resolve_message(message, _info):
            return message

        schema = GraphQLSchema(
            query=DummyQueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "newMessage": GraphQLField(
                        GraphQLString,
                        resolve=resolve_message,
                        subscribe=generate_messages,
                    )
                },
            ),
        )

        document = parse("subscription { newMessage }")
        subscription = subscribe(schema, document)
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == ({"newMessage": "Hello"}, None)

        with raises(RuntimeError) as exc_info:
            await anext(subscription)

        assert str(exc_info.value) == "test error"

        with raises(StopAsyncIteration):
            await anext(subscription)

    @mark.asyncio
    async def should_work_with_sync_resolve_function():
        async def generate_messages(_obj, _info):
            yield "Hello"

        def resolve_message(message, _info):
            return message

        schema = GraphQLSchema(
            query=QueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "newMessage": GraphQLField(
                        GraphQLString,
                        resolve=resolve_message,
                        subscribe=generate_messages,
                    )
                },
            ),
        )

        document = parse("subscription { newMessage }")
        subscription = subscribe(schema, document)
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == ({"newMessage": "Hello"}, None)

    @mark.asyncio
    async def should_work_with_async_resolve_function():
        async def generate_messages(_obj, _info):
            await asyncio.sleep(0)
            yield "Hello"

        async def resolve_message(message, _info):
            await asyncio.sleep(0)
            return message

        schema = GraphQLSchema(
            query=QueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "newMessage": GraphQLField(
                        GraphQLString,
                        resolve=resolve_message,
                        subscribe=generate_messages,
                    )
                },
            ),
        )

        document = parse("subscription { newMessage }")
        subscription = subscribe(schema, document)
        assert isinstance(subscription, MapAsyncIterable)

        assert await anext(subscription) == ({"newMessage": "Hello"}, None)
