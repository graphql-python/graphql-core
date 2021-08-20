from graphql.pyutils import natural_comparison_key

key = natural_comparison_key


def describe_natural_compare():
    def handles_empty_strings():
        assert key("") < key("a")
        assert key("") < key("1")

    def handles_strings_of_different_length():
        assert key("A") < key("AA")
        assert key("A1") < key("A1A")

    def handles_numbers():
        assert key("1") < key("2")
        assert key("2") < key("11")

    def handles_numbers_with_leading_zeros():
        assert key("0") < key("00")
        assert key("02") < key("11")
        assert key("011") < key("200")

    def handles_numbers_embedded_into_names():
        assert key("a0a") < key("a9a")
        assert key("a00a") < key("a09a")
        assert key("a0a1") < key("a0a9")
        assert key("a10a11a") < key("a10a19a")
        assert key("a10a11a") < key("a10a11b")
