from typing import Collection, List

__all__ = ["suggestion_list"]


def suggestion_list(input_: str, options: Collection[str]) -> List[str]:
    """Get list with suggestions for a given input.

    Given an invalid input string and list of valid options, returns a filtered list
    of valid options sorted based on their similarity with the input.
    """
    options_by_distance = {}
    lexical_distance = LexicalDistance(input_)

    input_threshold = len(input_) // 2
    for option in options:
        distance = lexical_distance.measure(option)
        threshold = max(input_threshold, len(option) // 2, 1)
        if distance <= threshold:
            options_by_distance[option] = distance

    # noinspection PyShadowingNames
    return sorted(
        options_by_distance,
        key=lambda option: (options_by_distance.get(option, 0), option),
    )


class LexicalDistance:
    """Computes the lexical distance between strings A and B.

    The "distance" between two strings is given by counting the minimum number of edits
    needed to transform string A into string B. An edit can be an insertion, deletion,
    or substitution of a single character, or a swap of two adjacent characters.

    This distance can be useful for detecting typos in input or sorting.
    """

    _input: str
    _input_lower_case: str
    _cells: List[List[int]]

    def __init__(self, input_: str):
        self._input = input_
        self._input_lower_case = input_.lower()
        self._cells = []

    def measure(self, option: str):
        if self._input == option:
            return 0

        option_lower_case = option.lower()

        # Any case change counts as a single edit
        if self._input_lower_case == option_lower_case:
            return 1

        d = self._cells
        a, b = option_lower_case, self._input_lower_case
        a_len, b_len = len(a), len(b)

        d = [[j for j in range(0, b_len + 1)]]
        for i in range(1, a_len + 1):
            d.append([i] + [0] * b_len)

        for i in range(1, a_len + 1):
            for j in range(1, b_len + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1

                current_cell = min(
                    d[i - 1][j] + 1,  # delete
                    d[i][j - 1] + 1,  # insert
                    d[i - 1][j - 1] + cost,  # substitute
                )

                if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                    # transposition
                    current_cell = min(current_cell, d[i - 2][j - 2] + 1)

                d[i][j] = current_cell

        return d[a_len][b_len]
