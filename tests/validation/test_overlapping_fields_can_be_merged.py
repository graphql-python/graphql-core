from graphql.type import (
    GraphQLField,
    GraphQLID,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.validation import OverlappingFieldsCanBeMergedRule
from graphql.validation.rules.overlapping_fields_can_be_merged import (
    fields_conflict_message
)

from .harness import (
    expect_fails_rule,
    expect_fails_rule_with_schema,
    expect_passes_rule,
    expect_passes_rule_with_schema,
)


def describe_validate_overlapping_fields_can_be_merged():
    def unique_fields():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment uniqueFields on Dog {
              name
              nickname
            }
            """,
        )

    def identical_fields():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment mergeIdenticalFields on Dog {
              name
              name
            }
            """,
        )

    def identical_fields_with_identical_args():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment mergeIdenticalFieldsWithIdenticalArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
              doesKnowCommand(dogCommand: SIT)
            }
            """,
        )

    def identical_fields_with_identical_directives():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment mergeSameFieldsWithSameDirectives on Dog {
              name @include(if: true)
              name @include(if: true)
            }
            """,
        )

    def different_args_with_different_aliases():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment differentArgsWithDifferentAliases on Dog {
              knowsSit: doesKnowCommand(dogCommand: SIT)
              knowsDown: doesKnowCommand(dogCommand: DOWN)
            }
            """,
        )

    def different_directives_with_different_aliases():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment differentDirectivesWithDifferentAliases on Dog {
              nameIfTrue: name @include(if: true)
              nameIfFalse: name @include(if: false)
            }
            """,
        )

    def different_skip_or_include_directives_accepted():
        # Note: Differing skip/include directives don't create an ambiguous
        # return value and are acceptable in conditions where differing runtime
        # values may have the same desired effect of including/skipping a field
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment differentDirectivesWithDifferentAliases on Dog {
              name @include(if: true)
              name @include(if: false)
            }
            """,
        )

    def same_aliases_with_different_field_targets():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment sameAliasesWithDifferentFieldTargets on Dog {
              fido: name
              fido: nickname
            }
            """,
            [
                {
                    "message": fields_conflict_message(
                        "fido", "name and nickname are different fields"
                    ),
                    "locations": [(3, 15), (4, 15)],
                    "path": None,
                }
            ],
        )

    def same_aliases_allowed_on_non_overlapping_fields():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment sameAliasesWithDifferentFieldTargets on Pet {
              ... on Dog {
                name
              }
              ... on Cat {
                name: nickname
              }
            }
            """,
        )

    def alias_masking_direct_field_access():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment aliasMaskingDirectFieldAccess on Dog {
              name: nickname
              name
            }
            """,
            [
                {
                    "message": fields_conflict_message(
                        "name", "nickname and name are different fields"
                    ),
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_args_second_adds_an_argument():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment conflictingArgs on Dog {
              doesKnowCommand
              doesKnowCommand(dogCommand: HEEL)
            }
            """,
            [
                {
                    "message": fields_conflict_message(
                        "doesKnowCommand", "they have differing arguments"
                    ),
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def different_args_second_missing_an_argument():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment conflictingArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
              doesKnowCommand
            }
            """,
            [
                {
                    "message": fields_conflict_message(
                        "doesKnowCommand", "they have differing arguments"
                    ),
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def conflicting_args():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment conflictingArgs on Dog {
              doesKnowCommand(dogCommand: SIT)
              doesKnowCommand(dogCommand: HEEL)
            }
            """,
            [
                {
                    "message": fields_conflict_message(
                        "doesKnowCommand", "they have differing arguments"
                    ),
                    "locations": [(3, 15), (4, 15)],
                }
            ],
        )

    def allows_different_args_where_no_conflict_is_possible():
        # This is valid since no object can be both a "Dog" and a "Cat", thus
        # these fields can never overlap.
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment conflictingArgs on Pet {
              ... on Dog {
                name(surname: true)
              }
              ... on Cat {
                name
              }
            }
            """,
        )

    def encounters_conflict_in_fragments():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "x", "a and b are different fields"
                    ),
                    "locations": [(7, 15), (10, 15)],
                }
            ],
        )

    def reports_each_conflict_once():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "x", "a and b are different fields"
                    ),
                    "locations": [(18, 15), (21, 15)],
                },
                {
                    "message": fields_conflict_message(
                        "x", "c and a are different fields"
                    ),
                    "locations": [(14, 17), (18, 15)],
                },
                {
                    "message": fields_conflict_message(
                        "x", "c and b are different fields"
                    ),
                    "locations": [(14, 17), (21, 15)],
                },
            ],
        )

    def deep_conflict():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "field", [("x", "a and b are different fields")]
                    ),
                    "locations": [(3, 15), (4, 17), (6, 15), (7, 17)],
                }
            ],
        )

    def deep_conflict_with_multiple_issues():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "field",
                        [
                            ("x", "a and b are different fields"),
                            ("y", "c and d are different fields"),
                        ],
                    ),
                    "locations": [(3, 15), (4, 17), (5, 17), (7, 15), (8, 17), (9, 17)],
                    "path": None,
                }
            ],
        )

    def very_deep_conflict():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "field",
                        [("deepField", [("x", "a and b are different fields")])],
                    ),
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
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "deepField", [("x", "a and b are different fields")]
                    ),
                    "locations": [(4, 17), (5, 19), (7, 17), (8, 19)],
                }
            ],
        )

    def reports_deep_conflict_to_nearest_common_ancestor_in_fragments():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "deeperField", [("x", "a and b are different fields")]
                    ),
                    "locations": [(12, 17), (13, 19), (15, 17), (16, 19)],
                }
            ],
        )

    def reports_deep_conflict_in_nested_fragments():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
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
                    "message": fields_conflict_message(
                        "field",
                        [
                            ("x", "a and b are different fields"),
                            ("y", "c and d are different fields"),
                        ],
                    ),
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
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
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
            """,
        )

    def describe_return_types_must_be_unambiguous():

        SomeBox = GraphQLInterfaceType(
            "SomeBox",
            lambda: {
                "deepBox": GraphQLField(SomeBox),
                "unrelatedField": GraphQLField(GraphQLString),
            },
        )

        StringBox = GraphQLObjectType(
            "StringBox",
            lambda: {
                "scalar": GraphQLField(GraphQLString),
                "deepBox": GraphQLField(StringBox),
                "unrelatedField": GraphQLField(GraphQLString),
                "listStringBox": GraphQLField(GraphQLList(StringBox)),
                "stringBox": GraphQLField(StringBox),
                "intBox": GraphQLField(IntBox),
            },
            interfaces=[SomeBox],
        )

        IntBox = GraphQLObjectType(
            "IntBox",
            lambda: {
                "scalar": GraphQLField(GraphQLInt),
                "deepBox": GraphQLField(IntBox),
                "unrelatedField": GraphQLField(GraphQLString),
                "listStringBox": GraphQLField(GraphQLList(StringBox)),
                "stringBox": GraphQLField(StringBox),
                "intBox": GraphQLField(IntBox),
            },
            interfaces=[SomeBox],
        )

        NonNullStringBox1 = GraphQLInterfaceType(
            "NonNullStringBox1", {"scalar": GraphQLField(GraphQLNonNull(GraphQLString))}
        )

        NonNullStringBox1Impl = GraphQLObjectType(
            "NonNullStringBox1Impl",
            {
                "scalar": GraphQLField(GraphQLNonNull(GraphQLString)),
                "deepBox": GraphQLField(StringBox),
                "unrelatedField": GraphQLField(GraphQLString),
            },
            interfaces=[SomeBox, NonNullStringBox1],
        )

        NonNullStringBox2 = GraphQLInterfaceType(
            "NonNullStringBox2", {"scalar": GraphQLField(GraphQLNonNull(GraphQLString))}
        )

        NonNullStringBox2Impl = GraphQLObjectType(
            "NonNullStringBox2Impl",
            {
                "scalar": GraphQLField(GraphQLNonNull(GraphQLString)),
                "unrelatedField": GraphQLField(GraphQLString),
                "deepBox": GraphQLField(StringBox),
            },
            interfaces=[SomeBox, NonNullStringBox2],
        )

        Connection = GraphQLObjectType(
            "Connection",
            {
                "edges": GraphQLField(
                    GraphQLList(
                        GraphQLObjectType(
                            "Edge",
                            {
                                "node": GraphQLField(
                                    GraphQLObjectType(
                                        "Node",
                                        {
                                            "id": GraphQLField(GraphQLID),
                                            "name": GraphQLField(GraphQLString),
                                        },
                                    )
                                )
                            },
                        )
                    )
                )
            },
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "QueryRoot",
                {
                    "someBox": GraphQLField(SomeBox),
                    "connection": GraphQLField(Connection),
                },
            ),
            types=[IntBox, StringBox, NonNullStringBox1Impl, NonNullStringBox2Impl],
        )

        def conflicting_return_types_which_potentially_overlap():
            # This is invalid since an object could potentially be both the
            # Object type IntBox and the interface type NonNullStringBox1.
            # While that condition does not exist in the current schema, the
            # schema could expand in the future to allow this.
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "scalar", "they return conflicting types Int and String!"
                        ),
                        "locations": [(5, 27), (8, 27)],
                    }
                ],
            )

        def compatible_return_shapes_on_different_return_types():
            # In this case `deepBox` returns `SomeBox` in the first usage, and
            # `StringBox` in the second usage. These types are not the same!
            # However this is valid because the return *shapes* are compatible.
            expect_passes_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
            )

        def disallows_differing_return_types_despite_no_overlap():
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "scalar", "they return conflicting types Int and String"
                        ),
                        "locations": [(5, 27), (8, 27)],
                    }
                ],
            )

        def reports_correctly_when_a_non_exclusive_follows_an_exclusive():
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "other",
                            [
                                (
                                    "scalar",
                                    "scalar and unrelatedField are different fields",
                                )
                            ],
                        ),
                        "locations": [(31, 23), (39, 23), (34, 23), (42, 23)],
                        "path": None,
                    }
                ],
            )

        def disallows_differing_return_type_nullability_despite_no_overlap():
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "scalar", "they return conflicting types String! and String"
                        ),
                        "locations": [(5, 27), (8, 27)],
                    }
                ],
            )

        def disallows_differing_return_type_list_despite_no_overlap_1():
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "box",
                            "they return conflicting types"
                            " [StringBox] and StringBox",
                        ),
                        "locations": [(5, 27), (10, 27)],
                    }
                ],
            )

            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "box",
                            "they return conflicting types"
                            " StringBox and [StringBox]",
                        ),
                        "locations": [(5, 27), (10, 27)],
                    }
                ],
            )

        def disallows_differing_subfields():
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "val", "scalar and unrelatedField are different fields"
                        ),
                        "locations": [(6, 29), (7, 29)],
                    }
                ],
            )

        def disallows_differing_deep_return_types_despite_no_overlap():
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "box",
                            [
                                (
                                    "scalar",
                                    "they return conflicting types String and Int",
                                )
                            ],
                        ),
                        "locations": [(5, 27), (6, 29), (10, 27), (11, 29)],
                        "path": None,
                    }
                ],
            )

        def allows_non_conflicting_overlapping_types():
            expect_passes_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
            )

        def same_wrapped_scalar_return_types():
            expect_passes_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
            )

        def allows_inline_typeless_fragments():
            expect_passes_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
                """
                    {
                      a
                      ... {
                        a
                      }
                    }
                    """,
            )

        def compares_deep_types_including_list():
            expect_fails_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
                        "message": fields_conflict_message(
                            "edges",
                            [("node", [("id", "name and id are different fields")])],
                        ),
                        "locations": [
                            (5, 25),
                            (6, 27),
                            (7, 29),
                            (14, 23),
                            (15, 25),
                            (16, 27),
                        ],
                        "path": None,
                    }
                ],
            )

        def ignores_unknown_types():
            expect_passes_rule_with_schema(
                schema,
                OverlappingFieldsCanBeMergedRule,
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
            )

        def error_message_contains_hint_for_alias_conflict():
            # The error template should end with a hint for the user to try
            # using different aliases.
            error = fields_conflict_message("x", "a and b are different fields")
            assert error == (
                "Fields 'x' conflict because a and b are different fields."
                " Use different aliases on the fields to fetch both"
                " if this was intentional."
            )

        def works_for_field_names_that_are_js_keywords():
            FooType = GraphQLObjectType(
                "Foo", {"constructor": GraphQLField(GraphQLString)}
            )

            schema_with_keywords = GraphQLSchema(
                GraphQLObjectType("query", lambda: {"foo": GraphQLField(FooType)})
            )

            expect_passes_rule_with_schema(
                schema_with_keywords,
                OverlappingFieldsCanBeMergedRule,
                """
                    {
                      foo {
                        constructor
                      }
                    }
                    """,
            )

        def works_for_field_names_that_are_python_keywords():
            FooType = GraphQLObjectType("Foo", {"class": GraphQLField(GraphQLString)})

            schema_with_keywords = GraphQLSchema(
                GraphQLObjectType("query", lambda: {"foo": GraphQLField(FooType)})
            )

            expect_passes_rule_with_schema(
                schema_with_keywords,
                OverlappingFieldsCanBeMergedRule,
                """
                    {
                      foo {
                        class
                      }
                    }
                    """,
            )

    def does_not_infinite_loop_on_recursive_fragments():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment fragA on Human { name, relatives { name, ...fragA } }
            """,
        )

    def does_not_infinite_loop_on_immediately_recursive_fragments():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment fragA on Human { name, ...fragA }
            """,
        )

    def does_not_infinite_loop_on_transitively_recursive_fragments():
        expect_passes_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment fragA on Human { name, ...fragB }
            fragment fragB on Human { name, ...fragC }
            fragment fragC on Human { name, ...fragA }
            """,
        )

    def finds_invalid_case_even_with_immediately_recursive_fragment():
        expect_fails_rule(
            OverlappingFieldsCanBeMergedRule,
            """
            fragment sameAliasesWithDifferentFieldTargets on Dog {
              ...sameAliasesWithDifferentFieldTargets
              fido: name
              fido: nickname
            }
            """,
            [
                {
                    "message": fields_conflict_message(
                        "fido", "name and nickname are different fields"
                    ),
                    "locations": [(4, 15), (5, 15)],
                }
            ],
        )
