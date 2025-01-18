import pytest

from graphql.pyutils import RefMap

obj1 = {"a": 1, "b": 2, "c": 3}
obj2 = obj1.copy()
obj3 = obj1.copy()
obj4 = obj1.copy()


def describe_object_map():
    def can_create_an_empty_map():
        m = RefMap[str, int]()
        assert not m
        assert len(m) == 0
        assert list(m) == []
        assert list(m.keys()) == []
        assert list(m.values()) == []
        assert list(m.items()) == []

    def can_create_a_map_with_scalar_keys_and_values():
        m = RefMap[str, int](list(obj1.items()))
        assert m
        assert len(m) == 3
        assert list(m) == ["a", "b", "c"]
        assert list(m.keys()) == ["a", "b", "c"]
        assert list(m.values()) == [1, 2, 3]
        assert list(m.items()) == [("a", 1), ("b", 2), ("c", 3)]
        for k, v in m.items():
            assert k in m
            assert m[k] == v
            assert m.get(k) == v
            assert v not in m
            with pytest.raises(KeyError):
                m[v]  # type: ignore
            assert m.get(v) is None

    def can_create_a_map_with_one_object_as_key():
        m = RefMap[dict, int]([(obj1, 1)])
        assert m
        assert len(m) == 1
        assert list(m) == [obj1]
        assert list(m.keys()) == [obj1]
        assert list(m.values()) == [1]
        assert list(m.items()) == [(obj1, 1)]
        assert obj1 in m
        assert 1 not in m
        assert obj2 not in m
        assert m[obj1] == 1
        assert m.get(obj1) == 1
        with pytest.raises(KeyError):
            m[1]  # type: ignore
        assert m.get(1) is None
        with pytest.raises(KeyError):
            m[obj2]
        assert m.get(obj2) is None

    def can_create_a_map_with_three_objects_as_keys():
        m = RefMap[dict, int]([(obj1, 1), (obj2, 2), (obj3, 3)])
        assert m
        assert len(m) == 3
        assert list(m) == [obj1, obj2, obj3]
        assert list(m.keys()) == [obj1, obj2, obj3]
        assert list(m.values()) == [1, 2, 3]
        assert list(m.items()) == [(obj1, 1), (obj2, 2), (obj3, 3)]
        for k, v in m.items():
            assert k in m
            assert m[k] == v
            assert m.get(k) == v
            assert v not in m
            with pytest.raises(KeyError):
                m[v]  # type: ignore
            assert m.get(v) is None
        assert obj4 not in m
        with pytest.raises(KeyError):
            m[obj4]
        assert m.get(obj4) is None

    def can_set_a_key_that_is_an_object():
        m = RefMap[dict, int]()
        m[obj1] = 1
        assert m[obj1] == 1
        assert list(m) == [obj1]
        with pytest.raises(KeyError):
            m[obj2]
        m[obj2] = 2
        assert m[obj1] == 1
        assert m[obj2] == 2
        assert list(m) == [obj1, obj2]
        m[obj2] = 3
        assert m[obj1] == 1
        assert m[obj2] == 3
        assert list(m) == [obj1, obj2]
        assert len(m) == 2

    def can_delete_a_key_that_is_an_object():
        m = RefMap[dict, int]([(obj1, 1), (obj2, 2), (obj3, 3)])
        del m[obj2]
        assert obj2 not in m
        assert list(m) == [obj1, obj3]
        with pytest.raises(KeyError):
            del m[obj2]
        assert list(m) == [obj1, obj3]
        assert len(m) == 2

    def can_update_a_map():
        m = RefMap[dict, int]([(obj1, 1), (obj2, 2)])
        m.update([])
        assert list(m.keys()) == [obj1, obj2]
        assert len(m) == 2
        m.update([(obj2, 3), (obj3, 4)])
        assert list(m.keys()) == [obj1, obj2, obj3]
        assert list(m.values()) == [1, 3, 4]
        assert list(m.items()) == [(obj1, 1), (obj2, 3), (obj3, 4)]
        assert obj3 in m
        assert m[obj2] == 3
        assert m[obj3] == 4
        assert len(m) == 3

    def can_get_the_representation_of_a_ref_map():
        m = RefMap[dict, int]([(obj1, 1), (obj2, 2)])
        assert repr(m) == (
            "RefMap([({'a': 1, 'b': 2, 'c': 3}, 1), ({'a': 1, 'b': 2, 'c': 3}, 2)])"
        )
