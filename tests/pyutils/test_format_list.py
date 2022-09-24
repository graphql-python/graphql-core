from pytest import raises

from graphql.pyutils import and_list, or_list


def describe_and_list():
    def does_not_accept_an_empty_list():
        with raises(ValueError):
            and_list([])

    def handles_single_item():
        assert and_list(["A"]) == "A"

    def handles_two_items():
        assert and_list(["A", "B"]) == "A and B"

    def handles_three_items():
        assert and_list(["A", "B", "C"]) == "A, B, and C"

    def handles_more_than_five_items():
        assert and_list(["A", "B", "C", "D", "E", "F"]) == "A, B, C, D, E, and F"


def describe_or_list():
    def does_not_accept_an_empty_list():
        with raises(ValueError):
            or_list([])

    def handles_single_item():
        assert or_list(["A"]) == "A"

    def handles_two_items():
        assert or_list(["A", "B"]) == "A or B"

    def handles_three_items():
        assert or_list(["A", "B", "C"]) == "A, B, or C"

    def handles_more_than_five_items():
        assert or_list(["A", "B", "C", "D", "E", "F"]) == "A, B, C, D, E, or F"
