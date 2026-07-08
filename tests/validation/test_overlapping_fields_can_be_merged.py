from functools import partial

import pytest

from graphql import parse, validate
from graphql.utilities import build_schema
from graphql.validation import OverlappingFieldsCanBeMergedRule

from .harness import assert_validation_errors, test_schema

assert_errors = partial(assert_validation_errors, OverlappingFieldsCanBeMergedRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_overlapping_fields_can_be_merged():
    def describe_fragment_arguments_must_produce_fields_that_can_be_merged():
        def allows_conflicting_spreads_at_different_depths():
            assert_valid(
                """
                query ValidDifferingFragmentArgs(
                  $command1: DogCommand, $command2: DogCommand
                ) {
                  dog {
                    ...DoesKnowCommand(command: $command1)
                    mother {
                      ...DoesKnowCommand(command: $command2)
                    }
                  }
                }
                fragment DoesKnowCommand($command: DogCommand) on Dog {
                  doesKnowCommand(dogCommand: $command)
                }
                """
            )

        def allows_spreads_without_provided_arguments():
            assert_valid(
                """
                {
                  ...WithArgs
                  ...WithArgs
                }
                fragment WithArgs($x: Int) on Type {
                  a(x: $x)
                }
                """
            )

        def encounters_conflict_in_fragments():
            assert_errors(
                """
                {
                  ...WithArgs(x: 3)
                  ...WithArgs(x: 4)
                }
                fragment WithArgs($x: Int) on Type {
                  a(x: $x)
                }
                """,
                [
                    {
                        "message": "Spreads 'WithArgs' conflict because"
                        " WithArgs(x: 3) and WithArgs(x: 4)"
                        " have different fragment arguments.",
                        "locations": [(3, 19), (4, 19)],
                    },
                ],
            )

        def allows_overlapping_fields_with_identical_operation_variables():
            assert_valid(
                """
                query ($y: Int = 1) {
                  a(x: $y)
                  ...WithArgs(x: 1)
                }
                fragment WithArgs($x: Int = 1) on Type {
                  a(x: $y)
                }
                """
            )

        def allows_overlapping_fields_with_identical_variable_args_via_fragment():
            assert_valid(
                """
                query ($y: Int = 1) {
                  a(x: $y)
                  ...WithArgs(x: $y)
                }
                fragment WithArgs($x: Int) on Type {
                  a(x: $x)
                }
                """
            )

        def allows_overlapping_fields_with_identical_args_via_nested_fragment():
            assert_valid(
                """
                query ($z: Int = 1) {
                  a(x: $z)
                  ...WithArgs(y: $z)
                }
                fragment WithArgs($y: Int) on Type {
                  ...NestedWithArgs(x: $y)
                }
                fragment NestedWithArgs($x: Int) on Type {
                  a(x: $x)
                }
                """
            )

        def allows_overlapping_fields_with_identical_args_via_fragment_defaults():
            assert_valid(
                """
                query {
                  a(x: 1)
                  ...WithArgs
                }
                fragment WithArgs($x: Int = 1) on Type {
                  a(x: $x)
                }
                """
            )

        def raises_errors_with_conflicting_args_via_operation_variables():
            assert_errors(
                """
                query ($y: Int = 1) {
                  a(x: $y)
                  ...WithArgs
                }
                fragment WithArgs($x: Int = 1) on Type {
                  a(x: $x)
                }
                """,
                [
                    {
                        "message": "Fields 'a' conflict because they have"
                        " differing arguments. Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(3, 19), (7, 19)],
                    },
                ],
            )

        def allows_overlapping_list_fields_with_identical_variable_args():
            assert_valid(
                """
                query Query($stringListVarY: [String]) {
                  complicatedArgs {
                    stringListArgField(stringListArg: $stringListVarY)
                    ...WithArgs(stringListVarX: $stringListVarY)
                  }
                }
                fragment WithArgs($stringListVarX: [String]) on Type {
                  stringListArgField(stringListArg: $stringListVarX)
                }
                """
            )

        def allows_overlapping_list_fields_with_identical_item_variable_args():
            assert_valid(
                """
                query Query($stringListVarY: [String]) {
                  complicatedArgs {
                    stringListArgField(stringListArg: [$stringListVarY])
                    ...WithArgs(stringListVarX: $stringListVarY)
                  }
                }
                fragment WithArgs($stringListVarX: [String]) on Type {
                  stringListArgField(stringListArg: [$stringListVarX])
                }
                """
            )

        def allows_overlapping_input_object_fields_with_identical_variable_args():
            assert_valid(
                """
                query Query($complexVarY: ComplexInput) {
                  complicatedArgs {
                    complexArgField(complexArg: $complexVarY)
                    ...WithArgs(complexVarX: $complexVarY)
                  }
                }
                fragment WithArgs($complexVarX: ComplexInput) on Type {
                  complexArgField(complexArg: $complexVarX)
                }
                """
            )

        def allows_overlapping_input_object_fields_with_identical_field_var_args():
            assert_valid(
                """
                query Query($boolVarY: Boolean) {
                  complicatedArgs {
                    complexArgField(complexArg: {requiredArg: $boolVarY})
                    ...WithArgs(boolVarX: $boolVarY)
                  }
                }
                fragment WithArgs($boolVarX: Boolean) on Type {
                  complexArgField(complexArg: {requiredArg: $boolVarX})
                }
                """
            )

        def encounters_nested_field_conflict_in_fragments_that_could_merge():
            assert_errors(
                """
                query ValidDifferingFragmentArgs(
                  $command1: DogCommand, $command2: DogCommand
                ) {
                  dog {
                    ...DoesKnowCommandNested(command: $command1)
                    mother {
                      ...DoesKnowCommandNested(command: $command2)
                    }
                  }
                }
                fragment DoesKnowCommandNested($command: DogCommand) on Dog {
                  doesKnowCommand(dogCommand: $command)
                  mother {
                    doesKnowCommand(dogCommand: $command)
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'mother' conflict because subfields"
                        " 'doesKnowCommand' conflict because they have differing"
                        " arguments. Use different aliases on the fields to fetch"
                        " both if this was intentional.",
                        "locations": [(7, 21), (15, 21), (14, 19), (13, 19)],
                    },
                ],
            )

        def encounters_nested_conflict_in_fragments():
            assert_errors(
                """
                {
                  connection {
                    edges {
                      ...WithArgs(x: 3)
                    }
                  }
                  ...Connection
                }
                fragment Connection on Type {
                  connection {
                    edges {
                      ...WithArgs(x: 4)
                    }
                  }
                }
                fragment WithArgs($x: Int) on Type {
                  a(x: $x)
                }
                """,
                [
                    {
                        "message": "Spreads 'WithArgs' conflict because"
                        " WithArgs(x: 3) and WithArgs(x: 4)"
                        " have different fragment arguments.",
                        "locations": [(5, 23), (13, 23)],
                    },
                ],
            )

    def unique_fields():
        assert_valid(
            """
            fragment uniqueFields on Dog {
              name
              nickname
            }
            """
        )

    def identical_fields():
        assert_valid(
            """
            fragment mergeIdenticalFields on Dog {
              name
              name
            }
            """
        )

    def identical_fields_with_identical_args():
        assert_valid(
            """
            fragment mergeIdenticalFieldsWithIdenticalArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
              doesKnowCommand(dogCommand: SIT)
            }
            """
        )

    def identical_fields_with_identical_directives():
        assert_valid(
            """
            fragment mergeSameFieldsWithSameDirectives on Dog {
              name @include(if: true)
              name @include(if: true)
            }
            """
        )

    def different_args_with_different_aliases():
        assert_valid(
            """
            fragment differentArgsWithDifferentAliases on Dog {
              knowsSit: doesKnowCommand(dogCommand: SIT)
              knowsDown: doesKnowCommand(dogCommand: DOWN)
            }
            """
        )

    def different_directives_with_different_aliases():
        assert_valid(
            """
            fragment differentDirectivesWithDifferentAliases on Dog {
              nameIfTrue: name @include(if: true)
              nameIfFalse: name @include(if: false)
            }
            """
        )

    def different_skip_or_include_directives_accepted():
        # Note: Differing skip/include directives don't create an ambiguous
        # return value and are acceptable in conditions where differing runtime
        # values may have the same desired effect of including/skipping a field
        assert_valid(
            """
            fragment differentDirectivesWithDifferentAliases on Dog {
              name @include(if: true)
              name @include(if: false)
            }
            """
        )

    def same_stream_directives_supported():
        assert_valid(
            """
            fragment differentDirectivesWithDifferentAliases on Dog {
              name @stream(label: "streamLabel", initialCount: 1)
              name @stream(label: "streamLabel", initialCount: 1)
            }
            """
        )

    def different_stream_directive_label():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              name @stream(label: "streamLabel", initialCount: 1)
              name @stream(label: "anotherLabel", initialCount: 1)
            }
            """,
            [
                {
                    "message": "Fields 'name' conflict because they have differing"
                    " stream directives. Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_stream_directive_initial_count():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              name @stream(label: "streamLabel", initialCount: 1)
              name @stream(label: "streamLabel", initialCount: 2)
            }
            """,
            [
                {
                    "message": "Fields 'name' conflict because they have differing"
                    " stream directives. Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_stream_directive_first_missing_args():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              name @stream
              name @stream(label: "streamLabel", initialCount: 1)
            }
            """,
            [
                {
                    "message": "Fields 'name' conflict because they have differing"
                    " stream directives. Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_stream_directive_second_missing_args():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              name @stream(label: "streamLabel", initialCount: 1)
              name @stream
            }
            """,
            [
                {
                    "message": "Fields 'name' conflict because they have differing"
                    " stream directives. Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_stream_directive_extra_argument():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              name @stream(label: "streamLabel", initialCount: 1)
              name @stream(label: "streamLabel", initialCount: 1, extraArg: true)
            }""",
            [
                {
                    "message": "Fields 'name' conflict because they have differing"
                    " stream directives. Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def mix_of_stream_and_no_stream():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              name @stream
              name
            }
            """,
            [
                {
                    "message": "Fields 'name' conflict because they have differing"
                    " stream directives. Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def same_stream_directive_both_missing_args():
        assert_valid(
            """
            fragment conflictingArgs on Dog {
              name @stream
              name @stream
            }
            """
        )

    def same_aliases_with_different_field_targets():
        assert_errors(
            """
            fragment sameAliasesWithDifferentFieldTargets on Dog {
              fido: name
              fido: nickname
            }
            """,
            [
                {
                    "message": "Fields 'fido' conflict"
                    " because 'name' and 'nickname' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                    "path": None,
                }
            ],
        )

    def same_aliases_allowed_on_non_overlapping_fields():
        assert_valid(
            """
            fragment sameAliasesWithDifferentFieldTargets on Pet {
              ... on Dog {
                name
              }
              ... on Cat {
                name: nickname
              }
            }
            """
        )

    def alias_masking_direct_field_access():
        assert_errors(
            """
            fragment aliasMaskingDirectFieldAccess on Dog {
              name: nickname
              name
            }
            """,
            [
                {
                    "message": "Fields 'name' conflict"
                    " because 'nickname' and 'name' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_args_second_adds_an_argument():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              doesKnowCommand
              doesKnowCommand(dogCommand: HEEL)
            }
            """,
            [
                {
                    "message": "Fields 'doesKnowCommand' conflict"
                    " because they have differing arguments."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_args_second_missing_an_argument():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
              doesKnowCommand
            }
            """,
            [
                {
                    "message": "Fields 'doesKnowCommand' conflict"
                    " because they have differing arguments."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def conflicting_arg_values():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
              doesKnowCommand(dogCommand: HEEL)
            }
            """,
            [
                {
                    "message": "Fields 'doesKnowCommand' conflict"
                    " because they have differing arguments."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def conflicting_arg_names():
        assert_errors(
            """
            fragment conflictingArgs on Dog {
              isAtLocation(x: 0)
              isAtLocation(y: 0)
            }
            """,
            [
                {
                    "message": "Fields 'isAtLocation' conflict"
                    " because they have differing arguments."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def allows_different_args_where_no_conflict_is_possible():
        # This is valid since no object can be both a "Dog" and a "Cat", thus
        # these fields can never overlap.
        assert_valid(
            """
            fragment conflictingArgs on Pet {
              ... on Dog {
                name(surname: true)
              }
              ... on Cat {
                name
              }
            }
            """
        )

    def allows_different_order_of_args():
        schema = build_schema(
            """
            type Query {
              someField(a: String, b: String): String
            }
            """
        )
        # This is valid since arguments are unordered, see:
        # https://spec.graphql.org/draft/#
        # sec-Language.Arguments.Arguments-are-unordered
        assert_valid(
            """
            {
              someField(a: null, b: null)
              someField(b: null, a: null)
            }
            """,
            schema=schema,
        )

    def allows_different_order_of_input_object_fields_in_arg_values():
        schema = build_schema(
            """
            input SomeInput {
              a: String
              b: String
            }

            type Query {
              someField(arg: SomeInput): String
            }
            """
        )
        # This is valid since input object fields are unordered, see:
        # https://spec.graphql.org/draft/#
        # sec-Input-Object-Values.Input-object-fields-are-unordered
        assert_valid(
            """
            {
              someField(arg: { a: null, b: null })
              someField(arg: { b: null, a: null })
            }
            """,
            schema=schema,
        )

    def encounters_conflict_in_fragments():
        assert_errors(
            """
            {
              ...A
              ...B
            }
            fragment A on Type {
              x: a
            }
            fragment B on Type {
              x: b
            }
            """,
            [
                {
                    "message": "Fields 'x' conflict"
                    " because 'a' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(7, 15), (10, 15)],
                }
            ],
        )

    def reports_each_conflict_once():
        assert_errors(
            """
            {
              f1 {
                ...A
                ...B
              }
              f2 {
                ...B
                ...A
              }
              f3 {
                ...A
                ...B
                x: c
              }
            }
            fragment A on Type {
              x: a
            }
            fragment B on Type {
              x: b
            }
            """,
            [
                {
                    "message": "Fields 'x' conflict"
                    " because 'a' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(18, 15), (21, 15)],
                },
                {
                    "message": "Fields 'x' conflict"
                    " because 'c' and 'a' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(14, 17), (18, 15)],
                },
                {
                    "message": "Fields 'x' conflict"
                    " because 'c' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(14, 17), (21, 15)],
                },
            ],
        )

    def deep_conflict():
        assert_errors(
            """
            {
              field {
                x: a
              },
              field {
                x: b
              }
            }
            """,
            [
                {
                    "message": "Fields 'field' conflict"
                    " because subfields 'x' conflict"
                    " because 'a' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 17), (6, 15), (7, 17)],
                }
            ],
        )

    def deep_conflict_with_multiple_issues():
        assert_errors(
            """
            {
              field {
                x: a
                y: c
              },
              field {
                x: b
                y: d
              }
            }
            """,
            [
                {
                    "message": "Fields 'field' conflict"
                    " because subfields 'x' conflict"
                    " because 'a' and 'b' are different fields"
                    " and subfields 'y' conflict"
                    " because 'c' and 'd' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (4, 17), (5, 17), (7, 15), (8, 17), (9, 17)],
                    "path": None,
                }
            ],
        )

    def very_deep_conflict():
        assert_errors(
            """
            {
              field {
                deepField {
                  x: a
                }
              },
              field {
                deepField {
                  x: b
                }
              }
            }
            """,
            [
                {
                    "message": "Fields 'field' conflict"
                    " because subfields 'deepField' conflict"
                    " because subfields 'x' conflict"
                    " because 'a' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [
                        (3, 15),
                        (4, 17),
                        (5, 19),
                        (8, 15),
                        (9, 17),
                        (10, 19),
                    ],
                    "path": None,
                }
            ],
        )

    def reports_deep_conflict_to_nearest_common_ancestor():
        assert_errors(
            """
            {
              field {
                deepField {
                  x: a
                }
                deepField {
                  x: b
                }
              },
              field {
                deepField {
                  y
                }
              }
            }
            """,
            [
                {
                    "message": "Fields 'deepField' conflict"
                    " because subfields 'x' conflict"
                    " because 'a' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(4, 17), (5, 19), (7, 17), (8, 19)],
                }
            ],
        )

    def reports_deep_conflict_to_nearest_common_ancestor_in_fragments():
        assert_errors(
            """
            {
              field {
                ...F
              }
              field {
                ...F
              }
            }
            fragment F on T {
              deepField {
                deeperField {
                  x: a
                }
                deeperField {
                  x: b
                }
              },
              deepField {
                deeperField {
                  y
                }
              }
            }
            """,
            [
                {
                    "message": "Fields 'deeperField' conflict"
                    " because subfields 'x' conflict"
                    " because 'a' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(12, 17), (13, 19), (15, 17), (16, 19)],
                }
            ],
        )

    def reports_deep_conflict_in_nested_fragments():
        assert_errors(
            """
            {
              field {
                ...F
              },
              field {
                ...I
              }
            }
            fragment F on T {
              x: a
              ...G
            }
            fragment G on T {
              y: c
            }
            fragment I on T {
              y: d
              ...J
            }
            fragment J on T {
              x: b
            }
            """,
            [
                {
                    "message": "Fields 'field' conflict"
                    " because subfields 'x' conflict"
                    " because 'a' and 'b' are different fields"
                    " and subfields 'y' conflict"
                    " because 'c' and 'd' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [
                        (3, 15),
                        (11, 15),
                        (15, 15),
                        (6, 15),
                        (22, 15),
                        (18, 15),
                    ],
                    "path": None,
                }
            ],
        )

    def reports_deep_conflict_after_nested_fragments():
        assert_errors(
            """
            fragment F on T {
              ...G
            }
            fragment G on T {
              ...H
            }
            fragment H on T {
              x: a
            }
            {
              x: b
              ...F
            }
            """,
            [
                {
                    "message": "Fields 'x' conflict"
                    " because 'b' and 'a' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(12, 15), (9, 15)],
                    "path": None,
                }
            ],
        )

    def ignores_unknown_fragments():
        assert_valid(
            """
            {
              field
              ...Unknown
              ...Known
            }

            fragment Known on T {
              field
              ...OtherUnknown
            }
            """
        )

    def describe_return_types_must_be_unambiguous():
        schema = build_schema(
            """
            interface SomeBox {
              deepBox: SomeBox
              unrelatedField: String
            }

            type StringBox implements SomeBox {
              scalar: String
              deepBox: StringBox
              unrelatedField: String
              listStringBox: [StringBox]
              stringBox: StringBox
              intBox: IntBox
            }

            type IntBox implements SomeBox {
              scalar: Int
              deepBox: IntBox
              unrelatedField: String
              listStringBox: [StringBox]
              stringBox: StringBox
              intBox: IntBox
            }

            interface NonNullStringBox1 {
              scalar: String!
            }

            type NonNullStringBox1Impl implements SomeBox & NonNullStringBox1 {
              scalar: String!
              unrelatedField: String
              deepBox: SomeBox
            }

            interface NonNullStringBox2 {
              scalar: String!
            }

            type NonNullStringBox2Impl implements SomeBox & NonNullStringBox2 {
              scalar: String!
              unrelatedField: String
              deepBox: SomeBox
            }

            type Connection {
              edges: [Edge]
            }

            type Edge {
              node: Node
            }

            type Node {
              id: ID
              name: String
            }

            type Query {
              someBox: SomeBox
              connection: Connection
            }
            """
        )

        def conflicting_return_types_which_potentially_overlap():
            # This is invalid since an object could potentially be both the
            # Object type IntBox and the interface type NonNullStringBox1.
            # While that condition does not exist in the current schema, the
            # schema could expand in the future to allow this.
            assert_errors(
                """
                {
                  someBox {
                    ...on IntBox {
                      scalar
                    }
                    ...on NonNullStringBox1 {
                      scalar
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'scalar' conflict because"
                        " they return conflicting types 'Int' and 'String!'."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(5, 23), (8, 23)],
                    }
                ],
                schema,
            )

        def compatible_return_shapes_on_different_return_types():
            # In this case `deepBox` returns `SomeBox` in the first usage, and
            # `StringBox` in the second usage. These types are not the same!
            # However this is valid because the return *shapes* are compatible.
            assert_valid(
                """
                {
                  someBox {
                      ... on SomeBox {
                      deepBox {
                        unrelatedField
                      }
                    }
                    ... on StringBox {
                      deepBox {
                        unrelatedField
                      }
                    }
                  }
                }
                """,
                schema=schema,
            )

        def disallows_differing_return_types_despite_no_overlap():
            assert_errors(
                """
                {
                  someBox {
                    ... on IntBox {
                      scalar
                    }
                    ... on StringBox {
                      scalar
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'scalar' conflict because"
                        " they return conflicting types 'Int' and 'String'."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(5, 23), (8, 23)],
                    }
                ],
                schema,
            )

        def reports_correctly_when_a_non_exclusive_follows_an_exclusive():
            assert_errors(
                """
                {
                  someBox {
                    ... on IntBox {
                      deepBox {
                        ...X
                      }
                    }
                  }
                  someBox {
                    ... on StringBox {
                      deepBox {
                        ...Y
                      }
                    }
                  }
                  memoed: someBox {
                    ... on IntBox {
                      deepBox {
                        ...X
                      }
                    }
                  }
                  memoed: someBox {
                    ... on StringBox {
                      deepBox {
                        ...Y
                      }
                    }
                  }
                  other: someBox {
                    ...X
                  }
                  other: someBox {
                    ...Y
                  }
                }
                fragment X on SomeBox {
                  scalar
                }
                fragment Y on SomeBox {
                  scalar: unrelatedField
                }
                """,
                [
                    {
                        "message": "Fields 'other' conflict because"
                        " subfields 'scalar' conflict because"
                        " 'scalar' and 'unrelatedField' are different fields."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(31, 19), (39, 19), (34, 19), (42, 19)],
                        "path": None,
                    }
                ],
                schema,
            )

        def disallows_differing_return_type_nullability_despite_no_overlap():
            assert_errors(
                """
                {
                  someBox {
                    ... on NonNullStringBox1 {
                      scalar
                    }
                    ... on StringBox {
                      scalar
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'scalar' conflict because"
                        " they return conflicting types 'String!' and 'String'."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(5, 23), (8, 23)],
                    }
                ],
                schema,
            )

        def disallows_differing_return_type_list_despite_no_overlap_1():
            assert_errors(
                """
                {
                  someBox {
                    ... on IntBox {
                      box: listStringBox {
                        scalar
                      }
                    }
                    ... on StringBox {
                      box: stringBox {
                        scalar
                      }
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'box' conflict because they return"
                        " conflicting types '[StringBox]' and 'StringBox'."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(5, 23), (10, 23)],
                    }
                ],
                schema,
            )

            assert_errors(
                """
                {
                  someBox {
                    ... on IntBox {
                      box: stringBox {
                        scalar
                      }
                    }
                    ... on StringBox {
                      box: listStringBox {
                        scalar
                      }
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'box' conflict because they return"
                        " conflicting types 'StringBox' and '[StringBox]'."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(5, 23), (10, 23)],
                    }
                ],
                schema,
            )

        def disallows_differing_subfields():
            assert_errors(
                """
                {
                  someBox {
                    ... on IntBox {
                      box: stringBox {
                        val: scalar
                        val: unrelatedField
                      }
                    }
                    ... on StringBox {
                      box: stringBox {
                        val: scalar
                      }
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'val' conflict because"
                        " 'scalar' and 'unrelatedField' are different fields."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(6, 25), (7, 25)],
                    }
                ],
                schema,
            )

        def disallows_differing_deep_return_types_despite_no_overlap():
            assert_errors(
                """
                {
                  someBox {
                    ... on IntBox {
                      box: stringBox {
                        scalar
                      }
                    }
                    ... on StringBox {
                      box: intBox {
                        scalar
                      }
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'box' conflict"
                        " because subfields 'scalar' conflict"
                        " because they return conflicting types 'String' and 'Int'."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [(5, 23), (6, 25), (10, 23), (11, 25)],
                        "path": None,
                    }
                ],
                schema,
            )

        def allows_non_conflicting_overlapping_types():
            assert_valid(
                """
                {
                  someBox {
                    ... on IntBox {
                      scalar: unrelatedField
                    }
                    ... on StringBox {
                      scalar
                    }
                  }
                }
                """,
                schema=schema,
            )

        def same_wrapped_scalar_return_types():
            assert_valid(
                """
                {
                  someBox {
                    ...on NonNullStringBox1 {
                      scalar
                    }
                    ...on NonNullStringBox2 {
                      scalar
                    }
                  }
                }
                """,
                schema=schema,
            )

        def allows_inline_fragments_without_type_condition():
            assert_valid(
                """
                {
                  a
                  ... {
                    a
                  }
                }
                """,
                schema=schema,
            )

        def compares_deep_types_including_list():
            assert_errors(
                """
                {
                  connection {
                    ...edgeID
                    edges {
                      node {
                        id: name
                      }
                    }
                  }
                }

                fragment edgeID on Connection {
                  edges {
                    node {
                      id
                    }
                  }
                }
                """,
                [
                    {
                        "message": "Fields 'edges' conflict"
                        " because subfields 'node' conflict"
                        " because subfields 'id' conflict"
                        " because 'name' and 'id' are different fields."
                        " Use different aliases on the fields"
                        " to fetch both if this was intentional.",
                        "locations": [
                            (5, 21),
                            (6, 23),
                            (7, 25),
                            (14, 19),
                            (15, 21),
                            (16, 23),
                        ],
                        "path": None,
                    }
                ],
                schema,
            )

        def ignores_unknown_types():
            assert_valid(
                """
                {
                  someBox {
                    ...on UnknownType {
                      scalar
                    }
                    ...on NonNullStringBox2 {
                      scalar
                    }
                  }
                }
                """,
                schema=schema,
            )

        def works_for_field_names_that_are_js_keywords():
            schema_with_keywords = build_schema(
                """
                type Foo {
                  constructor: String
                }

                type Query {
                  foo: Foo
                }
                """
            )

            assert_valid(
                """
                {
                  foo {
                    constructor
                  }
                }
                """,
                schema=schema_with_keywords,
            )

        def works_for_field_names_that_are_python_keywords():
            schema_with_keywords = build_schema(
                """
                type Foo {
                  class: String
                }

                type Query {
                  foo: Foo
                }
                """
            )

            assert_valid(
                """
                {
                  foo {
                    class
                  }
                }
                """,
                schema=schema_with_keywords,
            )

    def does_not_infinite_loop_on_recursive_fragments():
        assert_valid(
            """
            {
              ...fragA
            }

            fragment fragA on Human { name, relatives { name, ...fragA } }
            """
        )

    def does_not_infinite_loop_on_immediately_recursive_fragments():
        assert_valid(
            """
            {
              ...fragA
            }

            fragment fragA on Human { name, ...fragA }
            """
        )

    def does_not_infinite_loop_on_recursive_fragment_with_field_named_after_fragment():
        assert_valid(
            """
            {
              ...fragA
              fragA
            }

            fragment fragA on Query { ...fragA }
            """
        )

    def finds_invalid_cases_even_with_field_named_after_fragment():
        assert_errors(
            """
            {
              fragA
              ...fragA
            }

            fragment fragA on Type {
              fragA: b
            }
            """,
            [
                {
                    "message": "Fields 'fragA' conflict"
                    " because 'fragA' and 'b' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(3, 15), (8, 15)],
                }
            ],
        )

    def does_not_infinite_loop_on_transitively_recursive_fragments():
        assert_valid(
            """
            {
              ...fragA
              fragB
            }

            fragment fragA on Human { name, ...fragB }
            fragment fragB on Human { name, ...fragC }
            fragment fragC on Human { name, ...fragA }
            """
        )

    @pytest.mark.timeout(5)
    def many_repeated_fields_do_not_cause_quadratic_blowup():
        repeated_fields = "name " * 3000
        assert_valid(
            f"""
            fragment manyRepeatedFields on Dog {{
              {repeated_fields}
            }}
            """
        )

    def many_repeated_fields_with_conflict_still_detected():
        repeated_fields = "name " * 100
        doc = parse(
            f"""
            fragment conflictsAmongMany on Dog {{
              {repeated_fields}
              name: nickname
            }}
            """
        )
        errors = validate(test_schema, doc, [OverlappingFieldsCanBeMergedRule])
        assert errors
        assert "'name' and 'nickname' are different fields" in errors[0].message

    @pytest.mark.timeout(5)
    def many_repeated_composite_fields_do_not_cause_quadratic_blowup():
        # Each occurrence of a composite field has its own SelectionSetNode, so
        # deduplication must fingerprint the selection set by content, not identity,
        # otherwise these still trigger quadratic behavior.
        repeated_fields = "mother { name } " * 3000
        assert_valid(
            f"""
            fragment manyRepeatedCompositeFields on Dog {{
              {repeated_fields}
            }}
            """
        )

    @pytest.mark.timeout(5)
    def many_repeated_fields_with_reordered_arguments_do_not_cause_quadratic_blowup():
        # Fields whose arguments differ only in order are equivalent and must
        # deduplicate, so the fingerprint has to be argument-order independent.
        repeated_fields = "isAtLocation(x: 1, y: 2) isAtLocation(y: 2, x: 1) " * 1500
        assert_valid(
            f"""
            fragment reorderedArgs on Dog {{
              {repeated_fields}
            }}
            """
        )

    @pytest.mark.timeout(5)
    def repeated_fields_with_reordered_nested_arguments_do_not_cause_blowup():
        # Reordering arguments inside a nested selection set keeps the fields
        # equivalent, so deduplication must canonicalize recursively rather than rely
        # on the printed selection set (which preserves source argument order).
        repeated_fields = (
            "mother { isAtLocation(x: 1, y: 2) } "
            "mother { isAtLocation(y: 2, x: 1) } "
        ) * 1500
        assert_valid(
            f"""
            fragment reorderedNestedArgs on Dog {{
              {repeated_fields}
            }}
            """
        )

    def many_repeated_composite_fields_with_conflict_still_detected():
        repeated_fields = "mother { name } " * 100
        doc = parse(
            f"""
            fragment conflictsAmongManyComposites on Dog {{
              {repeated_fields}
              mother {{ name: nickname }}
            }}
            """
        )
        errors = validate(test_schema, doc, [OverlappingFieldsCanBeMergedRule])
        assert errors
        assert "'name' and 'nickname' are different fields" in errors[0].message

    def finds_invalid_case_even_with_immediately_recursive_fragment():
        assert_errors(
            """
            fragment sameAliasesWithDifferentFieldTargets on Dog {
              ...sameAliasesWithDifferentFieldTargets
              fido: name
              fido: nickname
            }
            """,
            [
                {
                    "message": "Fields 'fido' conflict"
                    " because 'name' and 'nickname' are different fields."
                    " Use different aliases on the fields"
                    " to fetch both if this was intentional.",
                    "locations": [(4, 15), (5, 15)],
                }
            ],
        )

    def does_not_infinite_loop_on_recursive_fragments_separated_by_fields():
        assert_valid(
            """
            {
              ...fragA
              ...fragB
            }

            fragment fragA on T {
              x {
                ...fragA
                x {
                  ...fragA
                }
              }
            }

            fragment fragB on T {
              x {
                ...fragB
                x {
                  ...fragB
                }
              }
            }
            """
        )

    @pytest.mark.timeout(5)
    def many_fields_with_differing_arguments_are_rejected_as_too_complex():
        # Fields differing only in their arguments genuinely conflict, so they
        # cannot be deduplicated and would otherwise force a quadratic number of
        # comparisons. The comparison budget bounds this by rejecting the query
        # with a single error instead of validating every pair.
        distinct_fields = " ".join(
            f"p: isAtLocation(x: {i})" for i in range(2000)
        )
        doc = parse(
            f"""
            fragment manyDistinctArguments on Dog {{
              {distinct_fields}
            }}
            """
        )
        errors = validate(test_schema, doc, [OverlappingFieldsCanBeMergedRule])
        assert errors
        assert "too complex to validate" in errors[0].message

    @pytest.mark.timeout(5)
    def valid_repeated_fields_across_fragments_are_not_too_complex():
        # Deduplication must also apply when comparing fields "between" two spread
        # fragments, otherwise a valid query repeating a field many times in each
        # fragment forces a quadratic number of comparisons and is wrongly rejected
        # by the comparison budget.
        repeated_fields = "name " * 400
        assert_valid(
            f"""
            {{
              dog {{ ...fragA ...fragB }}
            }}

            fragment fragA on Dog {{ {repeated_fields} }}
            fragment fragB on Dog {{ {repeated_fields} }}
            """
        )

    def modest_differing_arguments_still_report_the_real_conflict():
        # Below the budget the ordinary, specific conflict must still be reported
        # rather than the "too complex" fallback.
        doc = parse(
            """
            fragment fewDistinctArguments on Dog {
              p: isAtLocation(x: 0)
              p: isAtLocation(x: 1)
            }
            """
        )
        errors = validate(test_schema, doc, [OverlappingFieldsCanBeMergedRule])
        assert errors
        assert "they have differing arguments" in errors[0].message
