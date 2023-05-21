from functools import partial

from graphql.utilities import build_schema
from graphql.validation import DeferStreamDirectiveOnRootField

from .harness import assert_validation_errors


schema = build_schema(
    """
    type Message {
      body: String
      sender: String
    }

    type SubscriptionRoot {
      subscriptionField: Message
      subscriptionListField: [Message]
    }

    type MutationRoot {
      mutationField: Message
      mutationListField: [Message]
    }

    type QueryRoot {
      message: Message
      messages: [Message]
    }

    schema {
      query: QueryRoot
      mutation: MutationRoot
      subscription: SubscriptionRoot
    }
    """
)

assert_errors = partial(
    assert_validation_errors, DeferStreamDirectiveOnRootField, schema=schema
)

assert_valid = partial(assert_errors, errors=[])


def describe_defer_stream_on_root_field():
    def defer_fragments_spread_on_root_field():
        assert_valid(
            """
            {
              ...rootQueryFragment @defer
            }
            fragment rootQueryFragment on QueryRoot {
              message {
                body
              }
            }
            """
        )

    def defer_inline_fragment_spread_on_root_query_field():
        assert_valid(
            """
            {
              ... @defer {
                message {
                  body
                }
              }
            }
            """
        )

    def defer_fragment_spread_on_root_mutation_field():
        assert_errors(
            """
            mutation {
              ...rootFragment @defer
            }
            fragment rootFragment on MutationRoot {
              mutationField {
                body
              }
            }
            """,
            [
                {
                    "message": "Defer directive cannot be used on root"
                    " mutation type 'MutationRoot'.",
                    "locations": [(3, 31)],
                },
            ],
        )

    def defer_inline_fragment_spread_on_root_mutation_field():
        assert_errors(
            """
            mutation {
              ... @defer {
                mutationField {
                  body
                }
              }
            }
            """,
            [
                {
                    "message": "Defer directive cannot be used on root"
                    " mutation type 'MutationRoot'.",
                    "locations": [(3, 19)],
                },
            ],
        )

    def defer_fragment_spread_on_nested_mutation_field():
        assert_valid(
            """
            mutation {
              mutationField {
                ... @defer {
                  body
                }
              }
            }
            """
        )

    def defer_fragment_spread_on_root_subscription_field():
        assert_errors(
            """
            subscription {
              ...rootFragment @defer
            }
            fragment rootFragment on SubscriptionRoot {
              subscriptionField {
                body
              }
            }
            """,
            [
                {
                    "message": "Defer directive cannot be used on root"
                    " subscription type 'SubscriptionRoot'.",
                    "locations": [(3, 31)],
                },
            ],
        )

    def defer_inline_fragment_spread_on_root_subscription_field():
        assert_errors(
            """
            subscription {
              ... @defer {
                subscriptionField {
                  body
                }
              }
            }
            """,
            [
                {
                    "message": "Defer directive cannot be used on root"
                    " subscription type 'SubscriptionRoot'.",
                    "locations": [(3, 19)],
                },
            ],
        )

    def defer_fragment_spread_on_nested_subscription_field():
        assert_valid(
            """
            subscription {
              subscriptionField {
                ...nestedFragment
              }
            }
            fragment nestedFragment on Message {
              body
            }
            """
        )

    def stream_field_on_root_query_field():
        assert_valid(
            """
            {
              messages @stream {
                name
              }
            }
            """
        )

    def stream_field_on_fragment_on_root_query_field():
        assert_valid(
            """
            {
              ...rootFragment
            }
            fragment rootFragment on QueryType {
              messages @stream {
                name
              }
            }
            """
        )

    def stream_field_on_root_mutation_field():
        assert_errors(
            """
            mutation {
              mutationListField @stream {
                name
              }
            }
            """,
            [
                {
                    "message": "Stream directive cannot be used on root"
                    " mutation type 'MutationRoot'.",
                    "locations": [(3, 33)],
                },
            ],
        )

    def stream_field_on_fragment_on_root_mutation_field():
        assert_errors(
            """
            mutation {
              ...rootFragment
            }
            fragment rootFragment on MutationRoot {
              mutationListField @stream {
                name
              }
            }
            """,
            [
                {
                    "message": "Stream directive cannot be used on root"
                    " mutation type 'MutationRoot'.",
                    "locations": [(6, 33)],
                },
            ],
        )

    def stream_field_on_root_subscription_field():
        assert_errors(
            """
            subscription {
              subscriptionListField @stream {
                name
              }
            }
            """,
            [
                {
                    "message": "Stream directive cannot be used on root"
                    " subscription type 'SubscriptionRoot'.",
                    "locations": [(3, 37)],
                },
            ],
        )

    def stream_field_on_fragment_on_root_subscription_field():
        assert_errors(
            """
            subscription {
              ...rootFragment
            }
            fragment rootFragment on SubscriptionRoot {
              subscriptionListField @stream {
                name
              }
            }
            """,
            [
                {
                    "message": "Stream directive cannot be used on root"
                    " subscription type 'SubscriptionRoot'.",
                    "locations": [(6, 37)],
                },
            ],
        )
