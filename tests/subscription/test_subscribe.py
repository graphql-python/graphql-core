from pytest import mark, raises  # type: ignore

from graphql.language import parse
from graphql.pyutils import EventEmitter, EventEmitterAsyncIterator
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
from graphql.subscription import subscribe

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


def email_schema_with_resolvers(subscribe_fn=None, resolve_fn=None):
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


async def create_subscription(
    pubsub, schema: GraphQLSchema = email_schema, ast=None, variables=None
):
    data = {
        "inbox": {
            "emails": [
                {
                    "from": "joe@graphql.org",
                    "subject": "Hello",
                    "message": "Hello World",
                    "unread": False,
                }
            ]
        },
        "importantEmail": lambda _info, priority=None: EventEmitterAsyncIterator(
            pubsub, "importantEmail"
        ),
    }

    def send_important_email(new_email):
        data["inbox"]["emails"].append(new_email)
        # Returns True if the event was consumed by a subscriber.
        return pubsub.emit(
            "importantEmail",
            {"importantEmail": {"email": new_email, "inbox": data["inbox"]}},
        )

    default_ast = parse(
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

    # `subscribe` yields AsyncIterator or ExecutionResult
    return (
        send_important_email,
        await subscribe(schema, ast or default_ast, data, variable_values=variables),
    )


# Check all error cases when initializing the subscription.
def describe_subscription_initialization_phase():
    @mark.asyncio
    async def accepts_an_object_with_named_properties_as_arguments():
        document = parse(
            """
            subscription {
              importantEmail
            }
            """
        )

        async def empty_async_iterator(_info):
            for value in ():
                yield value

        await subscribe(
            email_schema, document, {"importantEmail": empty_async_iterator}
        )

    @mark.asyncio
    async def accepts_multiple_subscription_fields_defined_in_schema():
        pubsub = EventEmitter()
        SubscriptionTypeMultiple = GraphQLObjectType(
            "Subscription",
            {
                "importantEmail": GraphQLField(EmailEventType),
                "nonImportantEmail": GraphQLField(EmailEventType),
            },
        )

        test_schema = GraphQLSchema(
            query=QueryType, subscription=SubscriptionTypeMultiple
        )

        send_important_email, subscription = await create_subscription(
            pubsub, test_schema
        )

        send_important_email(
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
        pubsub = EventEmitter()

        def subscribe_email(_inbox, _info):
            return EventEmitterAsyncIterator(pubsub, "importantEmail")

        schema = GraphQLSchema(
            query=QueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "importantEmail": GraphQLField(
                        GraphQLString, subscribe=subscribe_email
                    )
                },
            ),
        )

        ast = parse(
            """
            subscription {
              importantEmail
            }
            """
        )

        subscription = await subscribe(schema, ast)

        pubsub.emit("importantEmail", {"importantEmail": {}})

        await anext(subscription)

    @mark.asyncio
    async def accepts_type_definition_with_async_subscribe_function():
        pubsub = EventEmitter()

        async def subscribe_email(_inbox, _info):
            return EventEmitterAsyncIterator(pubsub, "importantEmail")

        schema = GraphQLSchema(
            query=QueryType,
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "importantEmail": GraphQLField(
                        GraphQLString, subscribe=subscribe_email
                    )
                },
            ),
        )

        ast = parse(
            """
            subscription {
              importantEmail
            }
            """
        )

        subscription = await subscribe(schema, ast)

        pubsub.emit("importantEmail", {"importantEmail": {}})

        await anext(subscription)

    @mark.asyncio
    async def should_only_resolve_the_first_field_of_invalid_multi_field():
        did_resolve = {"importantEmail": False, "nonImportantEmail": False}

        def subscribe_important(_inbox, _info):
            did_resolve["importantEmail"] = True
            return EventEmitterAsyncIterator(EventEmitter(), "event")

        def subscribe_non_important(_inbox, _info):
            did_resolve["nonImportantEmail"] = True
            return EventEmitterAsyncIterator(EventEmitter(), "event")

        SubscriptionTypeMultiple = GraphQLObjectType(
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

        test_schema = GraphQLSchema(
            query=QueryType, subscription=SubscriptionTypeMultiple
        )

        ast = parse(
            """
            subscription {
              importantEmail
              nonImportantEmail
            }
            """
        )

        subscription = await subscribe(test_schema, ast)
        ignored = anext(subscription)  # Ask for a result, but ignore it.

        assert did_resolve["importantEmail"] is True
        assert did_resolve["nonImportantEmail"] is False

        # Close subscription
        # noinspection PyUnresolvedReferences
        await subscription.aclose()

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
            await subscribe(None, document)

        assert str(exc_info.value) == "Expected None to be a GraphQL schema."

        with raises(TypeError, match="missing .* positional argument: 'schema'"):
            # noinspection PyTypeChecker
            await subscribe(document=document)

    # noinspection PyArgumentList
    @mark.asyncio
    async def throws_an_error_if_document_is_missing():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            await subscribe(email_schema, None)

        assert str(exc_info.value) == "Must provide document"

        with raises(TypeError, match="missing .* positional argument: 'document'"):
            # noinspection PyTypeChecker
            await subscribe(schema=email_schema)

    @mark.asyncio
    async def resolves_to_an_error_for_unknown_subscription_field():
        ast = parse(
            """
            subscription {
              unknownField
            }
            """
        )

        pubsub = EventEmitter()

        subscription = (await create_subscription(pubsub, ast=ast))[1]

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

        pubsub = EventEmitter()

        with raises(TypeError) as exc_info:
            await create_subscription(pubsub, invalid_email_schema)

        assert str(exc_info.value) == (
            "Subscription field must return AsyncIterable. Received: 'test'"
        )

    @mark.asyncio
    async def resolves_to_an_error_for_subscription_resolver_errors():
        async def test_reports_error(schema):
            result = await subscribe(
                schema,
                parse(
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

        pubsub = EventEmitter()
        data = {
            "inbox": {
                "emails": [
                    {
                        "from": "joe@graphql.org",
                        "subject": "Hello",
                        "message": "Hello World",
                        "unread": False,
                    }
                ]
            },
            "importantEmail": lambda _info: EventEmitterAsyncIterator(
                pubsub, "importantEmail"
            ),
        }

        result = await subscribe(
            email_schema, ast, data, variable_values={"priority": "meow"}
        )

        assert result == (
            None,
            [
                {
                    "message": "Variable '$priority' got invalid value 'meow'; Expected"
                    " type Int. Int cannot represent non-integer value: 'meow'",
                    "locations": [(2, 27)],
                }
            ],
        )

        assert result.errors[0].original_error is not None


# Once a subscription returns a valid AsyncIterator, it can still yield errors.
def describe_subscription_publish_phase():
    @mark.asyncio
    async def produces_a_payload_for_multiple_subscribe_in_same_subscription():
        pubsub = EventEmitter()
        send_important_email, subscription = await create_subscription(pubsub)
        second = await create_subscription(pubsub)

        payload1 = anext(subscription)
        payload2 = anext(second[1])

        assert (
            send_important_email(
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
        pubsub = EventEmitter()
        send_important_email, subscription = await create_subscription(pubsub)

        # Wait for the next subscription payload.
        payload = anext(subscription)

        # A new email arrives!
        assert (
            send_important_email(
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
            send_important_email(
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
            send_important_email(
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
    async def event_order_is_correct_for_multiple_publishes():
        pubsub = EventEmitter()
        send_important_email, subscription = await create_subscription(pubsub)

        payload = anext(subscription)

        # A new email arrives!
        assert (
            send_important_email(
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
            send_important_email(
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
            async_email_schema,
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

        payload = await anext(subscription)
        assert payload == ({"importantEmail": {"email": {"subject": "Hello"}}}, None)
