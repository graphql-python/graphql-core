from __future__ import annotations

from typing import cast

from graphql.type import GraphQLNamedType, GraphQLObjectType, GraphQLSchema
from graphql.utilities import build_schema, print_schema
from graphql.utilities.map_schema_config import (
    ConfigMapperMap,
    MappedSchemaContext,
    SchemaElementKind,
    map_schema_config,
)

from ..utils import dedent


def expect_schema_mapping(schema_config, config_mapper_map_fn, expected):
    new_schema_config = map_schema_config(schema_config, config_mapper_map_fn)
    assert print_schema(GraphQLSchema(**new_schema_config)) == dedent(expected)


def describe_map_schema_config():
    def returns_the_original_config_when_no_mappers_are_included():
        sdl = "type Query"
        schema_config = build_schema(sdl).to_kwargs()
        expect_schema_mapping(schema_config, lambda _context: {}, sdl)

    def describe_scalar_mapping():
        def can_map_scalar_types():
            sdl = "scalar SomeScalar"

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.SCALAR: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                scalar SomeScalar
                """,
            )

    def describe_argument_mapping():
        def can_map_arguments():
            sdl = """
                type SomeType {
                  field(arg: String): String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.ARGUMENT: lambda config, *_args: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                type SomeType {
                  field(
                    \"\"\"Some description\"\"\"
                    arg: String
                  ): String
                }
                """,
            )

        def leaves_arguments_as_is_without_an_argument_mapper():
            sdl = """
                type SomeType {
                  field(arg: String): String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(schema_config, lambda _context: {}, sdl)

    def describe_field_mapping():
        def can_map_fields():
            sdl = """
                type SomeType {
                  field: String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.FIELD: lambda config, *_args: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                type SomeType {
                  \"\"\"Some description\"\"\"
                  field: String
                }
                """,
            )

        def can_map_fields_with_non_null_return_type():
            sdl = """
                type SomeType {
                  field: String!
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.FIELD: lambda config, *_args: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                type SomeType {
                  \"\"\"Some description\"\"\"
                  field: String!
                }
                """,
            )

        def can_map_fields_with_list_return_type():
            sdl = """
                type SomeType {
                  field: [String]
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.FIELD: lambda config, *_args: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                type SomeType {
                  \"\"\"Some description\"\"\"
                  field: [String]
                }
                """,
            )

        def maps_fields_after_mapping_arguments():
            sdl = """
                type SomeType {
                  field(arg: String): String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_field(config, _parent_type_name):
                assert config["args"]["arg"].description == "Some argument description"
                return {**config, "description": "Some field description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.ARGUMENT: lambda config, *_args: {
                        **config,
                        "description": "Some argument description",
                    },
                    SchemaElementKind.FIELD: map_field,
                },
                """
                type SomeType {
                  \"\"\"Some field description\"\"\"
                  field(
                    \"\"\"Some argument description\"\"\"
                    arg: String
                  ): String
                }
                """,
            )

    def describe_object_type_mapping():
        def can_map_object_types():
            sdl = "type SomeType"

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.OBJECT: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                type SomeType
                """,
            )

        def maps_object_types_after_mapping_fields():
            sdl = """
                type SomeType {
                  field: String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_object(config):
                assert (
                    config["fields"]()["field"].description == "Some field description"
                )
                return {**config, "description": "Some object description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.FIELD: lambda config, *_args: {
                        **config,
                        "description": "Some field description",
                    },
                    SchemaElementKind.OBJECT: map_object,
                },
                """
                \"\"\"Some object description\"\"\"
                type SomeType {
                  \"\"\"Some field description\"\"\"
                  field: String
                }
                """,
            )

        def maps_object_types_after_mapping_interfaces():
            sdl = """
                interface SomeInterface
                type SomeType implements SomeInterface
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_object(config):
                assert (
                    config["interfaces"]()[0].description
                    == "Some interface description"
                )
                return {**config, "description": "Some object description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.INTERFACE: lambda config: {
                        **config,
                        "description": "Some interface description",
                    },
                    SchemaElementKind.OBJECT: map_object,
                },
                """
                \"\"\"Some interface description\"\"\"
                interface SomeInterface

                \"\"\"Some object description\"\"\"
                type SomeType implements SomeInterface
                """,
            )

    def describe_interface_type_mapping():
        def can_map_interface_types():
            sdl = "interface SomeInterface"

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.INTERFACE: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                interface SomeInterface
                """,
            )

        def maps_interface_types_after_mapping_fields():
            sdl = """
                interface SomeInterface {
                  field: String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_interface(config):
                assert (
                    config["fields"]()["field"].description == "Some field description"
                )
                return {**config, "description": "Some interface description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.FIELD: lambda config, *_args: {
                        **config,
                        "description": "Some field description",
                    },
                    SchemaElementKind.INTERFACE: map_interface,
                },
                """
                \"\"\"Some interface description\"\"\"
                interface SomeInterface {
                  \"\"\"Some field description\"\"\"
                  field: String
                }
                """,
            )

        def maps_interface_types_after_mapping_parent_interfaces():
            sdl = """
                interface SomeParentInterface
                interface SomeInterface implements SomeParentInterface
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_interface(config):
                if config["name"] == "SomeInterface":
                    assert (
                        config["interfaces"]()[0].description
                        == "Some interface description"
                    )
                return {**config, "description": "Some interface description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {SchemaElementKind.INTERFACE: map_interface},
                """
                \"\"\"Some interface description\"\"\"
                interface SomeParentInterface

                \"\"\"Some interface description\"\"\"
                interface SomeInterface implements SomeParentInterface
                """,
            )

    def describe_union_type_mapping():
        def can_map_union_types():
            sdl = "union SomeUnion"

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.UNION: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                union SomeUnion
                """,
            )

        def maps_union_types_after_mapping_types():
            sdl = """
                type SomeType
                union SomeUnion = SomeType
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_union(config):
                assert config["types"]()[0].description == "Some type description"
                return {**config, "description": "Some union description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.OBJECT: lambda config: {
                        **config,
                        "description": "Some type description",
                    },
                    SchemaElementKind.UNION: map_union,
                },
                """
                \"\"\"Some type description\"\"\"
                type SomeType

                \"\"\"Some union description\"\"\"
                union SomeUnion = SomeType
                """,
            )

    def describe_enum_value_mapping():
        def can_map_enum_values():
            sdl = """
                enum SomeEnum {
                  SOME_VALUE
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.ENUM_VALUE: lambda config, *_args: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                enum SomeEnum {
                  \"\"\"Some description\"\"\"
                  SOME_VALUE
                }
                """,
            )

    def describe_enum_type_mapping():
        def can_map_enum_types():
            sdl = "enum SomeEnum"

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.ENUM: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                enum SomeEnum
                """,
            )

        def maps_enum_types_after_mapping_values():
            sdl = """
                enum SomeEnum {
                  SOME_VALUE
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_enum(config):
                assert (
                    config["values"]()["SOME_VALUE"].description
                    == "Some value description"
                )
                return {**config, "description": "Some enum description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.ENUM_VALUE: lambda config, *_args: {
                        **config,
                        "description": "Some value description",
                    },
                    SchemaElementKind.ENUM: map_enum,
                },
                """
                \"\"\"Some enum description\"\"\"
                enum SomeEnum {
                  \"\"\"Some value description\"\"\"
                  SOME_VALUE
                }
                """,
            )

    def describe_input_field_mapping():
        def can_map_input_fields():
            sdl = """
                input SomeInput {
                  field: String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.INPUT_FIELD: lambda config, *_args: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                input SomeInput {
                  \"\"\"Some description\"\"\"
                  field: String
                }
                """,
            )

    def describe_input_object_type_mapping():
        def can_map_input_object_types():
            sdl = "input SomeInput"

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.INPUT_OBJECT: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                input SomeInput
                """,
            )

        def maps_input_object_types_after_mapping_input_fields():
            sdl = """
                input SomeInput {
                  field: String
                }
                """

            schema_config = build_schema(sdl).to_kwargs()

            def map_input_object(config):
                assert (
                    config["fields"]()["field"].description
                    == "Some input field description"
                )
                return {**config, "description": "Some input object description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.INPUT_FIELD: lambda config, *_args: {
                        **config,
                        "description": "Some input field description",
                    },
                    SchemaElementKind.INPUT_OBJECT: map_input_object,
                },
                """
                \"\"\"Some input object description\"\"\"
                input SomeInput {
                  \"\"\"Some input field description\"\"\"
                  field: String
                }
                """,
            )

    def describe_directive_mapping():
        def can_map_directives():
            sdl = "directive @SomeDirective on FIELD"

            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.DIRECTIVE: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                directive @SomeDirective on FIELD
                """,
            )

        def maps_directives_after_mapping_arguments():
            sdl = "directive @SomeDirective(arg: String) on FIELD"

            schema_config = build_schema(sdl).to_kwargs()

            def map_directive(config):
                assert config["args"]["arg"].description == "Some argument description"
                return {**config, "description": "Some directive description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.ARGUMENT: lambda config, *_args: {
                        **config,
                        "description": "Some argument description",
                    },
                    SchemaElementKind.DIRECTIVE: map_directive,
                },
                """
                \"\"\"Some directive description\"\"\"
                directive @SomeDirective(
                  \"\"\"Some argument description\"\"\"
                  arg: String
                ) on FIELD
                """,
            )

    def describe_schema_mapping():
        sdl = """
            type Query

            type Mutation

            type Subscription

            directive @SomeDirective on FIELD

            scalar SomeScalar

            type SomeType {
              field: String
            }

            interface SomeInterface

            union SomeUnion

            enum SomeEnum {
              SOME_VALUE
            }

            input SomeInput {
              field: String
            }
            """

        def can_map_the_schema():
            schema_config = build_schema(sdl).to_kwargs()

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.SCHEMA: lambda config: {
                        **config,
                        "description": "Some description",
                    }
                },
                """
                \"\"\"Some description\"\"\"
                schema {
                  query: Query
                  mutation: Mutation
                  subscription: Subscription
                }

                directive @SomeDirective on FIELD

                type Query

                type Mutation

                type Subscription

                scalar SomeScalar

                type SomeType {
                  field: String
                }

                interface SomeInterface

                union SomeUnion

                enum SomeEnum {
                  SOME_VALUE
                }

                input SomeInput {
                  field: String
                }
                """,
            )

        def maps_the_schema_after_mapping_types_and_directives():
            schema_config = build_schema(sdl).to_kwargs()

            def map_schema(config):
                for directive in config["directives"]:
                    if directive.name == "SomeDirective":
                        assert directive.description == "Some directive description"

                for type_ in config["types"]:
                    if type_.name == "SomeScalar":
                        assert type_.description == "Some scalar description"
                    elif type_.name == "SomeType":
                        assert type_.description == "Some object description"
                    elif type_.name == "SomeInterface":
                        assert type_.description == "Some interface description"
                    elif type_.name == "SomeUnion":
                        assert type_.description == "Some union description"
                    elif type_.name == "SomeEnum":
                        assert type_.description == "Some enum description"
                    elif type_.name == "SomeInput":
                        assert type_.description == "Some input object description"

                return {**config, "description": "Some schema description"}

            expect_schema_mapping(
                schema_config,
                lambda _context: {
                    SchemaElementKind.DIRECTIVE: lambda config: {
                        **config,
                        "description": "Some directive description",
                    },
                    SchemaElementKind.SCALAR: lambda config: {
                        **config,
                        "description": "Some scalar description",
                    },
                    SchemaElementKind.OBJECT: lambda config: {
                        **config,
                        "description": "Some object description",
                    },
                    SchemaElementKind.INTERFACE: lambda config: {
                        **config,
                        "description": "Some interface description",
                    },
                    SchemaElementKind.UNION: lambda config: {
                        **config,
                        "description": "Some union description",
                    },
                    SchemaElementKind.ENUM: lambda config: {
                        **config,
                        "description": "Some enum description",
                    },
                    SchemaElementKind.INPUT_OBJECT: lambda config: {
                        **config,
                        "description": "Some input object description",
                    },
                    SchemaElementKind.SCHEMA: map_schema,
                },
                """
                \"\"\"Some schema description\"\"\"
                schema {
                  query: Query
                  mutation: Mutation
                  subscription: Subscription
                }

                \"\"\"Some directive description\"\"\"
                directive @SomeDirective on FIELD

                \"\"\"Some object description\"\"\"
                type Query

                \"\"\"Some object description\"\"\"
                type Mutation

                \"\"\"Some object description\"\"\"
                type Subscription

                \"\"\"Some scalar description\"\"\"
                scalar SomeScalar

                \"\"\"Some object description\"\"\"
                type SomeType {
                  field: String
                }

                \"\"\"Some interface description\"\"\"
                interface SomeInterface

                \"\"\"Some union description\"\"\"
                union SomeUnion

                \"\"\"Some enum description\"\"\"
                enum SomeEnum {
                  SOME_VALUE
                }

                \"\"\"Some input object description\"\"\"
                input SomeInput {
                  field: String
                }
                """,
            )

    def describe_schema_context():
        def allows_access_to_the_final_mapped_named_type_via_get_named_type():
            sdl = """
                \"\"\"Some description\"\"\"
                type SomeType
                """

            schema = build_schema(sdl)
            schema_config = schema.to_kwargs()
            some_type = cast("GraphQLNamedType", schema.get_type("SomeType"))

            def config_mapper_map_fn(context: MappedSchemaContext) -> ConfigMapperMap:
                def expect_mapped_some_type():
                    mapped_type = context.get_named_type(some_type.name)
                    assert mapped_type is not some_type
                    assert mapped_type.description == some_type.description

                def map_object(config):
                    original_fields = config["fields"]

                    def fields():
                        expect_mapped_some_type()
                        return original_fields()

                    return {**config, "fields": fields}

                def map_schema(config):
                    expect_mapped_some_type()
                    return config

                return {
                    SchemaElementKind.OBJECT: map_object,
                    SchemaElementKind.SCHEMA: map_schema,
                }

            expect_schema_mapping(schema_config, config_mapper_map_fn, sdl)

        def allows_adding_a_named_type_and_retrieving_the_new_list():
            sdl = "type SomeType"

            schema = build_schema(sdl)
            schema_config = schema.to_kwargs()

            def config_mapper_map_fn(context: MappedSchemaContext) -> ConfigMapperMap:
                def map_schema(config):
                    context.set_named_type(GraphQLObjectType("AnotherType", {}))
                    return {**config, "types": context.get_named_types()}

                return {SchemaElementKind.SCHEMA: map_schema}

            expect_schema_mapping(
                schema_config,
                config_mapper_map_fn,
                """
                type SomeType

                type AnotherType
                """,
            )
