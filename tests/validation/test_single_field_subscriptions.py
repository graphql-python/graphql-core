from functools import partial

from pytest import raises

from graphql.error import GraphQLError
from graphql.language import DirectiveNode, Visitor, parse, visit
from graphql.utilities import build_schema
from graphql.validation import SingleFieldSubscriptionsRule, validate
from graphql.validation import validation_context as validation_context_module

from .harness import assert_validation_errors

schema = build_schema("""
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
    """)

assert_errors = partial(
    assert_validation_errors, SingleFieldSubscriptionsRule, schema=schema
)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_subscriptions_with_single_field():
    def accounts_for_include_and_custom_subscription_directives():
        document = parse("subscription { importantEmails @include(if: true) @custom }")
        assert validate(schema, document, [SingleFieldSubscriptionsRule]) == []

    def preserves_errors_for_directive_ast_nodes_without_argument_arrays():
        class RemoveArguments(Visitor):
            def enter_directive(self, node, *_args):
                return DirectiveNode(name=node.name, arguments=None, loc=node.loc)

        document = visit(
            parse("subscription { importantEmails @include }"), RemoveArguments()
        )
        with raises(GraphQLError) as exc_info:
            validate(schema, document, [SingleFieldSubscriptionsRule])
        assert (
            exc_info.value.message
            == "Argument 'if' of required type 'Boolean!' was not provided."
        )

    def bounds_repeated_subscription_fragment_and_directive_work():
        operations = "\n".join(f"subscription S{i} {{ ...F }}" for i in range(300))
        selections = "importantEmails @skip(if: false) " * 100
        fragment = f"fragment F on SubscriptionRoot {{ {selections} }}"
        errors = validate(
            schema, parse(operations + fragment), [SingleFieldSubscriptionsRule]
        )
        assert [error.message for error in errors] == ["Validation aborted."]

    def valid_subscription():
        assert_valid("""
            subscription ImportantEmails {
              importantEmails
            }
            """)

    def valid_subscription_with_fragment():
        assert_valid("""
            subscription sub {
              ...newMessageFields
            }

            fragment newMessageFields on SubscriptionRoot {
              newMessage {
                body
                sender
              }
            }
            """)

    def valid_subscription_with_fragment_and_field():
        assert_valid("""
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
            """)

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
        empty_schema = build_schema("""
            type Query {
              dummy: String
            }
            """)
        assert_errors(
            """
            subscription {
              __typename
            }
            """,
            [],
            schema=empty_schema,
        )

    def shared_fragment_in_multiple_subscriptions():
        assert_valid("""
            subscription sub {
              ...newMessageFields
            }
            subscription other {
              ...newMessageFields
            }

            fragment newMessageFields on SubscriptionRoot {
              importantEmails
            }
            """)

    def spends_fragment_work_like_graphql_js(monkeypatch):
        # A GraphQL-core-only test: the work counted here must equal the work counted
        # by GraphQL.js (2 definitions, 2 root selections, 2 directives, 1 argument of
        # @include, none of the custom directive, and 1 fragment selection).
        document = """
            subscription {
              ...newMessageFields @include(if: true) @custom(arg: 1)
              newMessage { body }
            }
            fragment newMessageFields on SubscriptionRoot {
              newMessage { body sender }
            }
            """
        monkeypatch.setattr(validation_context_module, "MAX_FRAGMENT_WORK", 8)
        assert_valid(document)
        monkeypatch.setattr(validation_context_module, "MAX_FRAGMENT_WORK", 7)
        assert_errors(document, [{"message": "Validation aborted."}])
