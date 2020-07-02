from . import gen_fuzz_strings


def describe_gen_fuzz_strings():
    def always_provide_empty_string():
        assert list(gen_fuzz_strings(allowed_chars="", max_length=0)) == [""]
        assert list(gen_fuzz_strings(allowed_chars="", max_length=1)) == [""]
        assert list(gen_fuzz_strings(allowed_chars="a", max_length=0)) == [""]

    def generate_strings_with_single_character():
        assert list(gen_fuzz_strings(allowed_chars="a", max_length=1)) == ["", "a"]
        assert list(gen_fuzz_strings(allowed_chars="abc", max_length=1)) == [
            "",
            "a",
            "b",
            "c",
        ]

    def generate_strings_with_multiple_character():
        assert list(gen_fuzz_strings(allowed_chars="a", max_length=2)) == [
            "",
            "a",
            "aa",
        ]

        assert list(gen_fuzz_strings(allowed_chars="abc", max_length=2)) == [
            "",
            "a",
            "b",
            "c",
            "aa",
            "ab",
            "ac",
            "ba",
            "bb",
            "bc",
            "ca",
            "cb",
            "cc",
        ]

    def generate_strings_longer_than_possible_number_of_characters():
        assert list(gen_fuzz_strings(allowed_chars="ab", max_length=3)) == [
            "",
            "a",
            "b",
            "aa",
            "ab",
            "ba",
            "bb",
            "aaa",
            "aab",
            "aba",
            "abb",
            "baa",
            "bab",
            "bba",
            "bbb",
        ]
