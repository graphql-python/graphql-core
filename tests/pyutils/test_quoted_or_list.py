from pytest import raises

from graphql.pyutils import quoted_or_list


def describe_quoted_or_list():
    def does_not_accept_an_empty_list():
        with raises(ValueError):
            quoted_or_list([])

    def returns_single_quoted_item():
        assert quoted_or_list(["A"]) == "'A'"

    def returns_two_item_list():
        assert quoted_or_list(["A", "B"]) == "'A' or 'B'"

    def returns_comma_separated_many_item_list():
        assert quoted_or_list(["A", "B", "C"]) == "'A', 'B' or 'C'"

    def limits_to_five_items():
        assert (
            quoted_or_list(["A", "B", "C", "D", "E", "F"])
            == "'A', 'B', 'C', 'D' or 'E'"
        )
