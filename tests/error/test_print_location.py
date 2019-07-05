from graphql.language import print_source_location, Source, SourceLocation
from graphql.pyutils import dedent


def describe_print_location():
    def prints_single_digit_line_number_with_no_padding():
        result = print_source_location(
            Source("*", "Test", SourceLocation(9, 1)), SourceLocation(1, 1)
        )

        assert result + "\n" == dedent(
            """
            Test:9:1
            9: *
               ^
            """
        )

    def prints_line_numbers_with_correct_padding():
        result = print_source_location(
            Source("*\n", "Test", SourceLocation(9, 1)), SourceLocation(1, 1)
        )

        assert result + "\n" == dedent(
            """
            Test:9:1
             9: *
                ^
            10:\x20
            """
        )
