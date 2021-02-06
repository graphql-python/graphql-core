from functools import partial

from graphql.utilities import build_schema
from graphql.validation import NoSchemaIntrospectionCustomRule

from .harness import assert_validation_errors

schema = build_schema(
    """
    type Query {
      someQuery: SomeType
    }

    type SomeType {
      someField: String
      introspectionField: __EnumValue
    }
    """
)

assert_errors = partial(
    assert_validation_errors, NoSchemaIntrospectionCustomRule, schema=schema
)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_prohibit_introspection_queries():
    def ignores_valid_fields_including_typename():
        assert_valid(
            """
            {
              someQuery {
                __typename
                someField
              }
            }
            """
        )

    def ignores_fields_not_in_the_schema():
        assert_valid(
            """
            {
              __introspect
            }
            """
        )

    def reports_error_when_a_field_with_an_introspection_type_is_requested():
        assert_errors(
            """
            {
              __schema {
                queryType {
                  name
                }
              }
            }
            """,
            [
                {
                    "message": "GraphQL introspection has been disabled,"
                    " but the requested query contained the field '__schema'.",
                    "locations": [(3, 15)],
                },
                {
                    "message": "GraphQL introspection has been disabled,"
                    " but the requested query contained the field 'queryType'.",
                    "locations": [(4, 17)],
                },
            ],
        )

    def reports_error_when_a_field_with_introspection_type_is_requested_and_aliased():
        assert_errors(
            """
            {
              s: __schema {
                queryType {
                  name
                }
              }
            }
            """,
            [
                {
                    "message": "GraphQL introspection has been disabled,"
                    " but the requested query contained the field '__schema'.",
                    "locations": [(3, 15)],
                },
                {
                    "message": "GraphQL introspection has been disabled,"
                    " but the requested query contained the field 'queryType'.",
                    "locations": [(4, 17)],
                },
            ],
        )

    def reports_error_when_using_a_fragment_with_a_field_with_an_introspection_type():
        assert_errors(
            """
            {
              ...QueryFragment
            }

            fragment QueryFragment on Query {
              __schema {
                queryType {
                  name
                }
              }
            }
            """,
            [
                {
                    "message": "GraphQL introspection has been disabled,"
                    " but the requested query contained the field '__schema'.",
                    "locations": [(7, 15)],
                },
                {
                    "message": "GraphQL introspection has been disabled,"
                    " but the requested query contained the field 'queryType'.",
                    "locations": [(8, 17)],
                },
            ],
        )

    def reports_error_for_non_standard_introspection_fields():
        assert_errors(
            """
            {
              someQuery {
                introspectionField
              }
            }
            """,
            [
                {
                    "message": "GraphQL introspection has been disabled, but"
                    " the requested query contained the field 'introspectionField'.",
                    "locations": [(4, 17)],
                },
            ],
        )
