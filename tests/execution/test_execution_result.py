from pytest import raises

from graphql.error import GraphQLError
from graphql.execution import ExecutionResult


def describe_execution_result():

    data = {"foo": "Some data"}
    error = GraphQLError("Some error")
    errors = [error]
    extensions = {"bar": "Some extension"}

    def initializes_properly():
        res = ExecutionResult(data, errors)
        assert res.data is data
        assert res.errors is errors
        assert res.extensions is None
        res = ExecutionResult(data, errors, extensions)
        assert res.data is data
        assert res.errors is errors
        assert res.extensions is extensions

    def prints_a_representation():
        assert repr(ExecutionResult(data, errors)) == (
            "ExecutionResult(data={'foo': 'Some data'},"
            " errors=[GraphQLError('Some error')])"
        )
        assert repr(ExecutionResult(data, errors, extensions)) == (
            "ExecutionResult(data={'foo': 'Some data'},"
            " errors=[GraphQLError('Some error')],"
            " extensions={'bar': 'Some extension'})"
        )

    def formats_properly():
        res = ExecutionResult(data, None)
        assert res.formatted == {"data": data}
        res = ExecutionResult(data, errors)
        assert res.formatted == {
            "data": data,
            "errors": [{"message": "Some error"}],
        }
        res = ExecutionResult(data, None, extensions)
        assert res.formatted == {
            "data": data,
            "extensions": extensions,
        }
        res = ExecutionResult(data, errors, extensions)
        assert res.formatted == {
            "data": data,
            "errors": [{"message": "Some error"}],
            "extensions": extensions,
        }

    def compares_to_dict():
        res = ExecutionResult(data, errors)
        assert res == {"data": data, "errors": errors}
        assert res == {"data": data, "errors": errors, "extensions": None}
        assert res != {"data": data, "errors": None}
        assert res != {"data": None, "errors": errors}
        assert res != {"data": data, "errors": errors, "extensions": extensions}
        res = ExecutionResult(data, errors, extensions)
        assert res == {"data": data, "errors": errors}
        assert res == {"data": data, "errors": errors, "extensions": extensions}
        assert res != {"data": data, "errors": None}
        assert res != {"data": None, "errors": errors}
        assert res != {"data": data, "errors": errors, "extensions": None}

    def compares_to_tuple():
        res = ExecutionResult(data, errors)
        assert res == (data, errors)
        assert res == (data, errors, None)
        assert res != (data, None)
        assert res != (None, errors)
        assert res != (data, errors, extensions)
        res = ExecutionResult(data, errors, extensions)
        assert res == (data, errors)
        assert res == (data, errors, extensions)
        assert res != (data, None)
        assert res != (None, errors)
        assert res != (data, errors, None)

    def does_not_compare_to_list():
        res = ExecutionResult(data, errors)
        assert res != [data, errors]
        res = ExecutionResult(data, errors, extensions)
        assert res != [data, errors, extensions]

    def compares_to_another_execution_result():
        res1 = ExecutionResult(data, errors)
        res2 = ExecutionResult(data, errors)
        assert res1 == res2
        res2 = ExecutionResult({"foo": "other data"}, errors)
        assert res1 != res2
        res2 = ExecutionResult(data, [GraphQLError("Another error")])
        assert res1 != res2
        res2 = ExecutionResult(data, errors, extensions)
        assert res1 != res2
        res1 = ExecutionResult(data, errors, extensions)
        res2 = ExecutionResult(data, errors, extensions)
        assert res1 == res2
        res2 = ExecutionResult({"foo": "other data"}, errors, extensions)
        assert res1 != res2
        res2 = ExecutionResult(data, [GraphQLError("Another error")], extensions)
        assert res1 != res2
        res2 = ExecutionResult(data, errors, {"bar": "Another extension"})
        assert res1 != res2

    def unpacks_as_two_tuple():
        res = ExecutionResult(data, errors)
        res_data, res_errors = res  # type: ignore
        assert res_data == data  # type: ignore
        assert res_errors == errors  # type: ignore
        with raises(ValueError):
            res = ExecutionResult(data, errors, extensions)
            _res_data, _res_errors, _res_extensions = res  # type: ignore
