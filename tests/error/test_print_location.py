from graphql.language import print_source_location, Source, SourceLocation

from ..utils import dedent


def describe_print_location():
    def prints_minified_documents():
        minified_source = Source(
            "query SomeMinifiedQueryWithErrorInside("
            "$foo:String!=FIRST_ERROR_HERE$bar:String)"
            "{someField(foo:$foo bar:$bar baz:SECOND_ERROR_HERE)"
            "{fieldA fieldB{fieldC fieldD...on THIRD_ERROR_HERE}}}"
        )

        first_location = print_source_location(
            minified_source,
            SourceLocation(1, minified_source.body.index("FIRST_ERROR_HERE") + 1),
        )
        assert first_location == dedent("""
            GraphQL request:1:53
            1 | query SomeMinifiedQueryWithErrorInside($foo:String!=FIRST_ERROR_HERE$bar:String)
              |                                                     ^
              | {someField(foo:$foo bar:$bar baz:SECOND_ERROR_HERE){fieldA fieldB{fieldC fieldD.
            """)  # noqa: E501

        second_location = print_source_location(
            minified_source,
            SourceLocation(1, minified_source.body.index("SECOND_ERROR_HERE") + 1),
        )
        assert second_location == dedent("""
            GraphQL request:1:114
            1 | query SomeMinifiedQueryWithErrorInside($foo:String!=FIRST_ERROR_HERE$bar:String)
              | {someField(foo:$foo bar:$bar baz:SECOND_ERROR_HERE){fieldA fieldB{fieldC fieldD.
              |                                  ^
              | ..on THIRD_ERROR_HERE}}}
            """)  # noqa: E501

        third_location = print_source_location(
            minified_source,
            SourceLocation(1, minified_source.body.index("THIRD_ERROR_HERE") + 1),
        )
        assert third_location == dedent("""
            GraphQL request:1:166
            1 | query SomeMinifiedQueryWithErrorInside($foo:String!=FIRST_ERROR_HERE$bar:String)
              | {someField(foo:$foo bar:$bar baz:SECOND_ERROR_HERE){fieldA fieldB{fieldC fieldD.
              | ..on THIRD_ERROR_HERE}}}
              |      ^
            """)  # noqa: E501

    def prints_single_digit_line_number_with_no_padding():
        result = print_source_location(
            Source("*", "Test", SourceLocation(9, 1)), SourceLocation(1, 1)
        )

        assert result == dedent("""
            Test:9:1
            9 | *
              | ^
            """)

    def prints_line_numbers_with_correct_padding():
        result = print_source_location(
            Source("*\n", "Test", SourceLocation(9, 1)), SourceLocation(1, 1)
        )

        assert result == dedent("""
            Test:9:1
             9 | *
               | ^
            10 |
            """)

    def prints_locations_from_get_location_on_non_graphql_line_breaks():
        # Characters like VT, FF, NEL or U+2028/U+2029 are not GraphQL line
        # terminators, so Source.get_location() reports line 1 for positions
        # after them. Rendering that location must not fail.
        source = Source("x\vy")
        result = print_source_location(source, source.get_location(3))
        assert result == dedent("""
            GraphQL request:1:4
            1 | x\x0by
              |    ^
            """)
