from graphql.pyutils import Path


def describe_path():
    def can_create_a_path():
        first = Path(None, 1, "First")
        assert first.prev is None
        assert first.key == 1
        assert first.typename == "First"

    def can_add_a_new_key_to_an_existing_path():
        first = Path(None, 1, "First")
        second = first.add_key("two", "Second")
        assert second.prev is first
        assert second.key == "two"
        assert second.typename == "Second"

    def can_convert_a_path_to_a_list_of_its_keys():
        root = Path(None, 0, "Root")
        assert root.as_list() == [0]
        first = root.add_key("one", "First")
        assert first.as_list() == [0, "one"]
        second = first.add_key(2, "Second")
        assert second.as_list() == [0, "one", 2]
