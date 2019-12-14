from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.possible_type_extensions import PossibleTypeExtensionsRule

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, PossibleTypeExtensionsRule)

assert_valid = partial(assert_errors, errors=[])


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
        message = (
            "Cannot extend type 'Unknown' because it is not defined."
            " Did you mean 'Known'?"
        )

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
                {"message": message, "locations": [(4, 27)]},
                {"message": message, "locations": [(5, 25)]},
                {"message": message, "locations": [(6, 30)]},
                {"message": message, "locations": [(7, 26)]},
                {"message": message, "locations": [(8, 25)]},
                {"message": message, "locations": [(9, 26)]},
            ],
        )

    def does_not_consider_non_type_definitions():
        message = "Cannot extend type 'Foo' because it is not defined."

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
                {"message": message, "locations": [(6, 27)]},
                {"message": message, "locations": [(7, 25)]},
                {"message": message, "locations": [(8, 30)]},
                {"message": message, "locations": [(9, 26)]},
                {"message": message, "locations": [(10, 25)]},
                {"message": message, "locations": [(11, 26)]},
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
                {
                    "message": "Cannot extend non-object type 'FooScalar'.",
                    "locations": [(2, 13), (9, 13)],
                },
                {
                    "message": "Cannot extend non-interface type 'FooObject'.",
                    "locations": [(3, 13), (10, 13)],
                },
                {
                    "message": "Cannot extend non-union type 'FooInterface'.",
                    "locations": [(4, 13), (11, 13)],
                },
                {
                    "message": "Cannot extend non-enum type 'FooUnion'.",
                    "locations": [(5, 13), (12, 13)],
                },
                {
                    "message": "Cannot extend non-input object type 'FooEnum'.",
                    "locations": [(6, 13), (13, 13)],
                },
                {
                    "message": "Cannot extend non-scalar type 'FooInputObject'.",
                    "locations": [(7, 13), (14, 13)],
                },
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

        message = (
            "Cannot extend type 'Unknown' because it is not defined."
            " Did you mean 'Known'?"
        )
        assert_errors(
            sdl,
            [
                {"message": message, "locations": [(2, 27)]},
                {"message": message, "locations": [(3, 25)]},
                {"message": message, "locations": [(4, 30)]},
                {"message": message, "locations": [(5, 26)]},
                {"message": message, "locations": [(6, 25)]},
                {"message": message, "locations": [(7, 26)]},
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
                {
                    "message": "Cannot extend non-object type 'FooScalar'.",
                    "locations": [(2, 13)],
                },
                {
                    "message": "Cannot extend non-interface type 'FooObject'.",
                    "locations": [(3, 13)],
                },
                {
                    "message": "Cannot extend non-union type 'FooInterface'.",
                    "locations": [(4, 13)],
                },
                {
                    "message": "Cannot extend non-enum type 'FooUnion'.",
                    "locations": [(5, 13)],
                },
                {
                    "message": "Cannot extend non-input object type 'FooEnum'.",
                    "locations": [(6, 13)],
                },
                {
                    "message": "Cannot extend non-scalar type 'FooInputObject'.",
                    "locations": [(7, 13)],
                },
            ],
            schema,
        )
