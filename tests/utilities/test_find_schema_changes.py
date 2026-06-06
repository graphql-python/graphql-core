from graphql.utilities import (
    BreakingChangeType,
    DangerousChangeType,
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

    def should_detect_a_type_changing_description():
        new_schema = build_schema(
            """
            "New Description"
            type Type1
            """
        )

        old_schema = build_schema(
            """
            type Type1
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DESCRIPTION_CHANGED,
                'Description of Type1 has changed to "New Description".',
            ),
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

    def should_detect_a_field_changing_description():
        old_schema = build_schema(
            """
            type Query {
              foo: String
              bar: String
            }
            """
        )

        new_schema = build_schema(
            """
            type Query {
              foo: String
              "New Description"
              bar: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DESCRIPTION_CHANGED,
                'Description of field Query.bar has changed to "New Description".',
            ),
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

    def should_detect_if_an_arg_value_changes_description():
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
              foo(
                "New Description"
                x: String!
              ): String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DESCRIPTION_CHANGED,
                "Description of argument Query.foo(x)"
                ' has changed to "New Description".',
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

    def should_detect_if_a_changes_argument_safely():
        old_schema = build_schema(
            """
            directive @Foo(foo: String!) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo(foo: String) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.ARG_CHANGED_KIND_SAFE,
                "Argument @Foo(foo:) has changed type from String! to String.",
            ),
        ]

    def should_detect_if_a_default_value_is_added_to_an_argument():
        old_schema = build_schema(
            """
            directive @Foo(foo: String) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo(foo: String = "Foo") on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.ARG_DEFAULT_VALUE_ADDED,
                '@Foo(foo:) added a defaultValue "Foo".',
            ),
        ]

    def should_detect_if_a_default_value_is_removed_from_an_argument():
        new_schema = build_schema(
            """
            directive @Foo(foo: String) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        old_schema = build_schema(
            """
            directive @Foo(foo: String = "Foo") on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                DangerousChangeType.ARG_DEFAULT_VALUE_CHANGE,
                "@Foo(foo:) defaultValue was removed.",
            ),
        ]

    def should_detect_if_a_default_value_is_changed_in_an_argument():
        old_schema = build_schema(
            """
            directive @Foo(foo: String = "Bar") on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo(foo: String = "Foo") on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                DangerousChangeType.ARG_DEFAULT_VALUE_CHANGE,
                '@Foo(foo:) has changed defaultValue from "Bar" to "Foo".',
            ),
        ]

    def should_detect_if_a_directive_argument_does_a_breaking_change():
        old_schema = build_schema(
            """
            directive @Foo(foo: String) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo(foo: String!) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                BreakingChangeType.ARG_CHANGED_KIND,
                "Argument @Foo(foo:) has changed type from String to String!.",
            ),
        ]

    def should_not_detect_if_a_directive_argument_default_value_does_not_change():
        old_schema = build_schema(
            """
            directive @Foo(foo: String = "FOO") on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo(foo: String = "FOO") on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == []

    def should_detect_if_a_directive_changes_description():
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
            "New Description"
            directive @Foo on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DESCRIPTION_CHANGED,
                'Description of @Foo has changed to "New Description".',
            ),
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

    def should_detect_if_a_directive_arg_changes_description():
        old_schema = build_schema(
            """
            directive @Foo(
              arg1: String
            ) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            directive @Foo(
              "New Description"
              arg1: String
            ) on FIELD_DEFINITION

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DESCRIPTION_CHANGED,
                'Description of @Foo(Foo) has changed to "New Description".',
            ),
        ]

    def should_detect_if_an_enum_member_changes_description():
        old_schema = build_schema(
            """
            enum Foo {
              TEST
            }

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            enum Foo {
              "New Description"
              TEST
            }

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DESCRIPTION_CHANGED,
                'Description of enum value Foo.TEST has changed to "New Description".',
            ),
        ]

    def should_detect_if_an_input_field_changes_description():
        old_schema = build_schema(
            """
            input Foo {
              x: String
            }

            type Query {
              foo: String
            }
            """
        )

        new_schema = build_schema(
            """
            input Foo {
              "New Description"
              x: String
            }

            type Query {
              foo: String
            }
            """
        )
        assert find_schema_changes(old_schema, new_schema) == [
            (
                SafeChangeType.DESCRIPTION_CHANGED,
                'Description of input-field Foo.x has changed to "New Description".',
            ),
        ]
