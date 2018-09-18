from datetime import date

from pytest import fixture

from graphql.pyutils import contain_subset


def describe_plain_object():

    tested_object = {"a": "b", "c": "d"}

    def should_pass_for_smaller_object():
        assert contain_subset(tested_object, {"a": "b"})

    def should_pass_for_same_object():
        assert contain_subset(tested_object, {"a": "b", "c": "d"})

    def should_pass_for_similar_but_not_the_same_object():
        assert not contain_subset(tested_object, {"a": "notB", "c": "d"})


def describe_complex_object():

    tested_object = {"a": "b", "c": "d", "e": {"foo": "bar", "baz": {"qux": "quux"}}}

    def should_pass_for_smaller_object_1():
        assert contain_subset(tested_object, {"a": "b", "e": {"foo": "bar"}})

    def should_pass_for_smaller_object_2():
        assert contain_subset(
            tested_object, {"e": {"foo": "bar", "baz": {"qux": "quux"}}}
        )

    def should_pass_for_same_object():
        assert contain_subset(
            tested_object,
            {"a": "b", "c": "d", "e": {"foo": "bar", "baz": {"qux": "quux"}}},
        )

    def should_pass_for_similar_but_not_the_same_object():
        assert not contain_subset(
            tested_object, {"e": {"foo": "bar", "baz": {"qux": "notAQuux"}}}
        )

    def should_fail_if_comparing_when_comparing_objects_to_dates():
        assert not contain_subset(tested_object, {"e": date.today()})


def describe_circular_objects():
    @fixture
    def test_object():
        obj = {}
        obj["arr"] = [obj, obj]
        obj["arr"].append(obj["arr"])
        obj["obj"] = obj
        return obj

    # noinspection PyShadowingNames
    def should_contain_subdocument(test_object):
        assert contain_subset(
            test_object, {"arr": [{"arr": []}, {"arr": []}, [{"arr": []}, {"arr": []}]]}
        )

    # noinspection PyShadowingNames
    def should_not_contain_similar_object(test_object):
        assert not contain_subset(
            test_object,
            {
                "arr": [
                    {"arr": ["just random field"]},
                    {"arr": []},
                    [{"arr": []}, {"arr": []}],
                ]
            },
        )


def describe_object_with_compare_function():
    def should_pass_when_function_returns_true():
        assert contain_subset({"a": 5}, {"a": lambda a: a})

    def should_fail_when_function_returns_false():
        assert not contain_subset({"a": 5}, {"a": lambda a: not a})

    def should_pass_for_function_with_no_arguments():
        assert contain_subset({"a": 5}, {"a": lambda: True})


def describe_comparison_of_non_objects():
    def should_fail_if_actual_subset_is_null():
        assert not contain_subset(None, {"a": 1})

    def should_fail_if_expected_subset_is_not_an_object():
        assert not contain_subset({"a": 1}, None)

    def should_not_fail_for_same_non_object_string_variables():
        assert contain_subset("string", "string")


def describe_comparison_of_dates():
    def should_pass_for_the_same_date():
        assert contain_subset(date(2015, 11, 30), date(2015, 11, 30))

    def should_pass_for_the_same_date_if_nested():
        assert contain_subset({"a": date(2015, 11, 30)}, {"a": date(2015, 11, 30)})

    def should_fail_for_a_different_date():
        assert not contain_subset(date(2015, 11, 30), date(2012, 2, 22))

    def should_fail_for_a_different_date_if_nested():
        assert not contain_subset({"a": date(2015, 11, 30)}, {"a": date(2015, 2, 22)})


def describe_cyclic_objects():
    def should_pass():
        child = {}
        parent = {"children": [child]}
        child["parent"] = parent

        my_object = {"a": 1, "b": "two", "c": parent}
        assert contain_subset(my_object, {"a": 1, "c": parent})


def describe_list_objects():

    test_list = [{"a": "a", "b": "b"}, {"v": "f", "d": {"z": "g"}}]

    def works_well_with_lists():
        assert contain_subset(test_list, [{"a": "a"}])
        assert contain_subset(test_list, [{"a": "a", "b": "b"}])
        assert not contain_subset(test_list, [{"a": "a", "b": "bd"}])
