from graphql.pyutils import identity_func, Undefined


def describe_identity_func():
    def returns_the_first_argument_it_receives():
        assert identity_func() is Undefined
        assert identity_func(Undefined) is Undefined
        assert identity_func(None) is None
        obj = object()
        assert identity_func(obj) is obj

        assert identity_func(Undefined, None) is Undefined
        assert identity_func(None, Undefined) is None

        assert identity_func(None, Undefined, obj) is None
        assert identity_func(Undefined, None, obj) is Undefined
        assert identity_func(obj, None, Undefined) is obj
