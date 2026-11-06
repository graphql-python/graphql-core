from graphql import Source, SourceLocation, get_location
from graphql.language.location import get_locations


def describe_get_location():
    def gets_locations_in_an_empty_source():
        source = Source("")

        assert get_location(source, 0) == (1, 1)

    def gets_locations_in_a_source_without_line_endings():
        source = Source("abc")

        assert get_location(source, 0) == (1, 1)
        assert get_location(source, 2) == (1, 3)
        assert get_location(source, 3) == (1, 4)

    def gets_locations_before_on_and_after_different_line_endings():
        source = Source("a\nb\rc\r\nd")

        assert [
            get_location(source, position) for position in range(len(source.body) + 1)
        ] == [
            (1, 1),
            (1, 2),
            (2, 1),
            (2, 2),
            (3, 1),
            (3, 2),
            (4, 0),
            (4, 1),
            (4, 2),
        ]

    def gets_locations_around_consecutive_and_trailing_line_endings():
        source = Source("\n\r\r\n")

        assert [
            get_location(source, position) for position in range(len(source.body) + 1)
        ] == [
            (1, 1),
            (2, 1),
            (3, 1),
            (4, 0),
            (4, 1),
        ]

    # Positions and columns count code points in Python, where GraphQL.js counts
    # UTF-16 code units. So a supplementary character takes up only one column.
    # https://spec.graphql.org/draft/#sec-Errors.Error-Result-Format
    def counts_code_points():
        source = Source("\U0001f600\u00e9")

        assert get_location(source, 1) == (1, 2)
        assert get_location(source, 2) == (1, 3)

    # GraphQL defines CR, LF, and CRLF as line terminators:
    # https://spec.graphql.org/draft/#sec-Line-Terminators
    def does_not_treat_unicode_line_and_paragraph_separators_as_line_endings():
        source = Source("a\u2028b\u2029c")

        assert get_location(source, 2) == (1, 3)
        assert get_location(source, 4) == (1, 5)

    def gets_locations_relative_to_the_source_body_despite_its_location_offset():
        source = Source("a\nb", "example.graphql", SourceLocation(10, 20))

        assert get_location(source, 0) == (1, 1)
        assert get_location(source, 2) == (2, 1)

    def handles_repeated_calls_with_positions_in_any_order():
        source = Source("a\nb")

        assert get_location(source, 2) == (2, 1)
        assert get_location(source, 1) == (1, 2)
        assert get_location(source, 0) == (1, 1)
        assert get_location(source, 2) == (2, 1)

    def uses_the_current_source_body_on_each_call():
        source = Source("a\nb")

        assert get_location(source, 2) == (2, 1)
        source.body = "a b"
        assert get_location(source, 2) == (1, 3)
        source.body = "\r\nb"
        assert get_location(source, 2) == (2, 1)


def describe_get_locations():
    def handles_an_empty_list_of_positions():
        assert get_locations([]) == []

    def gets_locations_in_an_empty_source():
        source = Source("")

        assert get_locations([(source, 0)]) == [(1, 1)]

    def gets_locations_around_different_line_endings():
        source = Source("a\nb\rc\r\nd")

        assert get_locations(
            [(source, start) for start in range(len(source.body) + 1)]
        ) == [
            (1, 1),
            (1, 2),
            (2, 1),
            (2, 2),
            (3, 1),
            (3, 2),
            (4, 0),
            (4, 1),
            (4, 2),
        ]

    def preserves_input_order_and_duplicate_positions_without_changing_the_input():
        source = Source("a\nb\nc")
        locations = (
            (source, 4),
            (source, 0),
            (source, 2),
            (source, 4),
        )

        assert get_locations(locations) == [
            (3, 1),
            (1, 1),
            (2, 1),
            (3, 1),
        ]
        assert [start for _source, start in locations] == [4, 0, 2, 4]

    def groups_interleaved_sources_by_identity():
        first = Source("a\nb")
        second = Source("a b")

        assert get_locations(
            [
                (first, 2),
                (second, 2),
                (first, 1),
                (second, 0),
            ]
        ) == [
            (2, 1),
            (1, 3),
            (1, 2),
            (1, 1),
        ]

    # In Python, Source has a structural __eq__ and __hash__.
    def does_not_rely_on_the_equality_of_sources():
        class AllEqualSource(Source):
            def __eq__(self, _other: object) -> bool:
                return True

            def __hash__(self) -> int:
                return 0

        first = AllEqualSource("a\nb")
        second = AllEqualSource("a b")
        assert first == second
        assert hash(first) == hash(second)

        assert get_locations([(first, 2), (second, 2)]) == [(2, 1), (1, 3)]

    def uses_the_current_source_body_across_repeated_calls():
        source = Source("a\nb")
        locations = [
            (source, 2),
            (source, 1),
        ]

        assert get_locations(locations) == [(2, 1), (1, 2)]
        source.body = "a b"
        assert get_locations(locations) == [(1, 3), (1, 2)]


def describe_source_location():
    def can_be_formatted():
        location = SourceLocation(1, 2)
        assert location.formatted == {"line": 1, "column": 2}

    def can_compare_with_other_source_location():
        location = SourceLocation(1, 2)
        same_location = SourceLocation(1, 2)
        assert location == same_location
        assert not location != same_location
        different_location = SourceLocation(1, 1)
        assert not location == different_location
        assert location != different_location
        different_location = SourceLocation(2, 2)
        assert not location == different_location
        assert location != different_location

    def can_compare_with_location_tuple():
        location = SourceLocation(1, 2)
        same_location = (1, 2)
        assert location == same_location
        assert not location != same_location
        different_location = (1, 1)
        assert not location == different_location
        assert location != different_location
        different_location = (2, 2)
        assert not location == different_location
        assert location != different_location

    def can_compare_with_formatted_location():
        location = SourceLocation(1, 2)
        same_location = location.formatted
        assert location == same_location
        assert not location != same_location
        different_location = SourceLocation(1, 1).formatted
        assert not location == different_location
        assert location != different_location
        different_location = SourceLocation(2, 2).formatted
        assert not location == different_location
        assert location != different_location
