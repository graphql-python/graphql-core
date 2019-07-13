from pytest import raises  # type: ignore

from graphql.pyutils import FrozenError, FrozenDict


def describe_frozen_list():
    def can_read():
        fd = FrozenDict({1: 2, 3: 4})
        assert fd == {1: 2, 3: 4}
        assert list(i for i in fd) == [1, 3]
        assert fd.copy() == fd
        assert 3 in fd
        assert 2 not in fd
        assert fd[1] == 2
        with raises(KeyError):
            fd[2]
        assert len(fd) == 2
        assert fd.get(1) == 2
        assert fd.get(2, 5) == 5
        assert list(fd.items()) == [(1, 2), (3, 4)]
        assert list(fd.keys()) == [1, 3]
        assert list(fd.values()) == [2, 4]

    def cannot_write():
        fd = FrozenDict({1: 2, 3: 4})
        with raises(FrozenError):
            fd[1] = 2
        with raises(FrozenError):
            fd[4] = 5
        with raises(FrozenError):
            del fd[1]
        with raises(FrozenError):
            del fd[3]
        with raises(FrozenError):
            fd.clear()
        with raises(FrozenError):
            fd.pop(1)
        with raises(FrozenError):
            fd.pop(4, 5)
        with raises(FrozenError):
            fd.popitem()
        with raises(FrozenError):
            fd.setdefault(1, 2)
        with raises(FrozenError):
            fd.setdefault(4, 5)
        with raises(FrozenError):
            fd.update({1: 2})
        with raises(FrozenError):
            fd.update({4: 5})
        assert fd == {1: 2, 3: 4}
