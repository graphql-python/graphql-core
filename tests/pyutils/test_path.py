from graphql.pyutils import Path


def describe_path():
    def add_path():
        path = Path(None, 0)
        assert path.prev is None
        assert path.key == 0
        prev, path = path, Path(path, 1)
        assert path.prev is prev
        assert path.key == 1
        prev, path = path, Path(path, "two")
        assert path.prev is prev
        assert path.key == "two"

    def add_key():
        prev = Path(None, 0)
        path = prev.add_key("one")
        assert path.prev is prev
        assert path.key == "one"

    def as_list():
        path = Path(None, 1)
        assert path.as_list() == [1]
        path = path.add_key("two")
        assert path.as_list() == [1, "two"]
        path = path.add_key(3)
        assert path.as_list() == [1, "two", 3]
