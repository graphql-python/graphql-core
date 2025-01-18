import pytest

from graphql.pyutils import RefSet

obj1 = ["a", "b", "c"]
obj2 = obj1.copy()
obj3 = obj1.copy()
obj4 = obj1.copy()


def describe_object_set():
    def can_create_an_empty_set():
        s = RefSet[int]()
        assert not s
        assert len(s) == 0
        assert list(s) == []

    def can_create_a_set_with_scalar_values():
        s = RefSet[str](obj1)
        assert s
        assert len(s) == 3
        assert list(s) == ["a", "b", "c"]
        for v in s:
            assert v in s

    def can_create_a_set_with_one_object_as_value():
        s = RefSet[list]([obj1])
        assert s
        assert len(s) == 1
        assert obj1 in s
        assert obj2 not in s

    def can_create_a_set_with_three_objects_as_keys():
        s = RefSet[list]([obj1, obj2, obj3])
        assert s
        assert len(s) == 3
        assert list(s) == [obj1, obj2, obj3]
        for v in s:
            assert v in s
        assert obj4 not in s

    def can_add_a_value_that_is_an_object():
        s = RefSet[list]()
        s.add(obj1)
        assert obj1 in s
        assert list(s) == [obj1]
        assert obj2 not in s
        s.add(obj2)
        assert obj1 in s
        assert obj2 in s
        assert list(s) == [obj1, obj2]
        s.add(obj2)
        assert obj1 in s
        assert obj2 in s
        assert list(s) == [obj1, obj2]
        assert len(s) == 2

    def can_remove_a_value_that_is_an_object():
        s = RefSet[list]([obj1, obj2, obj3])
        s.remove(obj2)
        assert obj2 not in s
        assert list(s) == [obj1, obj3]
        with pytest.raises(KeyError):
            s.remove(obj2)
        assert list(s) == [obj1, obj3]
        assert len(s) == 2

    def can_discard_a_value_that_is_an_object():
        s = RefSet[list]([obj1, obj2, obj3])
        s.discard(obj2)
        assert obj2 not in s
        assert list(s) == [obj1, obj3]
        s.discard(obj2)
        assert list(s) == [obj1, obj3]
        assert len(s) == 2

    def can_update_a_set():
        s = RefSet[list]([obj1, obj2])
        s.update([])
        assert list(s) == [obj1, obj2]
        assert len(s) == 2
        s.update([obj2, obj3])
        assert list(s) == [obj1, obj2, obj3]
        assert obj3 in s
        assert len(s) == 3

    def can_get_the_representation_of_a_ref_set():
        s = RefSet[list]([obj1, obj2])
        assert repr(s) == ("RefSet([['a', 'b', 'c'], ['a', 'b', 'c']])")
