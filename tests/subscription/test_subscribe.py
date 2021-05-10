import asyncio

from typing import Any, Dict, List, Optional, Callable

from pytest import mark, raises

from graphql.language import parse, DocumentNode
from graphql.pyutils import SimplePubSub
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
from graphql.subscription import subscribe, MapAsyncIterator

Email = Dict  # should become a TypedDict once we require Python 3.8

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


async def anext(iterable):
    """Return the next item from an async iterator."""
    return await iterable.__anext__()


def email_schema_with_resolvers(
    subscribe_fn: Optional[Callable] = None, resolve_fn: Optional[Callable] = None
):
    return GraphQLSchema(
        query=QueryType,
        subscription=GraphQLObjectType(
            "Subscription",
            {
                "importantEmail": GraphQLField(
                    EmailEventType,
                    args={"priority": GraphQLArgument(GraphQLInt)},
                    resolve=resolve_fn,
                    subscribe=subscribe_fn,
                )
            },
        ),
    )


email_schema = email_schema_with_resolvers()

default_subscription_ast = parse(
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


def create_subscription(
    pubsub: SimplePubSub,
    schema: GraphQLSchema = email_schema,
    document: DocumentNode = default_subscription_ast,
):
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

    return subscribe(schema, document, data)


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

        async def empty_async_iterator(_info):
            for value in ():  # type: ignore
                yield value  # pragma: no cover

        ai = await subscribe(
            email_schema, document, {"importantEmail": empty_async_iterator}
        )

        with raises(StopAsyncIteration):
            await anext(ai)
        await ai.aclose()  # type: ignore

    @mark.asyncio
    async def accepts_multiple_subscription_fields_defined_in_schema():
        pubsub = SimplePubSub()
        subscription_type_multiple = GraphQLObjectType(
            "Subscription",
            {
                "importantEmail": GraphQLField(EmailEventType),
                "nonImportantEmail": GraphQLField(EmailEventType),
            },
        )

        test_schema = GraphQLSchema(
            query=QueryType, subscription=subscription_type_multiple
        )

        subscription = await create_subscription(pubsub, test_schema)

        assert isinstance(subscription, MapAsyncIterator)

        pubsub.emit(
            {
                "from": "yuzhi@graphql.org",
                "subject": "Alright",
                "message": "Tests are good",
                "unread": True,
            }
        )

        await anext(subscription)

    @mark.asyncio
    async def accepts_type_definition_with_sync_subscribe_function():
        pubsub = SimplePubSub()

        async def get_subscriber(*_args):
            return pubsub.get_subscriber()

        schema = GraphQLSchema(
            query=QueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "importantEmail": GraphQLField(
                        GraphQLString, subscribe=get_subscriber
                    )
                },
            ),
        )

        subscription = await subscribe(
            schema,
            parse(
                """
            subscription {
              importantEmail
            }
            """
            ),
        )

        pubsub.emit({"importantEmail": {}})

        await anext(subscription)

    @mark.asyncio
    async def accepts_type_definition_with_async_subscribe_function():
        pubsub = SimplePubSub()

        async def get_subscriber(*_args):
            await asyncio.sleep(0)
            return pubsub.get_subscriber()

        schema = GraphQLSchema(
            query=QueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "importantEmail": GraphQLField(
                        GraphQLString, subscribe=get_subscriber
                    )
                },
            ),
        )

        subscription = await subscribe(
            schema,
            parse(
                """
            subscription {
              importantEmail
            }
            """
            ),
        )

        pubsub.emit({"importantEmail": {}})

        await anext(subscription)

    @mark.asyncio
    async def should_only_resolve_the_first_field_of_invalid_multi_field():
        did_resolve = {"importantEmail": False, "nonImportantEmail": False}

        def subscribe_important(*_args):
            did_resolve["importantEmail"] = True
            return SimplePubSub().get_subscriber()

        def subscribe_non_important(*_args):  # pragma: no cover
            did_resolve["nonImportantEmail"] = True
            return SimplePubSub().get_subscriber()

        subscription_type_multiple = GraphQLObjectType(
            "Subscription",
            {
                "importantEmail": GraphQLField(
                    EmailEventType, subscribe=subscribe_important
                ),
                "nonImportantEmail": GraphQLField(
                    EmailEventType, subscribe=subscribe_non_important
                ),
            },
        )

        schema = GraphQLSchema(query=QueryType, subscription=subscription_type_multiple)

        subscription = await subscribe(
            schema,
            parse(
                """
            subscription {
              importantEmail
              nonImportantEmail
            }
            """
            ),
        )

        ignored = anext(subscription)  # Ask for a result, but ignore it.

        assert did_resolve["importantEmail"] is True
        assert did_resolve["nonImportantEmail"] is False

        # Close subscription
        # noinspection PyUnresolvedReferences
        await subscription.aclose()  # type: ignore

        with raises(StopAsyncIteration):
            await ignored

    # noinspection PyArgumentList
    @mark.asyncio
    async def throws_an_error_if_schema_is_missing():
        document = parse(
            """
            subscription {
              importantEmail
            }
            """
        )

        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            await subscribe(None, document)  # type: ignore

        assert str(exc_info.value) == "Expected None to be a GraphQL schema."

        with raises(TypeError, match="missing .* positional argument: 'schema'"):
            # noinspection PyTypeChecker
            await subscribe(document=document)  # type: ignore

    # noinspection PyArgumentList
    @mark.asyncio
    async def throws_an_error_if_document_is_missing():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            await subscribe(email_schema, None)  # type: ignore

        assert str(exc_info.value) == "Must provide document."

        with raises(TypeError, match="missing .* positional argument: 'document'"):
            # noinspection PyTypeChecker
            await subscribe(schema=email_schema)  # type: ignore

    @mark.asyncio
    async def resolves_to_an_error_for_unknown_subscription_field():
        ast = parse(
            """
            subscription {
              unknownField
            }
            """
        )

        pubsub = SimplePubSub()

        subscription = await create_subscription(pubsub, email_schema, ast)

        assert subscription == (
            None,
            [
                {
                    "message": "The subscription field 'unknownField' is not defined.",
                    "locations": [(3, 15)],
                }
            ],
        )

    @mark.asyncio
    async def should_pass_through_unexpected_errors_thrown_in_subscribe():
        with raises(TypeError, match="Must provide document\\."):
            await subscribe(schema=email_schema, document={})  # type: ignore

    @mark.asyncio
    @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    async def throws_an_error_if_subscribe_does_not_return_an_iterator():
        invalid_email_schema = GraphQLSchema(
            query=QueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "importantEmail": GraphQLField(
                        GraphQLString, subscribe=lambda _inbox, _info: "test"
                    )
                },
            ),
        )

        pubsub = SimplePubSub()

        with raises(TypeError) as exc_info:
            await create_subscription(pubsub, invalid_email_schema)

        assert str(exc_info.value) == (
            "Subscription field must return AsyncIterable. Received: 'test'."
        )

    @mark.asyncio
    async def resolves_to_an_error_for_subscription_resolver_errors():
        async def test_reports_error(schema: GraphQLSchema):
            result = await subscribe(
                schema=schema,
                document=parse(
                    """
                    subscription {
                      importantEmail
                    }
                    """
                ),
            )

            assert result == (
                None,
                [
                    {
                        "message": "test error",
                        "locations": [(3, 23)],
                        "path": ["importantEmail"],
                    }
                ],
            )

        # Returning an error
        def return_error(*_args):
            return TypeError("test error")

        subscription_returning_error_schema = email_schema_with_resolvers(return_error)
        await test_reports_error(subscription_returning_error_schema)

        # Throwing an error
        def throw_error(*_args):
            raise TypeError("test error")

        subscription_throwing_error_schema = email_schema_with_resolvers(throw_error)
        await test_reports_error(subscription_throwing_error_schema)

        # Resolving to an error
        async def resolve_error(*_args):
            return TypeError("test error")

        subscription_resolving_error_schema = email_schema_with_resolvers(resolve_error)
        await test_reports_error(subscription_resolving_error_schema)

        # Rejecting with an error
        async def reject_error(*_args):
            return TypeError("test error")

        subscription_rejecting_error_schema = email_schema_with_resolvers(reject_error)
        await test_reports_error(subscription_rejecting_error_schema)

    @mark.asyncio
    async def resolves_to_an_error_if_variables_were_wrong_type():
        # If we receive variables that cannot be coerced correctly, subscribe() will
        # resolve to an ExecutionResult that contains an informative error description.
        ast = parse(
            """
            subscription ($priority: Int) {
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

        result = await subscribe(
            schema=email_schema,
            document=ast,
            variable_values={"priority": "meow"},
        )

        assert result == (
            None,
            [
                {
                    "message": "Variable '$priority' got invalid value 'meow';"
                    " Int cannot represent non-integer value: 'meow'",
                    "locations": [(2, 27)],
                }
            ],
        )

        assert result.errors[0].original_error is None  # type: ignore


# Once a subscription returns a valid AsyncIterator, it can still yield errors.
def describe_subscription_publish_phase():
    @mark.asyncio
    async def produces_a_payload_for_multiple_subscribe_in_same_subscription():
        pubsub = SimplePubSub()

        subscription = await create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterator)

        second_subscription = await create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterator)

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
        subscription = await create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterator)

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

        # Another new email arrives, before subscription.___anext__ is called.
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
        subscription = await create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterator)

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
        subscription = await create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterator)

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
        subscription = await create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterator)

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
    async def event_order_is_correct_for_multiple_publishes():
        pubsub = SimplePubSub()
        subscription = await create_subscription(pubsub)
        assert isinstance(subscription, MapAsyncIterator)

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

        payload = subscription.__anext__()

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
        async def subscribe_fn(_data, _info):
            yield {"email": {"subject": "Hello"}}
            yield {"email": {"subject": "Goodbye"}}
            yield {"email": {"subject": "Bonjour"}}

        def resolve_fn(event, _info):
            if event["email"]["subject"] == "Goodbye":
                raise RuntimeError("Never leave")
            return event

        erroring_email_schema = email_schema_with_resolvers(subscribe_fn, resolve_fn)

        subscription = await subscribe(
            erroring_email_schema,
            parse(
                """
                subscription {
                  importantEmail {
                    email {
                      subject
                    }
                  }
                }
                """
            ),
        )

        payload1 = await anext(subscription)
        assert payload1 == ({"importantEmail": {"email": {"subject": "Hello"}}}, None)

        # An error in execution is presented as such.
        payload2 = await anext(subscription)
        assert payload2 == (
            {"importantEmail": None},
            [
                {
                    "message": "Never leave",
                    "locations": [(3, 19)],
                    "path": ["importantEmail"],
                }
            ],
        )

        # However that does not close the response event stream. Subsequent events are
        # still executed.
        payload3 = await anext(subscription)
        assert payload3 == ({"importantEmail": {"email": {"subject": "Bonjour"}}}, None)

    @mark.asyncio
    async def should_pass_through_error_thrown_in_source_event_stream():
        async def subscribe_fn(_data, _info):
            yield {"email": {"subject": "Hello"}}
            raise RuntimeError("test error")

        def resolve_fn(event, _info):
            return event

        erroring_email_schema = email_schema_with_resolvers(subscribe_fn, resolve_fn)

        subscription = await subscribe(
            schema=erroring_email_schema,
            document=parse(
                """
                subscription {
                  importantEmail {
                    email {
                      subject
                    }
                  }
                }
                """
            ),
        )

        payload1 = await anext(subscription)
        assert payload1 == ({"importantEmail": {"email": {"subject": "Hello"}}}, None)

        with raises(RuntimeError) as exc_info:
            await anext(subscription)

        assert str(exc_info.value) == "test error"

        with raises(StopAsyncIteration):
            await anext(subscription)

    @mark.asyncio
    async def should_work_with_async_resolve_function():
        async def subscribe_fn(_data, _info):
            yield {"email": {"subject": "Hello"}}

        async def resolve_fn(event, _info):
            return event

        async_email_schema = email_schema_with_resolvers(subscribe_fn, resolve_fn)

        subscription = await subscribe(
            schema=async_email_schema,
            document=parse(
                """
                subscription {
                  importantEmail {
                    email {
                      subject
                    }
                  }
                }
                """
            ),
        )

        payload = await anext(subscription)
        assert payload == ({"importantEmail": {"email": {"subject": "Hello"}}}, None)
