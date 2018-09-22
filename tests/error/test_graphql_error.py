from graphql.error import GraphQLError, format_error
from graphql.language import parse, Source


def describe_graphql_error():
    def is_a_class_and_is_a_subclass_of_exception():
        assert issubclass(GraphQLError, Exception)
        assert isinstance(GraphQLError("msg"), GraphQLError)

    def has_a_name_message_and_stack_trace():
        e = GraphQLError("msg")
        assert e.__class__.__name__ == "GraphQLError"
        assert e.message == "msg"

    def stores_the_original_error():
        original = Exception("original")
        e = GraphQLError("msg", original_error=original)
        assert e.__class__.__name__ == "GraphQLError"
        assert e.message == "msg"
        assert e.original_error == original

    def converts_nodes_to_positions_and_locations():
        source = Source("{\n      field\n}")
        ast = parse(source)
        # noinspection PyUnresolvedReferences
        field_node = ast.definitions[0].selection_set.selections[0]
        e = GraphQLError("msg", [field_node])
        assert e.nodes == [field_node]
        assert e.source is source
        assert e.positions == [8]
        assert e.locations == [(2, 7)]

    def converts_single_node_to_positions_and_locations():
        source = Source("{\n      field\n}")
        ast = parse(source)
        # noinspection PyUnresolvedReferences
        field_node = ast.definitions[0].selection_set.selections[0]
        e = GraphQLError("msg", field_node)  # Non-array value.
        assert e.nodes == [field_node]
        assert e.source is source
        assert e.positions == [8]
        assert e.locations == [(2, 7)]

    def converts_node_with_loc_start_zero_to_positions_and_locations():
        source = Source("{\n      field\n}")
        ast = parse(source)
        operations_node = ast.definitions[0]
        e = GraphQLError("msg", [operations_node])
        assert e.nodes == [operations_node]
        assert e.source is source
        assert e.positions == [0]
        assert e.locations == [(1, 1)]

    def converts_source_and_positions_to_locations():
        source = Source("{\n      field\n}")
        # noinspection PyArgumentEqualDefault
        e = GraphQLError("msg", None, source, [10])
        assert e.nodes is None
        assert e.source is source
        assert e.positions == [10]
        assert e.locations == [(2, 9)]

    def serializes_to_include_message():
        e = GraphQLError("msg")
        assert str(e) == "msg"
        assert repr(e) == "GraphQLError('msg')"

    def serializes_to_include_message_and_locations():
        # noinspection PyUnresolvedReferences
        node = parse("{ field }").definitions[0].selection_set.selections[0]
        e = GraphQLError("msg", [node])
        assert "msg" in str(e)
        assert "(1:3)" in str(e)
        assert repr(e) == (
            "GraphQLError('msg', locations=[SourceLocation(line=1, column=3)])"
        )

    def serializes_to_include_path():
        path = ["path", 3, "to", "field"]
        # noinspection PyArgumentEqualDefault
        e = GraphQLError("msg", None, None, None, path)
        assert e.path is path
        assert repr(e) == "GraphQLError('msg', path=['path', 3, 'to', 'field'])"

    def default_error_formatter_includes_path():
        path = ["path", 3, "to", "field"]
        # noinspection PyArgumentEqualDefault
        e = GraphQLError("msg", None, None, None, path)
        formatted = format_error(e)
        assert formatted == e.formatted
        assert formatted == {"message": "msg", "locations": None, "path": path}

    def default_error_formatter_includes_extension_fields():
        # noinspection PyArgumentEqualDefault
        e = GraphQLError("msg", None, None, None, None, None, {"foo": "bar"})
        formatted = format_error(e)
        assert formatted == e.formatted
        assert formatted == {
            "message": "msg",
            "locations": None,
            "path": None,
            "extensions": {"foo": "bar"},
        }
