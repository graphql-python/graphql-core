import pickle

import pytest
from graphql.pyutils import Undefined, UndefinedType


def describe_Undefined():
    def has_repr():
        assert repr(Undefined) == "Undefined"

    def has_str():
        assert str(Undefined) == "Undefined"

    def is_hashable():
        assert hash(Undefined) == hash(Undefined)
        assert hash(Undefined) != hash(None)
        assert hash(Undefined) != hash(False)
        assert hash(Undefined) != hash(True)

    def as_bool_is_false():
        assert bool(Undefined) is False

    def only_equal_to_itself_and_none():
        # because we want it to behave similarly to JavaScript
        assert Undefined == Undefined  # noqa: PLR0124
        none_object = None
        assert Undefined == none_object
        assert none_object == Undefined
        false_object = False
        assert Undefined != false_object
        assert false_object != Undefined

    def should_not_be_an_exception():
        # because we want to create similar code to JavaScript where
        # undefined return values are different from exceptions
        # (for instance, this is used in the completeValue function)
        assert not isinstance(Undefined, Exception)

    def cannot_be_redefined():
        with pytest.warns(RuntimeWarning, match="Redefinition of 'Undefined'"):
            redefined_undefined = UndefinedType()
        assert redefined_undefined is Undefined

    def can_be_pickled():
        pickled_undefined = pickle.dumps(Undefined)
        unpickled_undefined = pickle.loads(pickled_undefined)
        assert unpickled_undefined is Undefined
