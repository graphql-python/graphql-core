from functools import partial

from graphql.utilities import build_schema
from graphql.validation import SingleFieldSubscriptionsRule

from .harness import assert_validation_errors

schema = build_schema(
    """
    type Message {
      body: String
      sender: String
    }

    type SubscriptionRoot {
      importantEmails: [String]
      notImportantEmails: [String]
      moreImportantEmails: [String]
      spamEmails: [String]
      deletedEmails: [String]
      newMessage: Message
    }

    type QueryRoot {
      dummy: String
    }

    schema {
      query: QueryRoot
      subscription: SubscriptionRoot
    }
    """
)

assert_errors = partial(
    assert_validation_errors, SingleFieldSubscriptionsRule, schema=schema
)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_subscriptions_with_single_field():
    def valid_subscription():
        assert_valid(
            """
            subscription ImportantEmails {
              importantEmails
            }
            """
        )

    def valid_subscription_with_fragment():
        assert_valid(
            """
            subscription sub {
              ...newMessageFields
            }

            fragment newMessageFields on SubscriptionRoot {
              newMessage {
                body
                sender
              }
            }
            """
        )

    def valid_subscription_with_fragment_and_field():
        assert_valid(
            """
            subscription sub {
              newMessage {
                body
              }
              ...newMessageFields
            }

            fragment newMessageFields on SubscriptionRoot {
              newMessage {
                body
                sender
              }
            }
            """
        )

    def fails_with_more_than_one_root_field():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              notImportantEmails
            }
            """,
            [
                {
                    "message": "Subscription 'ImportantEmails'"
                    " must select only one top level field.",
                    "locations": [(4, 15)],
                }
            ],
        )

    def fails_with_more_than_one_root_field_including_introspection():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              __typename
            }
            """,
            [
                {
                    "message": "Subscription 'ImportantEmails'"
                    " must select only one top level field.",
                    "locations": [(4, 15)],
                },
                {
                    "message": "Subscription 'ImportantEmails'"
                    " must not select an introspection top level field.",
                    "locations": [(4, 15)],
                },
            ],
        )

    def fails_with_more_than_one_root_field_including_aliased_introspection():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              ...Introspection
            }
            fragment Introspection on SubscriptionRoot {
              typename: __typename
            }
            """,
            [
                {
                    "message": "Subscription 'ImportantEmails'"
                    " must select only one top level field.",
                    "locations": [(7, 15)],
                },
                {
                    "message": "Subscription 'ImportantEmails'"
                    " must not select an introspection top level field.",
                    "locations": [(7, 15)],
                },
            ],
        )

    def fails_with_many_more_than_one_root_field():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              notImportantEmails
              spamEmails
            }
            """,
            [
                {
                    "message": "Subscription 'ImportantEmails'"
                    " must select only one top level field.",
                    "locations": [(4, 15), (5, 15)],
                }
            ],
        )

    def fails_with_more_than_one_root_field_via_fragments():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              ... {
                more: moreImportantEmails
              }
              ...NotImportantEmails
            }
            fragment NotImportantEmails on SubscriptionRoot {
              notImportantEmails
              deleted: deletedEmails
              ...SpamEmails
            }
            fragment SpamEmails on SubscriptionRoot {
              spamEmails
            }
            """,
            [
                {
                    "message": "Subscription 'ImportantEmails'"
                    " must select only one top level field.",
                    "locations": [(5, 17), (10, 15), (11, 15), (15, 15)],
                },
            ],
        )

    def does_not_infinite_loop_on_recursive_fragments():
        assert_errors(
            """
            subscription NoInfiniteLoop {
              ...A
            }
            fragment A on SubscriptionRoot {
              ...A
            }
            """,
            [],
        )

    def fails_with_more_than_one_root_field_via_fragments_anonymous():
        assert_errors(
            """
            subscription {
              importantEmails
              ... {
                more: moreImportantEmails
                ...NotImportantEmails
              }
              ...NotImportantEmails
            }
            fragment NotImportantEmails on SubscriptionRoot {
              notImportantEmails
              deleted: deletedEmails
              ... {
                ... {
                  archivedEmails
                }
              }
              ...SpamEmails
            }
            fragment SpamEmails on SubscriptionRoot {
              spamEmails
              ...NonExistentFragment
            }
            """,
            [
                {
                    "message": "Anonymous Subscription"
                    " must select only one top level field.",
                    "locations": [(5, 17), (11, 15), (12, 15), (15, 19), (21, 15)],
                },
            ],
        )

    def fails_with_more_than_one_root_field_in_anonymous_subscriptions():
        assert_errors(
            """
            subscription {
              importantEmails
              notImportantEmails
            }
            """,
            [
                {
                    "message": "Anonymous Subscription"
                    " must select only one top level field.",
                    "locations": [(4, 15)],
                }
            ],
        )

    def fails_with_introspection_field():
        assert_errors(
            """
            subscription ImportantEmails {
              __typename
            }
            """,
            [
                {
                    "message": "Subscription 'ImportantEmails' must not"
                    " select an introspection top level field.",
                    "locations": [(3, 15)],
                }
            ],
        )

    def fails_with_introspection_field_in_anonymous_subscription():
        assert_errors(
            """
            subscription {
              __typename
            }
            """,
            [
                {
                    "message": "Anonymous Subscription must not"
                    " select an introspection top level field.",
                    "locations": [(3, 15)],
                }
            ],
        )

    def skips_if_not_subscription_type():
        empty_schema = build_schema(
            """
            type Query {
              dummy: String
            }
            """
        )
        assert_errors(
            """
            subscription {
              __typename
            }
            """,
            [],
            schema=empty_schema,
        )
