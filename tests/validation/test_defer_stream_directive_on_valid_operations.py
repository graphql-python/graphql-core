from functools import partial

from graphql.utilities import build_schema
from graphql.validation import DeferStreamDirectiveOnValidOperationsRule

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
    assert_validation_errors, DeferStreamDirectiveOnValidOperationsRule, schema=schema
)

assert_valid = partial(assert_errors, errors=[])


def describe_defer_stream_directive_on_valid_operations():
    def defer_fragment_spread_nested_in_query_operation():
        assert_valid(
            """
            {
              message {
                ...myFragment @defer
              }
            }
            fragment myFragment on Message {
              message {
                body
              }
            }
            """
        )

    def defer_inline_fragment_spread_in_query_operation():
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

    def defer_fragment_spread_on_mutation_field():
        assert_valid(
            """
            mutation {
              mutationField {
                ...myFragment @defer
              }
            }
            fragment myFragment on Message {
              body
            }
            """
        )

    def defer_inline_fragment_spread_on_mutation_field():
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

    def defer_fragment_spread_on_subscription_field():
        assert_errors(
            """
            subscription {
              subscriptionField {
                ...myFragment @defer
              }
            }
            fragment myFragment on Message {
              body
            }
            """,
            [
                {
                    "message": "Defer directive not supported"
                    " on subscription operations."
                    " Disable `@defer` by setting the `if` argument to `false`.",
                    "locations": [(4, 31)],
                },
            ],
        )

    def defer_fragment_spread_with_boolean_true_if_argument():
        assert_errors(
            """
            subscription {
              subscriptionField {
                ...myFragment @defer(if: true)
              }
            }
            fragment myFragment on Message {
              body
            }
            """,
            [
                {
                    "message": "Defer directive not supported"
                    " on subscription operations."
                    " Disable `@defer` by setting the `if` argument to `false`.",
                    "locations": [(4, 31)],
                },
            ],
        )

    def defer_fragment_spread_with_boolean_false_if_argument():
        assert_valid(
            """
            subscription {
              subscriptionField {
                ...myFragment @defer(if: false)
              }
            }
            fragment myFragment on Message {
              body
            }
            """
        )

    def defer_fragment_spread_on_query_in_multi_operation_document():
        assert_valid(
            """
            subscription MySubscription {
              subscriptionField {
                ...myFragment
              }
            }
            query MyQuery {
              message {
                ...myFragment @defer
              }
            }
            fragment myFragment on Message {
              body
            }
            """
        )

    def defer_fragment_spread_on_subscription_in_multi_operation_document():
        assert_errors(
            """
            subscription MySubscription {
              subscriptionField {
                ...myFragment @defer
              }
            }
            query MyQuery {
              message {
                ...myFragment @defer
              }
            }
            fragment myFragment on Message {
              body
            }
            """,
            [
                {
                    "message": "Defer directive not supported"
                    " on subscription operations."
                    " Disable `@defer` by setting the `if` argument to `false`.",
                    "locations": [(4, 31)],
                },
            ],
        )

    def defer_fragment_spread_with_invalid_if_argument():
        assert_errors(
            """
            subscription MySubscription {
              subscriptionField {
                ...myFragment @defer(if: "Oops")
              }
            }
            fragment myFragment on Message {
              body
            }
            """,
            [
                {
                    "message": "Defer directive not supported"
                    " on subscription operations."
                    " Disable `@defer` by setting the `if` argument to `false`.",
                    "locations": [(4, 31)],
                },
            ],
        )

    def stream_on_query_field():
        assert_valid(
            """
            {
              messages @stream {
                name
              }
            }
            """
        )

    def stream_on_mutation_field():
        assert_valid(
            """
            mutation {
              mutationField {
                messages @stream
              }
            }
            """
        )

    def stream_on_fragment_on_mutation_field():
        assert_valid(
            """
            mutation {
              mutationField {
                ...myFragment
              }
            }
            fragment myFragment on Message {
              messages @stream
            }
            """
        )

    def stream_on_subscription_field():
        assert_errors(
            """
            subscription {
              subscriptionField {
                messages @stream
              }
            }
            """,
            [
                {
                    "message": "Stream directive not supported"
                    " on subscription operations."
                    " Disable `@stream` by setting the `if` argument to `false`.",
                    "locations": [(4, 26)],
                },
            ],
        )

    def stream_on_fragment_on_subscription_field():
        assert_errors(
            """
            subscription {
              subscriptionField {
                ...myFragment
              }
            }
            fragment myFragment on Message {
              messages @stream
            }
            """,
            [
                {
                    "message": "Stream directive not supported"
                    " on subscription operations."
                    " Disable `@stream` by setting the `if` argument to `false`.",
                    "locations": [(8, 24)],
                },
            ],
        )

    def stream_on_fragment_on_query_in_multi_operation_document():
        assert_valid(
            """
            subscription MySubscription {
              subscriptionField {
                message
              }
            }
            query MyQuery {
              message {
                ...myFragment
              }
            }
            fragment myFragment on Message {
              messages @stream
            }
            """
        )

    def stream_on_subscription_in_multi_operation_document():
        assert_errors(
            """
            query MyQuery {
              message {
                ...myFragment
              }
            }
            subscription MySubscription {
              subscriptionField {
                message {
                  ...myFragment
                }
              }
            }
            fragment myFragment on Message {
              messages @stream
            }
            """,
            [
                {
                    "message": "Stream directive not supported"
                    " on subscription operations."
                    " Disable `@stream` by setting the `if` argument to `false`.",
                    "locations": [(15, 24)],
                },
            ],
        )

    def stream_with_boolean_false_if_argument():
        assert_valid(
            """
            subscription {
              subscriptionField {
                ...myFragment @stream(if:false)
              }
            }
            """
        )

    def stream_with_two_arguments():
        assert_valid(
            """
            subscription {
              subscriptionField {
                ...myFragment @stream(foo:false,if:false)
              }
            }
            """
        )

    def stream_with_variable_argument():
        assert_valid(
            """
            subscription ($stream: boolean!) {
              subscriptionField {
                ...myFragment @stream(if:$stream)
              }
            }
            """
        )

    def other_directive_on_subscription_field():
        assert_valid(
            """
            subscription {
              subscriptionField {
                ...myFragment @foo
              }
            }
            """
        )
