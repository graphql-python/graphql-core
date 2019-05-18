from graphql.pyutils import ReadOnlyError


def describe_read_only_error():
    def read_only_error_is_type_error():
        assert issubclass(ReadOnlyError, TypeError)
