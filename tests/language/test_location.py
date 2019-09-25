from graphql import SourceLocation


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
