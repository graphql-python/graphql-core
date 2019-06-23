from graphql.error import INVALID
from graphql.pyutils import identity_func


def describe_identity_func():
    def returns_the_first_argument_it_receives():
        assert identity_func() is INVALID
        assert identity_func(INVALID) is INVALID
        assert identity_func(None) is None
        obj = object()
        assert identity_func(obj) is obj

        assert identity_func(INVALID, None) is INVALID
        assert identity_func(None, INVALID) is None

        assert identity_func(None, INVALID, obj) is None
        assert identity_func(INVALID, None, obj) is INVALID
        assert identity_func(obj, None, INVALID) is obj
