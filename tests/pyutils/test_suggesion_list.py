from graphql.pyutils import suggestion_list


def describe_suggestion_list():
    def returns_results_when_input_is_empty():
        assert suggestion_list("", ["a"]) == ["a"]

    def returns_empty_array_when_there_are_no_options():
        assert suggestion_list("input", []) == []

    def returns_options_with_small_lexical_distance():
        assert suggestion_list("greenish", ["green"]) == ["green"]
        assert suggestion_list("green", ["greenish"]) == ["greenish"]

    def returns_options_with_different_case():
        assert suggestion_list("verylongstring", ["VERYLONGSTRING"]) == [
            "VERYLONGSTRING"
        ]

        assert suggestion_list("VERYLONGSTRING", ["verylongstring"]) == [
            "verylongstring"
        ]

        assert suggestion_list("VERYLONGSTRING", ["VeryLongString"]) == [
            "VeryLongString"
        ]

    def returns_options_with_transpositions():
        assert suggestion_list("agr", ["arg"]) == ["arg"]

        assert suggestion_list("214365879", ["123456789"]) == ["123456789"]

    def returns_options_sorted_based_on_lexical_distance():
        assert suggestion_list("abc", ["a", "ab", "abc"]) == ["abc", "ab"]

        assert suggestion_list(
            "GraphQl", ["graphics", "SQL", "GraphQL", "quarks", "mark"]
        ) == ["GraphQL", "graphics"]

    def returns_options_with_the_same_lexical_distance_sorted_lexicographically():
        assert suggestion_list("a", ["az", "ax", "ay"]) == ["ax", "ay", "az"]

        assert suggestion_list("boo", ["moo", "foo", "zoo"]) == ["foo", "moo", "zoo"]

    def returns_options_sorted_first_by_lexical_distance_then_lexicographically():
        assert suggestion_list(
            "csutomer", ["store", "customer", "stomer", "some", "more"]
        ) == ["customer", "stomer", "some", "store"]
