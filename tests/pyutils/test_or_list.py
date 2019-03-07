from pytest import raises

from graphql.pyutils import or_list


def describe_or_list():
    def returns_none_for_empty_list():
        with raises(ValueError):
            or_list([])

    def prints_list_with_one_item():
        assert or_list(["one"]) == "one"

    def prints_list_with_two_items():
        assert or_list(["one", "two"]) == "one or two"

    def prints_list_with_three_items():
        assert or_list(["A", "B", "C"]) == "A, B or C"
        assert or_list(["one", "two", "three"]) == "one, two or three"

    def prints_list_with_five_items():
        assert or_list(["A", "B", "C", "D", "E"]) == "A, B, C, D or E"

    def prints_shortened_list_with_six_items():
        assert or_list(["A", "B", "C", "D", "E", "F"]) == "A, B, C, D or E"

    def prints_tuple_with_three_items():
        assert or_list(("A", "B", "C")) == "A, B or C"
