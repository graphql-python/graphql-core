from functools import partial

from graphql.utilities import build_schema
from graphql.validation import KnownTypeNamesRule
from graphql.validation.rules.known_type_names import unknown_type_message

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, KnownTypeNamesRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(assert_sdl_validation_errors, KnownTypeNamesRule)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def unknown_type(type_name, suggested_types, line, column):
    return {
        "message": unknown_type_message(type_name, suggested_types),
        "locations": [(line, column)],
    }


def describe_validate_known_type_names():
    def known_type_names_are_valid():
        assert_valid(
            """
            query Foo($var: String, $required: [String!]!) {
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
            fragment PetFields on Peettt {
              name
            }
            """,
            [
                unknown_type("JumbledUpLetters", [], 2, 29),
                unknown_type("Badger", [], 5, 31),
                unknown_type("Peettt", ["Pet"], 8, 35),
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
                unknown_type("ID", [], 2, 25),
                unknown_type("Float", [], 2, 37),
                unknown_type("Int", [], 2, 50),
            ],
            schema,
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
                unknown_type("C", ["A", "B"], 5, 40),
                unknown_type("D", ["ID", "A", "B"], 6, 20),
                unknown_type("E", ["A", "B"], 6, 24),
                unknown_type("F", ["A", "B"], 9, 31),
                unknown_type("G", ["A", "B"], 9, 35),
                unknown_type("H", ["A", "B"], 12, 20),
                unknown_type("I", ["ID", "A", "B"], 12, 24),
                unknown_type("J", ["A", "B"], 16, 18),
                unknown_type("K", ["A", "B"], 19, 41),
                unknown_type("L", ["A", "B"], 22, 22),
                unknown_type("M", ["A", "B"], 23, 25),
                unknown_type("N", ["A", "B"], 24, 29),
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
            [unknown_type("Foo", [], 7, 20)],
        )

    def reference_standard_scalars_inside_extension_document():
        schema = build_schema("type Foo")
        sdl = """
            type SomeType {
              string: String
              int: Int
              float: Float
              boolean: Boolean
              id: ID
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
                unknown_type("C", ["A", "B"], 4, 40),
                unknown_type("D", ["ID", "A", "B"], 5, 20),
                unknown_type("E", ["A", "B"], 5, 24),
                unknown_type("F", ["A", "B"], 8, 31),
                unknown_type("G", ["A", "B"], 8, 35),
                unknown_type("H", ["A", "B"], 11, 20),
                unknown_type("I", ["ID", "A", "B"], 11, 24),
                unknown_type("J", ["A", "B"], 15, 18),
                unknown_type("K", ["A", "B"], 18, 41),
                unknown_type("L", ["A", "B"], 21, 22),
                unknown_type("M", ["A", "B"], 22, 25),
                unknown_type("N", ["A", "B"], 23, 29),
            ],
            schema,
        )
