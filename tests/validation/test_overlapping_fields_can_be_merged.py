from functools import partial

from graphql.utilities import build_schema
from graphql.validation import OverlappingFieldsCanBeMergedRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, OverlappingFieldsCanBeMergedRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_overlapping_fields_can_be_merged():
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
            fragment fragA on Human { name, relatives { name, ...fragA } }
            """
        )

    def does_not_infinite_loop_on_immediately_recursive_fragments():
        assert_valid(
            """
            fragment fragA on Human { name, ...fragA }
            """
        )

    def does_not_infinite_loop_on_transitively_recursive_fragments():
        assert_valid(
            """
            fragment fragA on Human { name, ...fragB }
            fragment fragB on Human { name, ...fragC }
            fragment fragC on Human { name, ...fragA }
            """
        )

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
