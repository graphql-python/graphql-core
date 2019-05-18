from pytest import raises

from graphql.pyutils import ReadOnlyError, ReadOnlyList


def describe_read_only_list():
    def can_read():
        rol = ReadOnlyList([1, 2, 3])
        assert rol == [1, 2, 3]
        assert list(i for i in rol) == rol
        assert rol.copy() == rol
        assert 2 in rol
        assert 4 not in rol
        assert rol + [4, 5] == [1, 2, 3, 4, 5]
        assert [4, 5] + rol == [4, 5, 1, 2, 3]
        assert rol * 2 == [1, 2, 3, 1, 2, 3]
        assert 2 * rol == [1, 2, 3, 1, 2, 3]
        assert rol[1] == 2
        with raises(IndexError):
            rol[3]
        assert rol[1:4] == [2, 3]
        assert rol[::2] == [1, 3]
        assert len(rol) == 3
        assert min(rol) == 1
        assert max(rol) == 3
        assert sum(rol) == 6
        assert rol.index(2) == 1
        with raises(ValueError):
            rol.index(4)
        assert rol.count(2) == 1
        assert rol.count(4) == 0
        assert list(reversed(rol)) == [3, 2, 1]
        assert sorted(rol) == [1, 2, 3]

    def cannot_write():
        rol = ReadOnlyList([1, 2, 3])
        with raises(ReadOnlyError):
            rol[1] = 4
        with raises(ReadOnlyError):
            rol[1:4] = [4]
        with raises(ReadOnlyError):
            del rol[1]
        with raises(ReadOnlyError):
            del rol[1:4]
        with raises(ReadOnlyError):
            rol[1::2] = [4]
        with raises(ReadOnlyError):
            del rol[::2]
        with raises(ReadOnlyError):
            rol.append(4)
        with raises(ReadOnlyError):
            rol.clear()
        with raises(ReadOnlyError):
            rol.extend([4])
        with raises(ReadOnlyError):
            rol += [4]
        with raises(ReadOnlyError):
            rol *= 2
        with raises(ReadOnlyError):
            rol.insert(1, 4)
        with raises(ReadOnlyError):
            rol.pop()
        with raises(ReadOnlyError):
            rol.remove(2)
        with raises(ReadOnlyError):
            rol.sort()
        with raises(ReadOnlyError):
            rol.reverse()
        assert rol == [1, 2, 3]

    def can_add_rol():
        rol1 = ReadOnlyList([1, 2])
        rol2 = ReadOnlyList([3, 4])
        assert rol1 + rol2 == [1, 2, 3, 4]

    def can_add_tuple():
        rol = ReadOnlyList([1, 2])
        assert rol + (3, 4) == [1, 2, 3, 4]
