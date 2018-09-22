def compare_query_results_unordered(data, reference):
    def err_to_dict(exception):
        exception_dict = {
            "message": exception.message,
            "path": exception.path,
            "locations": exception.locations,
        }

        extensions = exception.extensions
        if extensions:
            exception_dict["extensions"] = extensions

        return exception_dict

    def key(e):
        return e["path"]

    assert data[0] == reference[0]
    assert sorted(map(err_to_dict, data[1]), key=key) == sorted(reference[1], key=key)
