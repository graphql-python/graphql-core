from graphql.utilities import (
    SafeChangeType,
    build_schema,
    find_schema_changes,
)


def describe_find_schema_changes():
    def should_detect_if_a_type_was_added():
        new_schema = build_schema(
            """
            type Type1
            type Type2
            """
        )

        old_schema = build_schema(
            """
            type Type1
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (SafeChangeType.TYPE_ADDED, "Type2 was added."),
        ]

    def should_detect_if_a_field_was_added():
        old_schema = build_schema(
            """
            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            type Query {
              foo: String
              bar: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (SafeChangeType.FIELD_ADDED, "Field Query.bar was added."),
        ]

    def should_detect_if_a_default_value_was_added():
        old_schema = build_schema(
            """
            type Query {
              foo(x: String): String
            }
            """
        )

        new_schema = build_schema(
            """
            type Query {
              foo(x: String = "bar"): String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.ARG_DEFAULT_VALUE_ADDED,
                'Query.foo(x:) added a defaultValue "bar".',
            ),
        ]

    def should_detect_if_an_arg_value_changes_safely():
        old_schema = build_schema(
            """
            type Query {
              foo(x: String!): String
            }
            """
        )

        new_schema = build_schema(
            """
            type Query {
              foo(x: String): String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.ARG_CHANGED_KIND_SAFE,
                "Argument Query.foo(x:) has changed type from String! to String.",
            ),
        ]

    def should_detect_if_a_directive_was_added():
        old_schema = build_schema(
            """
            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (SafeChangeType.DIRECTIVE_ADDED, "Directive @Foo was added."),
        ]

    def should_detect_if_a_directive_becomes_repeatable():
        old_schema = build_schema(
            """
            directive @Foo on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo repeatable on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DIRECTIVE_REPEATABLE_ADDED,
                "Repeatable flag was added to @Foo.",
            ),
        ]

    def should_detect_if_a_directive_adds_locations():
        old_schema = build_schema(
            """
            directive @Foo on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo on FIELD_DEFINITION | QUERY

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (SafeChangeType.DIRECTIVE_LOCATION_ADDED, "QUERY was added to @Foo."),
        ]

    def should_detect_if_a_directive_arg_gets_added():
        old_schema = build_schema(
            """
            directive @Foo on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo(arg1: String) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.OPTIONAL_DIRECTIVE_ARG_ADDED,
                "An optional argument @Foo(arg1:) was added.",
            ),
        ]
