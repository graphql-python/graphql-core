"""List with suggestions"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .natural_compare import natural_comparison_key

if TYPE_CHECKING:
    from collections.abc import Collection

__all__ = ["suggestion_list"]


def suggestion_list(input_: str, options: Collection[str]) -> list[str]:
    """Get list with suggestions for a given input.

    Given an invalid input string and list of valid options, returns a filtered list
    of valid options sorted based on their similarity with the input.
    """
    options_by_distance = {}
    lexical_distance = LexicalDistance(input_)

    threshold = int(len(input_) * 0.4) + 1
    for option in options:
        distance = lexical_distance.measure(option, threshold)
        if distance is not None:
            options_by_distance[option] = distance

    return sorted(
        options_by_distance,
        key=lambda option: (
            options_by_distance.get(option, 0),
            natural_comparison_key(option),
        ),
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
    _rows: list[list[int]]

    def __init__(self, input_: str) -> None:
        self._input = input_
        self._input_lower_case = input_.lower()
        row_size = len(input_) + 1
        self._rows = [[0] * row_size, [0] * row_size, [0] * row_size]

    def measure(self, option: str, threshold: int) -> int | None:
        if self._input == option:
            return 0

        option_lower_case = option.lower()

        # Any case change counts as a single edit
        if self._input_lower_case == option_lower_case:
            return 1

        a = self._input_lower_case
        b = option_lower_case
        a_len = len(a)
        b_len = len(b)
        if a_len < b_len:
            a, b = b, a
            a_len, b_len = b_len, a_len

        # Too many missing characters to fit under the threshold.
        if a_len - b_len > threshold:
            return None

        # Matching characters at the start or end of both strings never need
        # an edit in an optimal alignment, so only the middle part is scored.
        start = 0
        while start < b_len and a[start] == b[start]:
            start += 1
        end = 0
        while end < b_len - start and a[a_len - 1 - end] == b[b_len - 1 - end]:
            end += 1
        a = a[start : a_len - end]
        b = b[start : b_len - end]
        a_len = len(a)
        b_len = len(b)

        # Rotate three row buffers instead of allocating a table per option.
        # ``prev`` is row i-1, ``cur`` is the row being computed and ``prev2``
        # is row i-2, needed for the transposition check.
        prev2, prev, cur = self._rows[2], self._rows[0], self._rows[1]
        for j in range(b_len + 1):
            prev[j] = j

        for i in range(1, a_len + 1):
            a_char = a[i - 1]
            smallest_cell = cur[0] = i
            for j in range(1, b_len + 1):
                if a_char == b[j - 1]:
                    # Equal characters cost nothing: the diagonal cell is
                    # always the smallest of the three candidates.
                    current_cell = prev[j - 1]
                else:
                    current_cell = prev[j] + 1  # delete
                    insert = cur[j - 1] + 1
                    substitute = prev[j - 1] + 1
                    if insert < current_cell:
                        current_cell = insert
                    if substitute < current_cell:
                        current_cell = substitute

                if i > 1 and j > 1 and a_char == b[j - 2] and a[i - 2] == b[j - 1]:
                    transposition = prev2[j - 2] + 1
                    if transposition < current_cell:
                        current_cell = transposition

                if current_cell < smallest_cell:
                    smallest_cell = current_cell
                cur[j] = current_cell

            # The distance cannot fall below the smallest cell of this row.
            if smallest_cell > threshold:
                return None

            prev2, prev, cur = prev, cur, prev2

        distance = prev[b_len]
        return distance if distance <= threshold else None
