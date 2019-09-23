from graphql import SourceLocation


def describe_SourceLocation():
    def equals_with_itself():
        assert SourceLocation(1, 2) == SourceLocation(1, 2)
        assert (SourceLocation(1, 2) != SourceLocation(1, 2)) is False

    def equals_with_formatted_form():
        sl = SourceLocation(1, 2)
        assert SourceLocation(1, 2) == sl.formatted
        assert (SourceLocation(1, 2) != sl.formatted) is False
