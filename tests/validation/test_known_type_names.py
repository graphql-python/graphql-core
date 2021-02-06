from functools import partial

from graphql.utilities import build_schema
from graphql.validation import KnownTypeNamesRule

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, KnownTypeNamesRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(assert_sdl_validation_errors, KnownTypeNamesRule)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def describe_validate_known_type_names():
    def known_type_names_are_valid():
        assert_valid(
            """
            query Foo(
              $var: String
              $required: [Int!]!
              $introspectionType: __EnumValue
            ) {
              user(id: 4) {
                pets { ... on Pet { name }, ...PetFields, ... { name } }
              }
            }

            fragment PetFields on Pet {
              name
            }
            """
        )

    def unknown_type_names_are_invalid():
        assert_errors(
            """
            query Foo($var: JumbledUpLetters) {
              user(id: 4) {
                name
                pets { ... on Badger { name }, ...PetFields, ... { name } }
              }
            }
            fragment PetFields on Peat {
              name
            }
            """,
            [
                {
                    "message": "Unknown type 'JumbledUpLetters'.",
                    "locations": [(2, 29)],
                },
                {"message": "Unknown type 'Badger'.", "locations": [(5, 31)]},
                {
                    "message": "Unknown type 'Peat'. Did you mean 'Pet' or 'Cat'?",
                    "locations": [(8, 35)],
                },
            ],
        )

    def references_to_standard_scalars_that_are_missing_in_schema():
        schema = build_schema("type Query { foo: String }")
        query = """
            query ($id: ID, $float: Float, $int: Int) {
              __typename
            }
            """
        assert_errors(
            query,
            [
                {"message": "Unknown type 'ID'.", "locations": [(2, 25)]},
                {"message": "Unknown type 'Float'.", "locations": [(2, 37)]},
                {"message": "Unknown type 'Int'.", "locations": [(2, 50)]},
            ],
            schema,
        )

    def describe_within_sdl():
        def use_standard_types():
            assert_sdl_valid(
                """
                type Query {
                  string: String
                  int: Int
                  float: Float
                  boolean: Boolean
                  id: ID
                  introspectionType: __EnumValue
                }
                """
            )

        def reference_types_defined_inside_the_same_document():
            assert_sdl_valid(
                """
                union SomeUnion = SomeObject | AnotherObject

                type SomeObject implements SomeInterface {
                someScalar(arg: SomeInputObject): SomeScalar
                }

                type AnotherObject {
                foo(arg: SomeInputObject): String
                }

                type SomeInterface {
                someScalar(arg: SomeInputObject): SomeScalar
                }

                input SomeInputObject {
                someScalar: SomeScalar
                }

                scalar SomeScalar

                type RootQuery {
                someInterface: SomeInterface
                someUnion: SomeUnion
                someScalar: SomeScalar
                someObject: SomeObject
                }

                schema {
                query: RootQuery
                }
                """
            )

        def unknown_type_references():
            assert_sdl_errors(
                """
                type A
                type B

                type SomeObject implements C {
                  e(d: D): E
                }

                union SomeUnion = F | G

                interface SomeInterface {
                  i(h: H): I
                }

                input SomeInput {
                  j: J
                }

                directive @SomeDirective(k: K) on QUERY

                schema {
                  query: L
                  mutation: M
                  subscription: N
                }
                """,
                [
                    {
                        "message": "Unknown type 'C'. Did you mean 'A' or 'B'?",
                        "locations": [(5, 44)],
                    },
                    {
                        "message": "Unknown type 'D'. Did you mean 'A', 'B', or 'ID'?",
                        "locations": [(6, 24)],
                    },
                    {
                        "message": "Unknown type 'E'. Did you mean 'A' or 'B'?",
                        "locations": [(6, 28)],
                    },
                    {
                        "message": "Unknown type 'F'. Did you mean 'A' or 'B'?",
                        "locations": [(9, 35)],
                    },
                    {
                        "message": "Unknown type 'G'. Did you mean 'A' or 'B'?",
                        "locations": [(9, 39)],
                    },
                    {
                        "message": "Unknown type 'H'. Did you mean 'A' or 'B'?",
                        "locations": [(12, 24)],
                    },
                    {
                        "message": "Unknown type 'I'. Did you mean 'A', 'B', or 'ID'?",
                        "locations": [(12, 28)],
                    },
                    {
                        "message": "Unknown type 'J'. Did you mean 'A' or 'B'?",
                        "locations": [(16, 22)],
                    },
                    {
                        "message": "Unknown type 'K'. Did you mean 'A' or 'B'?",
                        "locations": [(19, 45)],
                    },
                    {
                        "message": "Unknown type 'L'. Did you mean 'A' or 'B'?",
                        "locations": [(22, 26)],
                    },
                    {
                        "message": "Unknown type 'M'. Did you mean 'A' or 'B'?",
                        "locations": [(23, 29)],
                    },
                    {
                        "message": "Unknown type 'N'. Did you mean 'A' or 'B'?",
                        "locations": [(24, 33)],
                    },
                ],
            )

        def does_not_consider_non_type_definitions():
            assert_sdl_errors(
                """
                query Foo { __typename }
                fragment Foo on Query { __typename }
                directive @Foo on QUERY

                type Query {
                  foo: Foo
                }
                """,
                [{"message": "Unknown type 'Foo'.", "locations": [(7, 24)]}],
            )

        def reference_standard_types_inside_extension_document():
            schema = build_schema("type Foo")
            sdl = """
                type SomeType {
                  string: String
                  int: Int
                  float: Float
                  boolean: Boolean
                  id: ID
                  introspectionType: __EnumValue
                }
                """

            assert_sdl_valid(sdl, schema=schema)

        def reference_types_inside_extension_document():
            schema = build_schema("type Foo")
            sdl = """
                type QueryRoot {
                  foo: Foo
                  bar: Bar
                }

                scalar Bar

                schema {
                  query: QueryRoot
                }
                """

            assert_sdl_valid(sdl, schema=schema)

        def unknown_type_references_inside_extension_document():
            schema = build_schema("type A")
            sdl = """
                type B

                type SomeObject implements C {
                  e(d: D): E
                }

                union SomeUnion = F | G

                interface SomeInterface {
                  i(h: H): I
                }

                input SomeInput {
                  j: J
                }

                directive @SomeDirective(k: K) on QUERY

                schema {
                  query: L
                  mutation: M
                  subscription: N
                }
                """

            assert_sdl_errors(
                sdl,
                [
                    {
                        "message": "Unknown type 'C'. Did you mean 'A' or 'B'?",
                        "locations": [(4, 44)],
                    },
                    {
                        "message": "Unknown type 'D'. Did you mean 'A', 'B', or 'ID'?",
                        "locations": [(5, 24)],
                    },
                    {
                        "message": "Unknown type 'E'. Did you mean 'A' or 'B'?",
                        "locations": [(5, 28)],
                    },
                    {
                        "message": "Unknown type 'F'. Did you mean 'A' or 'B'?",
                        "locations": [(8, 35)],
                    },
                    {
                        "message": "Unknown type 'G'. Did you mean 'A' or 'B'?",
                        "locations": [(8, 39)],
                    },
                    {
                        "message": "Unknown type 'H'. Did you mean 'A' or 'B'?",
                        "locations": [(11, 24)],
                    },
                    {
                        "message": "Unknown type 'I'. Did you mean 'A', 'B', or 'ID'?",
                        "locations": [(11, 28)],
                    },
                    {
                        "message": "Unknown type 'J'. Did you mean 'A' or 'B'?",
                        "locations": [(15, 22)],
                    },
                    {
                        "message": "Unknown type 'K'. Did you mean 'A' or 'B'?",
                        "locations": [(18, 45)],
                    },
                    {
                        "message": "Unknown type 'L'. Did you mean 'A' or 'B'?",
                        "locations": [(21, 26)],
                    },
                    {
                        "message": "Unknown type 'M'. Did you mean 'A' or 'B'?",
                        "locations": [(22, 29)],
                    },
                    {
                        "message": "Unknown type 'N'. Did you mean 'A' or 'B'?",
                        "locations": [(23, 33)],
                    },
                ],
                schema,
            )
