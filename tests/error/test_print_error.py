from typing import cast

from graphql.error import GraphQLError, print_error
from graphql.language import parse, ObjectTypeDefinitionNode, Source, SourceLocation
from graphql.pyutils import dedent


def describe_print_error():

    # noinspection PyArgumentEqualDefault
    def prints_line_numbers_with_correct_padding():
        single_digit = GraphQLError(
            "Single digit line number with no padding",
            None,
            Source("*", "Test", SourceLocation(9, 1)),
            [0],
        )
        assert print_error(single_digit) == dedent(
            """
            Single digit line number with no padding

            Test (9:1)
            9: *
               ^
            """
        )

        double_digit = GraphQLError(
            "Left padded first line number",
            None,
            Source("*\n", "Test", SourceLocation(9, 1)),
            [0],
        )

        assert print_error(double_digit) == dedent(
            """
            Left padded first line number

            Test (9:1)
             9: *
                ^
            10:\x20
            """
        )

    def prints_an_error_with_nodes_from_different_sources():
        source_a = parse(
            Source(
                dedent(
                    """
            type Foo {
              field: String
            }
        """
                ),
                "SourceA",
            )
        )
        field_type_a = (
            cast(ObjectTypeDefinitionNode, source_a.definitions[0]).fields[0].type
        )
        source_b = parse(
            Source(
                dedent(
                    """
            type Foo {
              field: Int
            }
        """
                ),
                "SourceB",
            )
        )
        field_type_b = (
            cast(ObjectTypeDefinitionNode, source_b.definitions[0]).fields[0].type
        )
        error = GraphQLError(
            "Example error with two nodes", [field_type_a, field_type_b]
        )
        printed_error = print_error(error)
        assert printed_error == dedent(
            """
            Example error with two nodes

            SourceA (2:10)
            1: type Foo {
            2:   field: String
                        ^
            3: }

            SourceB (2:10)
            1: type Foo {
            2:   field: Int
                        ^
            3: }
            """
        )
        assert str(error) == printed_error
