from pytest import raises

from graphql.pyutils import ReadOnlyError, ReadOnlyDict


def describe_read_only_list():
    def can_read():
        rod = ReadOnlyDict({1: 2, 3: 4})
        assert rod == {1: 2, 3: 4}
        assert list(i for i in rod) == [1, 3]
        assert rod.copy() == rod
        assert 3 in rod
        assert 2 not in rod
        assert rod[1] == 2
        with raises(KeyError):
            rod[2]
        assert len(rod) == 2
        assert rod.get(1) == 2
        assert rod.get(2, 5) == 5
        assert list(rod.items()) == [(1, 2), (3, 4)]
        assert list(rod.keys()) == [1, 3]
        assert list(rod.values()) == [2, 4]

    def cannot_write():
        rod = ReadOnlyDict({1: 2, 3: 4})
        with raises(ReadOnlyError):
            rod[1] = 2
        with raises(ReadOnlyError):
            rod[4] = 5
        with raises(ReadOnlyError):
            del rod[1]
        with raises(ReadOnlyError):
            del rod[3]
        with raises(ReadOnlyError):
            rod.clear()
        with raises(ReadOnlyError):
            rod.pop(1)
        with raises(ReadOnlyError):
            rod.pop(4, 5)
        with raises(ReadOnlyError):
            rod.popitem()
        with raises(ReadOnlyError):
            rod.setdefault(1, 2)
        with raises(ReadOnlyError):
            rod.setdefault(4, 5)
        with raises(ReadOnlyError):
            rod.update({1: 2})
        with raises(ReadOnlyError):
            rod.update({4: 5})
        assert rod == {1: 2, 3: 4}
