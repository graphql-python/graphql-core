from pytest import raises  # type: ignore

from graphql.pyutils import FrozenError, FrozenList


def describe_frozen_list():
    def can_read():
        fl = FrozenList([1, 2, 3])
        assert fl == [1, 2, 3]
        assert list(i for i in fl) == fl
        assert fl.copy() == fl
        assert 2 in fl
        assert 4 not in fl
        assert fl + [4, 5] == [1, 2, 3, 4, 5]
        assert [4, 5] + fl == [4, 5, 1, 2, 3]
        assert fl * 2 == [1, 2, 3, 1, 2, 3]
        assert 2 * fl == [1, 2, 3, 1, 2, 3]
        assert fl[1] == 2
        with raises(IndexError):
            fl[3]
        assert fl[1:4] == [2, 3]
        assert fl[::2] == [1, 3]
        assert len(fl) == 3
        assert min(fl) == 1
        assert max(fl) == 3
        assert sum(fl) == 6
        assert fl.index(2) == 1
        with raises(ValueError):
            fl.index(4)
        assert fl.count(2) == 1
        assert fl.count(4) == 0
        assert list(reversed(fl)) == [3, 2, 1]
        assert sorted(fl) == [1, 2, 3]

    def cannot_write():
        fl = FrozenList([1, 2, 3])
        with raises(FrozenError):
            fl[1] = 4
        with raises(FrozenError):
            fl[1:4] = [4]
        with raises(FrozenError):
            del fl[1]
        with raises(FrozenError):
            del fl[1:4]
        with raises(FrozenError):
            fl[1::2] = [4]
        with raises(FrozenError):
            del fl[::2]
        with raises(FrozenError):
            fl.append(4)
        with raises(FrozenError):
            fl.clear()
        with raises(FrozenError):
            fl.extend([4])
        with raises(FrozenError):
            fl += [4]
        with raises(FrozenError):
            fl *= 2
        with raises(FrozenError):
            fl.insert(1, 4)
        with raises(FrozenError):
            fl.pop()
        with raises(FrozenError):
            fl.remove(2)
        with raises(FrozenError):
            fl.sort()
        with raises(FrozenError):
            fl.reverse()
        assert fl == [1, 2, 3]

    def can_add_rol():
        fl1 = FrozenList([1, 2])
        rol2 = FrozenList([3, 4])
        assert fl1 + rol2 == [1, 2, 3, 4]

    def can_add_tuple():
        fl = FrozenList([1, 2])
        assert fl + (3, 4) == [1, 2, 3, 4]
