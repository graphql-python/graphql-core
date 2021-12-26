from graphql.pyutils import group_by


def describe_group_by():
    def does_accept_an_empty_list():
        def key_fn(_x: str) -> str:
            raise TypeError("Unexpected call of key function.")

        assert group_by([], key_fn) == {}

    def does_not_change_order():
        def key_fn(_x: int) -> str:
            return "all"

        assert group_by([3, 1, 5, 4, 2, 6], key_fn) == {
            "all": [3, 1, 5, 4, 2, 6],
        }

    def can_group_by_odd_and_even():
        def key_fn(x: int) -> str:
            return "odd" if x % 2 else "even"

        assert group_by([3, 1, 5, 4, 2, 6], key_fn) == {
            "odd": [3, 1, 5],
            "even": [4, 2, 6],
        }

    def can_group_by_string_length():
        def key_fn(s: str) -> int:
            return len(s)

        assert group_by(
            [
                "alpha",
                "beta",
                "gamma",
                "delta",
                "epsilon",
                "zeta",
                "eta",
                "iota",
                "kapp",
                "lambda",
                "my",
                "ny",
                "omikron",
            ],
            key_fn,
        ) == {
            2: ["my", "ny"],
            3: ["eta"],
            4: ["beta", "zeta", "iota", "kapp"],
            5: ["alpha", "gamma", "delta"],
            6: ["lambda"],
            7: ["epsilon", "omikron"],
        }
