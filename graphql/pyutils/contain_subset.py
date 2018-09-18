__all__ = ["contain_subset"]


def contain_subset(actual, expected):
    """Recursively check if actual collection contains an expected subset.

    This simulates the containSubset object properties matcher for Chai.
    """
    if expected == actual:
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return all(
            any(contain_subset(actual_value, expected_value) for actual_value in actual)
            for expected_value in expected
        )
    if not isinstance(expected, dict):
        return False
    if not isinstance(actual, dict):
        return False
    for key, expected_value in expected.items():
        try:
            actual_value = actual[key]
        except KeyError:
            return False
        if callable(expected_value):
            try:
                if not expected_value(actual_value):
                    return False
            except TypeError:
                if not expected_value():
                    return False
        elif not contain_subset(actual_value, expected_value):
            return False
    return True
