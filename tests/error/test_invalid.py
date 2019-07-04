from graphql.error import INVALID


def describe_invalid():
    def has_repr():
        assert repr(INVALID) == "<INVALID>"

    def has_str():
        assert str(INVALID) == "INVALID"

    def is_hashable():
        assert hash(INVALID) == hash(INVALID)
        assert hash(INVALID) != hash(None)
        assert hash(INVALID) != hash(False)
        assert hash(INVALID) != hash(True)

    def as_bool_is_false():
        assert bool(INVALID) is False

    def only_equal_to_itself():
        assert INVALID == INVALID
        assert not INVALID != INVALID
        none_object = None
        assert INVALID != none_object
        assert not INVALID == none_object
        false_object = False
        assert INVALID != false_object
        assert not INVALID == false_object
