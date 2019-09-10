from graphql.pyutils import print_path_list


def describe_print_path_as_list():
    def without_key():
        assert print_path_list([]) == ""

    def with_one_key():
        assert print_path_list(["one"]) == ".one"
        assert print_path_list([1]) == "[1]"

    def with_three_keys():
        assert print_path_list([0, "one", 2]) == "[0].one[2]"
        assert print_path_list(["one", 2, "three"]) == ".one[2].three"
