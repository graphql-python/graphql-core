from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.possible_type_extensions import (
    PossibleTypeExtensionsRule,
    extending_unknown_type_message,
    extending_different_type_kind_message,
)

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, PossibleTypeExtensionsRule)

assert_valid = partial(assert_errors, errors=[])


def unknown_type(type_name, suggested_types, line, col):
    return {
        "message": extending_unknown_type_message(type_name, suggested_types),
        "locations": [(line, col)],
    }


def different_type(type_name, kind, l1, c1, l2=None, c2=None):
    message = extending_different_type_kind_message(type_name, kind)
    locations = [(l1, c1)]
    if l2 is not None and c2 is not None:
        locations.append((l2, c2))
    return {"message": message, "locations": locations}


def describe_validate_possible_type_extensions():
    def no_extensions():
        assert_valid(
            """
            scalar FooScalar
            type FooObject
            interface FooInterface
            union FooUnion
            enum FooEnum
            input FooInputObject
            """
        )

    def one_extension_per_type():
        assert_valid(
            """
            scalar FooScalar
            type FooObject
            interface FooInterface
            union FooUnion
            enum FooEnum
            input FooInputObject

            extend scalar FooScalar @dummy
            extend type FooObject @dummy
            extend interface FooInterface @dummy
            extend union FooUnion @dummy
            extend enum FooEnum @dummy
            extend input FooInputObject @dummy
            """
        )

    def many_extensions_per_type():
        assert_valid(
            """
            scalar FooScalar
            type FooObject
            interface FooInterface
            union FooUnion
            enum FooEnum
            input FooInputObject

            extend scalar FooScalar @dummy
            extend type FooObject @dummy
            extend interface FooInterface @dummy
            extend union FooUnion @dummy
            extend enum FooEnum @dummy
            extend input FooInputObject @dummy

            extend scalar FooScalar @dummy
            extend type FooObject @dummy
            extend interface FooInterface @dummy
            extend union FooUnion @dummy
            extend enum FooEnum @dummy
            extend input FooInputObject @dummy
            """
        )

    def extending_unknown_type():
        assert_errors(
            """
            type Known

            extend scalar Unknown @dummy
            extend type Unknown @dummy
            extend interface Unknown @dummy
            extend union Unknown @dummy
            extend enum Unknown @dummy
            extend input Unknown @dummy
            """,
            [
                unknown_type("Unknown", ["Known"], 4, 27),
                unknown_type("Unknown", ["Known"], 5, 25),
                unknown_type("Unknown", ["Known"], 6, 30),
                unknown_type("Unknown", ["Known"], 7, 26),
                unknown_type("Unknown", ["Known"], 8, 25),
                unknown_type("Unknown", ["Known"], 9, 26),
            ],
        )

    def does_not_consider_non_type_definitions():
        assert_errors(
            """
            query Foo { __typename }
            fragment Foo on Query { __typename }
            directive @Foo on SCHEMA

            extend scalar Foo @dummy
            extend type Foo @dummy
            extend interface Foo @dummy
            extend union Foo @dummy
            extend enum Foo @dummy
            extend input Foo @dummy
            """,
            [
                unknown_type("Foo", [], 6, 27),
                unknown_type("Foo", [], 7, 25),
                unknown_type("Foo", [], 8, 30),
                unknown_type("Foo", [], 9, 26),
                unknown_type("Foo", [], 10, 25),
                unknown_type("Foo", [], 11, 26),
            ],
        )

    def extending_with_different_kinds():
        assert_errors(
            """
            scalar FooScalar
            type FooObject
            interface FooInterface
            union FooUnion
            enum FooEnum
            input FooInputObject

            extend type FooScalar @dummy
            extend interface FooObject @dummy
            extend union FooInterface @dummy
            extend enum FooUnion @dummy
            extend input FooEnum @dummy
            extend scalar FooInputObject @dummy
            """,
            [
                different_type("FooScalar", "scalar", 2, 13, 9, 13),
                different_type("FooObject", "object", 3, 13, 10, 13),
                different_type("FooInterface", "interface", 4, 13, 11, 13),
                different_type("FooUnion", "union", 5, 13, 12, 13),
                different_type("FooEnum", "enum", 6, 13, 13, 13),
                different_type("FooInputObject", "input object", 7, 13, 14, 13),
            ],
        )

    def extending_types_within_existing_schema():
        schema = build_schema(
            """
            scalar FooScalar
            type FooObject
            interface FooInterface
            union FooUnion
            enum FooEnum
            input FooInputObject
            """
        )
        sdl = """
            extend scalar FooScalar @dummy
            extend type FooObject @dummy
            extend interface FooInterface @dummy
            extend union FooUnion @dummy
            extend enum FooEnum @dummy
            extend input FooInputObject @dummy
            """

        assert_valid(sdl, schema=schema)

    def extending_unknown_types_within_existing_schema():
        schema = build_schema("type Known")
        sdl = """
            extend scalar Unknown @dummy
            extend type Unknown @dummy
            extend interface Unknown @dummy
            extend union Unknown @dummy
            extend enum Unknown @dummy
            extend input Unknown @dummy
            """

        assert_errors(
            sdl,
            [
                unknown_type("Unknown", ["Known"], 2, 27),
                unknown_type("Unknown", ["Known"], 3, 25),
                unknown_type("Unknown", ["Known"], 4, 30),
                unknown_type("Unknown", ["Known"], 5, 26),
                unknown_type("Unknown", ["Known"], 6, 25),
                unknown_type("Unknown", ["Known"], 7, 26),
            ],
            schema,
        )

    def extending_types_with_different_kinds_within_existing_schema():
        schema = build_schema(
            """
            scalar FooScalar
            type FooObject
            interface FooInterface
            union FooUnion
            enum FooEnum
            input FooInputObject
            """
        )
        sdl = """
            extend type FooScalar @dummy
            extend interface FooObject @dummy
            extend union FooInterface @dummy
            extend enum FooUnion @dummy
            extend input FooEnum @dummy
            extend scalar FooInputObject @dummy
            """

        assert_errors(
            sdl,
            [
                different_type("FooScalar", "scalar", 2, 13),
                different_type("FooObject", "object", 3, 13),
                different_type("FooInterface", "interface", 4, 13),
                different_type("FooUnion", "union", 5, 13),
                different_type("FooEnum", "enum", 6, 13),
                different_type("FooInputObject", "input object", 7, 13),
            ],
            schema,
        )
