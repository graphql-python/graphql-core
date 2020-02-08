from pytest import raises  # type: ignore

from graphql.language import Source


def describe_source():
    def can_be_stringified():
        source = Source("")
        assert str(source) == "<Source name='GraphQL request'>"

        source = Source("", "Custom source name")
        assert str(source) == "<Source name='Custom source name'>"

    def rejects_invalid_location_offset():
        def create_source(location_offset):
            return Source("", "", location_offset)

        with raises(
            ValueError,
            match="line in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((0, 1))
        with raises(
            ValueError,
            match="line in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((-1, 1))

        with raises(
            ValueError,
            match="column in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((1, 0))
        with raises(
            ValueError,
            match="column in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((1, -1))
