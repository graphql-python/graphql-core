from textwrap import dedent
from typing import List, Optional, Tuple

from pytest import raises

from graphql.error import GraphQLSyntaxError
from graphql.language import (
    ArgumentNode,
    BooleanValueNode,
    DirectiveDefinitionNode,
    DirectiveNode,
    DocumentNode,
    EnumTypeDefinitionNode,
    EnumValueDefinitionNode,
    FieldDefinitionNode,
    InputObjectTypeDefinitionNode,
    InputValueDefinitionNode,
    InterfaceTypeDefinitionNode,
    InterfaceTypeExtensionNode,
    ListTypeNode,
    NameNode,
    NamedTypeNode,
    NonNullTypeNode,
    ObjectTypeDefinitionNode,
    ObjectTypeExtensionNode,
    OperationType,
    OperationTypeDefinitionNode,
    ScalarTypeDefinitionNode,
    SchemaDefinitionNode,
    SchemaExtensionNode,
    StringValueNode,
    TypeNode,
    UnionTypeDefinitionNode,
    ValueNode,
    parse,
)

from ..fixtures import kitchen_sink_sdl  # noqa: F401

Location = Optional[Tuple[int, int]]


def assert_syntax_error(text: str, message: str, location: Location) -> None:
    with raises(GraphQLSyntaxError) as exc_info:
        parse(text)
    error = exc_info.value
    assert error.message == f"Syntax Error: {message}"
    assert error.description == message
    assert error.locations == [location]


def assert_definitions(body: str, loc: Location, num=1):
    doc = parse(body)
    assert isinstance(doc, DocumentNode)
    assert doc.loc == loc
    definitions = doc.definitions
    assert isinstance(definitions, list)
    assert len(definitions) == num
    return definitions[0] if num == 1 else definitions


def type_node(name: str, loc: Location):
    return NamedTypeNode(name=name_node(name, loc), loc=loc)


def name_node(name: str, loc: Location):
    return NameNode(value=name, loc=loc)


def field_node(name: NameNode, type_: TypeNode, loc: Location):
    return field_node_with_args(name, type_, [], loc)


def field_node_with_args(name: NameNode, type_: TypeNode, args: List, loc: Location):
    return FieldDefinitionNode(
        name=name, arguments=args, type=type_, directives=[], loc=loc, description=None
    )


def non_null_type(type_: TypeNode, loc: Location):
    return NonNullTypeNode(type=type_, loc=loc)


def enum_value_node(name: str, loc: Location):
    return EnumValueDefinitionNode(
        name=name_node(name, loc), directives=[], loc=loc, description=None
    )


def input_value_node(
    name: NameNode, type_: TypeNode, default_value: Optional[ValueNode], loc: Location
):
    return InputValueDefinitionNode(
        name=name,
        type=type_,
        default_value=default_value,
        directives=[],
        loc=loc,
        description=None,
    )


def boolean_value_node(value: bool, loc: Location):
    return BooleanValueNode(value=value, loc=loc)


def string_value_node(value: str, block: Optional[bool], loc: Location):
    return StringValueNode(value=value, block=block, loc=loc)


def list_type_node(type_: TypeNode, loc: Location):
    return ListTypeNode(type=type_, loc=loc)


def schema_extension_node(
    directives: List[DirectiveNode],
    operation_types: List[OperationTypeDefinitionNode],
    loc: Location,
):
    return SchemaExtensionNode(
        directives=directives, operation_types=operation_types, loc=loc
    )


def operation_type_definition(operation: OperationType, type_: TypeNode, loc: Location):
    return OperationTypeDefinitionNode(operation=operation, type=type_, loc=loc)


def directive_node(name: NameNode, arguments: List[ArgumentNode], loc: Location):
    return DirectiveNode(name=name, arguments=arguments, loc=loc)


def describe_schema_parser():
    def simple_type():
        body = dedent(
            """
            type Hello {
              world: String
            }
            """
        )
        definition = assert_definitions(body, (0, 32))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.interfaces == []
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("world", (16, 21)), type_node("String", (23, 29)), (16, 29)
            )
        ]
        assert definition.loc == (1, 31)

    def parses_type_with_description_string():
        body = dedent(
            """
            "Description"
            type Hello {
              world: String
            }
            """
        )
        definition = assert_definitions(body, (0, 46))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (20, 25))
        description = definition.description
        assert description == string_value_node("Description", False, (1, 14))

    def parses_type_with_description_multi_line_string():
        body = dedent(
            '''
            """
            Description
            """
            # Even with comments between them
            type Hello {
              world: String
            }'''
        )
        definition = assert_definitions(body, (0, 85))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (60, 65))
        description = definition.description
        assert description == string_value_node("Description", True, (1, 20))

    def parses_schema_with_description_string():
        body = dedent(
            """
            "Description"
            schema {
              query: Foo
            }
            """
        )
        definition = assert_definitions(body, (0, 39))
        assert isinstance(definition, SchemaDefinitionNode)
        description = definition.description
        assert description == string_value_node("Description", False, (1, 14))

    def description_followed_by_something_other_than_type_system_definition_throws():
        assert_syntax_error('"Description" 1', "Unexpected Int '1'.", (1, 15))

    def simple_extension():
        body = dedent(
            """
            extend type Hello {
              world: String
            }
            """
        )
        extension = assert_definitions(body, (0, 39))
        assert isinstance(extension, ObjectTypeExtensionNode)
        assert extension.name == name_node("Hello", (13, 18))
        assert extension.interfaces == []
        assert extension.directives == []
        assert extension.fields == [
            field_node(
                name_node("world", (23, 28)), type_node("String", (30, 36)), (23, 36)
            )
        ]
        assert extension.loc == (1, 38)

    def object_extension_without_fields():
        body = "extend type Hello implements Greeting"
        extension = assert_definitions(body, (0, 37))
        assert isinstance(extension, ObjectTypeExtensionNode)
        assert extension.name == name_node("Hello", (12, 17))
        assert extension.interfaces == [type_node("Greeting", (29, 37))]
        assert extension.directives == []
        assert extension.fields == []
        assert extension.loc == (0, 37)

    def interface_extension_without_fields():
        body = "extend interface Hello implements Greeting"
        extension = assert_definitions(body, (0, 42))
        assert isinstance(extension, InterfaceTypeExtensionNode)
        assert extension.name == name_node("Hello", (17, 22))
        assert extension.interfaces == [type_node("Greeting", (34, 42))]
        assert extension.directives == []
        assert extension.fields == []
        assert extension.loc == (0, 42)

    def object_extension_without_fields_followed_by_extension():
        body = (
            "\n      extend type Hello implements Greeting\n\n"
            "      extend type Hello implements SecondGreeting\n    "
        )
        extensions = assert_definitions(body, (0, 100), 2)
        extension = extensions[0]
        assert isinstance(extension, ObjectTypeExtensionNode)
        assert extension.name == name_node("Hello", (19, 24))
        assert extension.interfaces == [type_node("Greeting", (36, 44))]
        assert extension.directives == []
        assert extension.fields == []
        assert extension.loc == (7, 44)
        extension = extensions[1]
        assert isinstance(extension, ObjectTypeExtensionNode)
        assert extension.name == name_node("Hello", (64, 69))
        assert extension.interfaces == [type_node("SecondGreeting", (81, 95))]
        assert extension.directives == []
        assert extension.fields == []
        assert extension.loc == (52, 95)

    def extension_without_anything_throws():
        assert_syntax_error("extend scalar Hello", "Unexpected <EOF>.", (1, 20))
        assert_syntax_error("extend type Hello", "Unexpected <EOF>.", (1, 18))
        assert_syntax_error("extend interface Hello", "Unexpected <EOF>.", (1, 23))
        assert_syntax_error("extend union Hello", "Unexpected <EOF>.", (1, 19))
        assert_syntax_error("extend enum Hello", "Unexpected <EOF>.", (1, 18))
        assert_syntax_error("extend input Hello", "Unexpected <EOF>.", (1, 19))

    def interface_extension_without_fields_followed_by_extension():
        body = (
            "\n      extend interface Hello implements Greeting\n\n"
            "      extend interface Hello implements SecondGreeting\n    "
        )
        extensions = assert_definitions(body, (0, 110), 2)
        extension = extensions[0]
        assert isinstance(extension, InterfaceTypeExtensionNode)
        assert extension.name == name_node("Hello", (24, 29))
        assert extension.interfaces == [type_node("Greeting", (41, 49))]
        assert extension.directives == []
        assert extension.fields == []
        assert extension.loc == (7, 49)
        extension = extensions[1]
        assert isinstance(extension, InterfaceTypeExtensionNode)
        assert extension.name == name_node("Hello", (74, 79))
        assert extension.interfaces == [type_node("SecondGreeting", (91, 105))]
        assert extension.directives == []
        assert extension.fields == []
        assert extension.loc == (57, 105)

    def object_extension_do_not_include_descriptions():
        assert_syntax_error(
            """
            "Description"
            extend type Hello {
              world: String
            }""",
            "Unexpected description,"
            " descriptions are supported only on type definitions.",
            (2, 13),
        )
        assert_syntax_error(
            """
            extend "Description" type Hello {
              world: String
            }""",
            "Unexpected String 'Description'.",
            (2, 20),
        )

    def interface_extension_do_not_include_descriptions():
        assert_syntax_error(
            """
            "Description"
            extend interface Hello {
              world: String
            }""",
            "Unexpected description,"
            " descriptions are supported only on type definitions.",
            (2, 13),
        )
        assert_syntax_error(
            """
            extend "Description" interface Hello {
              world: String
            }""",
            "Unexpected String 'Description'.",
            (2, 20),
        )

    def schema_extension():
        body = """
            extend schema {
              mutation: Mutation
            }"""
        doc = parse(body)
        assert isinstance(doc, DocumentNode)
        assert doc.loc == (0, 75)
        assert doc.definitions == [
            schema_extension_node(
                [],
                [
                    operation_type_definition(
                        OperationType.MUTATION,
                        type_node("Mutation", (53, 61)),
                        (43, 61),
                    )
                ],
                (13, 75),
            )
        ]

    def schema_extension_with_only_directives():
        body = "extend schema @directive"
        doc = parse(body)
        assert isinstance(doc, DocumentNode)
        assert doc.loc == (0, 24)
        assert doc.definitions == [
            schema_extension_node(
                [directive_node(name_node("directive", (15, 24)), [], (14, 24))],
                [],
                (0, 24),
            )
        ]

    def schema_extension_without_anything_throws():
        assert_syntax_error("extend schema", "Unexpected <EOF>.", (1, 14))

    def schema_extension_with_invalid_operation_type_throws():
        assert_syntax_error(
            "extend schema { unknown: SomeType }", "Unexpected Name 'unknown'.", (1, 17)
        )

    def simple_non_null_type():
        body = dedent(
            """
            type Hello {
              world: String!
            }
            """
        )
        definition = assert_definitions(body, (0, 33))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.interfaces == []
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("world", (16, 21)),
                non_null_type(type_node("String", (23, 29)), (23, 30)),
                (16, 30),
            )
        ]
        assert definition.loc == (1, 32)

    def simple_interface_inheriting_interface():
        body = "interface Hello implements World { field: String }"
        definition = assert_definitions(body, (0, 50))
        assert isinstance(definition, InterfaceTypeDefinitionNode)
        assert definition.name == name_node("Hello", (10, 15))
        assert definition.description is None
        assert definition.interfaces == [type_node("World", (27, 32))]
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("field", (35, 40)), type_node("String", (42, 48)), (35, 48)
            )
        ]
        assert definition.loc == (0, 50)

    def simple_type_inheriting_interface():
        body = "type Hello implements World { field: String }"
        definition = assert_definitions(body, (0, 45))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (5, 10))
        assert definition.description is None
        assert definition.interfaces == [type_node("World", (22, 27))]
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("field", (30, 35)), type_node("String", (37, 43)), (30, 43)
            )
        ]
        assert definition.loc == (0, 45)

    def simple_type_inheriting_multiple_interfaces():
        body = "type Hello implements Wo & rld { field: String }"
        definition = assert_definitions(body, (0, 48))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (5, 10))
        assert definition.description is None
        assert definition.interfaces == [
            type_node("Wo", (22, 24)),
            type_node("rld", (27, 30)),
        ]
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("field", (33, 38)), type_node("String", (40, 46)), (33, 46)
            )
        ]
        assert definition.loc == (0, 48)

    def simple_interface_inheriting_multiple_interfaces():
        body = "interface Hello implements Wo & rld { field: String }"
        definition = assert_definitions(body, (0, 53))
        assert isinstance(definition, InterfaceTypeDefinitionNode)
        assert definition.name == name_node("Hello", (10, 15))
        assert definition.description is None
        assert definition.interfaces == [
            type_node("Wo", (27, 29)),
            type_node("rld", (32, 35)),
        ]
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("field", (38, 43)), type_node("String", (45, 51)), (38, 51)
            )
        ]
        assert definition.loc == (0, 53)

    def simple_type_inheriting_multiple_interfaces_with_leading_ampersand():
        body = "type Hello implements & Wo & rld { field: String }"
        definition = assert_definitions(body, (0, 50))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (5, 10))
        assert definition.description is None
        assert definition.interfaces == [
            type_node("Wo", (24, 26)),
            type_node("rld", (29, 32)),
        ]
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("field", (35, 40)), type_node("String", (42, 48)), (35, 48)
            )
        ]
        assert definition.loc == (0, 50)

    def simple_interface_inheriting_multiple_interfaces_with_leading_ampersand():
        body = "interface Hello implements & Wo & rld { field: String }"
        definition = assert_definitions(body, (0, 55))
        assert isinstance(definition, InterfaceTypeDefinitionNode)
        assert definition.name == name_node("Hello", (10, 15))
        assert definition.description is None
        assert definition.interfaces == [
            type_node("Wo", (29, 31)),
            type_node("rld", (34, 37)),
        ]
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("field", (40, 45)), type_node("String", (47, 53)), (40, 53)
            )
        ]
        assert definition.loc == (0, 55)

    def single_value_enum():
        body = "enum Hello { WORLD }"
        definition = assert_definitions(body, (0, 20))
        assert isinstance(definition, EnumTypeDefinitionNode)
        assert definition.name == name_node("Hello", (5, 10))
        assert definition.description is None
        assert definition.directives == []
        assert definition.values == [enum_value_node("WORLD", (13, 18))]
        assert definition.loc == (0, 20)

    def double_value_enum():
        body = "enum Hello { WO, RLD }"
        definition = assert_definitions(body, (0, 22))
        assert isinstance(definition, EnumTypeDefinitionNode)
        assert definition.name == name_node("Hello", (5, 10))
        assert definition.description is None
        assert definition.directives == []
        assert definition.values == [
            enum_value_node("WO", (13, 15)),
            enum_value_node("RLD", (17, 20)),
        ]
        assert definition.loc == (0, 22)

    def simple_interface():
        body = dedent(
            """
            interface Hello {
              world: String
            }
            """
        )
        definition = assert_definitions(body, (0, 37))
        assert isinstance(definition, InterfaceTypeDefinitionNode)
        assert definition.name == name_node("Hello", (11, 16))
        assert definition.description is None
        assert definition.interfaces == []
        assert definition.directives == []
        assert definition.fields == [
            field_node(
                name_node("world", (21, 26)), type_node("String", (28, 34)), (21, 34)
            )
        ]
        assert definition.loc == (1, 36)

    def simple_field_with_arg():
        body = dedent(
            """
            type Hello {
              world(flag: Boolean): String
            }
            """
        )
        definition = assert_definitions(body, (0, 47))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.interfaces == []
        assert definition.directives == []
        assert definition.fields == [
            field_node_with_args(
                name_node("world", (16, 21)),
                type_node("String", (38, 44)),
                [
                    input_value_node(
                        name_node("flag", (22, 26)),
                        type_node("Boolean", (28, 35)),
                        None,
                        (22, 35),
                    )
                ],
                (16, 44),
            )
        ]
        assert definition.loc == (1, 46)

    def simple_field_with_arg_with_default_value():
        body = dedent(
            """
            type Hello {
              world(flag: Boolean = true): String
            }
            """
        )
        definition = assert_definitions(body, (0, 54))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.interfaces == []
        assert definition.directives == []
        assert definition.fields == [
            field_node_with_args(
                name_node("world", (16, 21)),
                type_node("String", (45, 51)),
                [
                    input_value_node(
                        name_node("flag", (22, 26)),
                        type_node("Boolean", (28, 35)),
                        boolean_value_node(True, (38, 42)),
                        (22, 42),
                    )
                ],
                (16, 51),
            )
        ]
        assert definition.loc == (1, 53)

    def simple_field_with_list_arg():
        body = dedent(
            """
            type Hello {
              world(things: [String]): String
            }
            """
        )
        definition = assert_definitions(body, (0, 50))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.interfaces == []
        assert definition.directives == []
        assert definition.fields == [
            field_node_with_args(
                name_node("world", (16, 21)),
                type_node("String", (41, 47)),
                [
                    input_value_node(
                        name_node("things", (22, 28)),
                        list_type_node(type_node("String", (31, 37)), (30, 38)),
                        None,
                        (22, 38),
                    )
                ],
                (16, 47),
            )
        ]
        assert definition.loc == (1, 49)

    def simple_field_with_two_args():
        body = dedent(
            """
          type Hello {
            world(argOne: Boolean, argTwo: Int): String
          }
          """
        )
        definition = assert_definitions(body, (0, 62))
        assert isinstance(definition, ObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.interfaces == []
        assert definition.directives == []
        assert definition.fields == [
            field_node_with_args(
                name_node("world", (16, 21)),
                type_node("String", (53, 59)),
                [
                    input_value_node(
                        name_node("argOne", (22, 28)),
                        type_node("Boolean", (30, 37)),
                        None,
                        (22, 37),
                    ),
                    input_value_node(
                        name_node("argTwo", (39, 45)),
                        type_node("Int", (47, 50)),
                        None,
                        (39, 50),
                    ),
                ],
                (16, 59),
            )
        ]
        assert definition.loc == (1, 61)

    def simple_union():
        body = "union Hello = World"
        definition = assert_definitions(body, (0, 19))
        assert isinstance(definition, UnionTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.directives == []
        assert definition.types == [type_node("World", (14, 19))]
        assert definition.loc == (0, 19)

    def union_with_two_types():
        body = "union Hello = Wo | Rld"
        definition = assert_definitions(body, (0, 22))
        assert isinstance(definition, UnionTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.description is None
        assert definition.directives == []
        assert definition.types == [
            type_node("Wo", (14, 16)),
            type_node("Rld", (19, 22)),
        ]
        assert definition.loc == (0, 22)

    def union_with_two_types_and_leading_pipe():
        body = "union Hello = | Wo | Rld"
        definition = assert_definitions(body, (0, 24))
        assert isinstance(definition, UnionTypeDefinitionNode)
        assert definition.name == name_node("Hello", (6, 11))
        assert definition.directives == []
        assert definition.types == [
            type_node("Wo", (16, 18)),
            type_node("Rld", (21, 24)),
        ]
        assert definition.loc == (0, 24)

    def union_fails_with_no_types():
        assert_syntax_error("union Hello = |", "Expected Name, found <EOF>.", (1, 16))

    def union_fails_with_leading_double_pipe():
        assert_syntax_error(
            "union Hello = || Wo | Rld", "Expected Name, found '|'.", (1, 16)
        )

    def union_fails_with_double_pipe():
        assert_syntax_error(
            "union Hello = Wo || Rld", "Expected Name, found '|'.", (1, 19)
        )

    def union_fails_with_trailing_pipe():
        assert_syntax_error(
            "union Hello = | Wo | Rld |", "Expected Name, found <EOF>.", (1, 27)
        )

    def scalar():
        body = "scalar Hello"
        definition = assert_definitions(body, (0, 12))
        assert isinstance(definition, ScalarTypeDefinitionNode)
        assert definition.name == name_node("Hello", (7, 12))
        assert definition.description is None
        assert definition.directives == []
        assert definition.loc == (0, 12)

    def simple_input_object():
        body = "\ninput Hello {\n  world: String\n}"
        definition = assert_definitions(body, (0, 32))
        assert isinstance(definition, InputObjectTypeDefinitionNode)
        assert definition.name == name_node("Hello", (7, 12))
        assert definition.description is None
        assert definition.directives == []
        assert definition.fields == [
            input_value_node(
                name_node("world", (17, 22)),
                type_node("String", (24, 30)),
                None,
                (17, 30),
            )
        ]
        assert definition.loc == (1, 32)

    def simple_input_object_with_args_should_fail():
        assert_syntax_error(
            "\ninput Hello {\n  world(foo : Int): String\n}",
            "Expected ':', found '('.",
            (3, 8),
        )

    def directive_definition():
        body = "directive @foo on OBJECT | INTERFACE"
        definition = assert_definitions(body, (0, 36))
        assert isinstance(definition, DirectiveDefinitionNode)
        assert definition.name == name_node("foo", (11, 14))
        assert definition.description is None
        assert definition.arguments == []
        assert definition.repeatable is False
        assert definition.locations == [
            name_node("OBJECT", (18, 24)),
            name_node("INTERFACE", (27, 36)),
        ]

    def repeatable_directive_definition():
        body = "directive @foo repeatable on OBJECT | INTERFACE"
        definition = assert_definitions(body, (0, 47))
        assert isinstance(definition, DirectiveDefinitionNode)
        assert definition.name == name_node("foo", (11, 14))
        assert definition.description is None
        assert definition.arguments == []
        assert definition.repeatable is True
        assert definition.locations == [
            name_node("OBJECT", (29, 35)),
            name_node("INTERFACE", (38, 47)),
        ]

    def directive_with_incorrect_locations():
        assert_syntax_error(
            "\ndirective @foo on FIELD | INCORRECT_LOCATION",
            "Unexpected Name 'INCORRECT_LOCATION'.",
            (2, 27),
        )

    def parses_kitchen_sink_schema(kitchen_sink_sdl):  # noqa: F811
        assert parse(kitchen_sink_sdl)
