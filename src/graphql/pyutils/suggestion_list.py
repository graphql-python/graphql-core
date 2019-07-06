from typing import Collection, List

__all__ = ["suggestion_list"]


def suggestion_list(input_: str, options: Collection[str]) -> List[str]:
    """Get list with suggestions for a given input.

    Given an invalid input string and list of valid options, returns a filtered list
    of valid options sorted based on their similarity with the input.
    """
    options_by_distance = {}
    input_threshold = len(input_) // 2

    for option in options:
        distance = lexical_distance(input_, option)
        threshold = max(input_threshold, len(option) // 2, 1)
        if distance <= threshold:
            options_by_distance[option] = distance

    return sorted(options_by_distance, key=options_by_distance.get)


def lexical_distance(a_str: str, b_str: str) -> int:
    """Computes the lexical distance between strings A and B.

    The "distance" between two strings is given by counting the minimum number of edits
    needed to transform string A into string B. An edit can be an insertion, deletion,
    or substitution of a single character, or a swap of two adjacent characters.

    This distance can be useful for detecting typos in input or sorting.
    """
    if a_str == b_str:
        return 0

    a, b = a_str.lower(), b_str.lower()
    a_len, b_len = len(a), len(b)

    # Any case change counts as a single edit
    if a == b:
        return 1

    d = [[j for j in range(0, b_len + 1)]]
    for i in range(1, a_len + 1):
        d.append([i] + [0] * b_len)

    for i in range(1, a_len + 1):
        for j in range(1, b_len + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1

            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)

            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)

    return d[a_len][b_len]
