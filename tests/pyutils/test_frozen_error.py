from graphql.pyutils import FrozenError


def describe_frozen_error():
    def frozen_error_is_type_error():
        assert issubclass(FrozenError, TypeError)
