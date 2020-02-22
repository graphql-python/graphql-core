from copy import copy, deepcopy

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
            # noinspection PyStatementEffect
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
        with raises(FrozenError):
            fd += {4: 5}
        assert fd == {1: 2, 3: 4}

    def can_hash():
        fd1 = FrozenDict({1: 2, 3: 4})
        fd2 = FrozenDict({1: 2, 3: 4})
        assert fd2 == fd1
        assert fd2 is not fd1
        assert hash(fd2) is not hash(fd1)
        fd3 = FrozenDict({1: 2, 3: 5})
        assert fd3 != fd1
        assert hash(fd3) != hash(fd1)

    def can_copy():
        fd1 = FrozenDict({1: 2, 3: 4})
        fd2 = fd1.copy()
        assert isinstance(fd2, FrozenDict)
        assert fd2 == fd1
        assert hash(fd2) == hash(fd1)
        assert fd2 is not fd1
        fd3 = copy(fd1)
        assert isinstance(fd3, FrozenDict)
        assert fd3 == fd1
        assert hash(fd3) == hash(fd1)
        assert fd3 is not fd1

    def can_deep_copy():
        fd11 = FrozenDict({1: 2, 3: 4})
        fd12 = FrozenDict({2: 1, 4: 3})
        fd1 = FrozenDict({1: fd11, 2: fd12})
        assert fd1[1] is fd11
        assert fd1[2] is fd12
        fd2 = deepcopy(fd1)
        assert isinstance(fd2, FrozenDict)
        assert fd2 == fd1
        assert hash(fd2) == hash(fd1)
        fd21 = fd2[1]
        fd22 = fd2[2]
        assert isinstance(fd21, FrozenDict)
        assert isinstance(fd22, FrozenDict)
        assert fd21 == fd11
        assert fd21 is not fd11
        assert fd22 == fd12
        assert fd22 is not fd12
