from __future__ import annotations

import asyncio
from typing import Any, Awaitable, cast

import pytest
from graphql.error import GraphQLError
from graphql.execution import execute, execute_sync
from graphql.language import FieldNode, OperationDefinitionNode, parse
from graphql.pyutils import Undefined, inspect
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLDeferDirective,
    GraphQLField,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLResolveInfo,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLStreamDirective,
    GraphQLString,
    GraphQLUnionType,
    ResponsePath,
)


def describe_execute_handles_basic_execution_tasks():
    def accepts_positional_arguments():
        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type",
                {"a": GraphQLField(GraphQLString, resolve=lambda obj, *_args: obj)},
            )
        )

        result = execute_sync(schema, parse("{ a }"), "rootValue")

        assert result == ({"a": "rootValue"}, None)

    @pytest.mark.asyncio()
    async def executes_arbitrary_code():
        # noinspection PyMethodMayBeStatic,PyMethodMayBeStatic
        class Data:
            def a(self, _info):
                return "Apple"

            def b(self, _info):
                return "Banana"

            def c(self, _info):
                return "Cookie"

            def d(self, _info):
                return "Donut"

            def e(self, _info):
                return "Egg"

            f = "Fish"

            # Called only by DataType::pic static resolver
            def pic(self, _info, size: int):
                return f"Pic of size: {size}"

            def deep(self, _info):
                return DeepData()

            def promise(self, _info):
                return promise_data()

        # noinspection PyMethodMayBeStatic,PyMethodMayBeStatic
        class DeepData:
            def a(self, _info):
                return "Already Been Done"

            def b(self, _info):
                return "Boring"

            def c(self, _info):
                return ["Contrived", None, "Confusing"]

            def deeper(self, _info):
                return [Data(), None, Data()]

        async def promise_data():
            await asyncio.sleep(0)
            return Data()

        DeepDataType: GraphQLObjectType

        DataType = GraphQLObjectType(
            "DataType",
            lambda: {
                "a": GraphQLField(GraphQLString),
                "b": GraphQLField(GraphQLString),
                "c": GraphQLField(GraphQLString),
                "d": GraphQLField(GraphQLString),
                "e": GraphQLField(GraphQLString),
                "f": GraphQLField(GraphQLString),
                "pic": GraphQLField(
                    GraphQLString,
                    args={"size": GraphQLArgument(GraphQLInt)},
                    resolve=lambda obj, info, size: obj.pic(info, size),
                ),
                "deep": GraphQLField(DeepDataType),
                "promise": GraphQLField(DataType),
            },
        )

        DeepDataType = GraphQLObjectType(
            "DeepDataType",
            {
                "a": GraphQLField(GraphQLString),
                "b": GraphQLField(GraphQLString),
                "c": GraphQLField(GraphQLList(GraphQLString)),
                "deeper": GraphQLField(GraphQLList(DataType)),
            },
        )

        document = parse(
            """
            query ($size: Int) {
              a,
              b,
              x: c
              ...c
              f
              ...on DataType {
                pic(size: $size)
                promise {
                  a
                }
              }
              deep {
                a
                b
                c
                deeper {
                  a
                  b
                }
              }
            }

            fragment c on DataType {
              d
              e
            }
            """
        )

        awaitable_result = execute(
            GraphQLSchema(DataType), document, Data(), variable_values={"size": 100}
        )
        assert isinstance(awaitable_result, Awaitable)
        result = await awaitable_result

        assert result == (
            {
                "a": "Apple",
                "b": "Banana",
                "x": "Cookie",
                "d": "Donut",
                "e": "Egg",
                "f": "Fish",
                "pic": "Pic of size: 100",
                "promise": {"a": "Apple"},
                "deep": {
                    "a": "Already Been Done",
                    "b": "Boring",
                    "c": ["Contrived", None, "Confusing"],
                    "deeper": [
                        {"a": "Apple", "b": "Banana"},
                        None,
                        {"a": "Apple", "b": "Banana"},
                    ],
                },
            },
            None,
        )

    def merges_parallel_fragments():
        Type = GraphQLObjectType(
            "Type",
            lambda: {
                "a": GraphQLField(GraphQLString, resolve=lambda *_args: "Apple"),
                "b": GraphQLField(GraphQLString, resolve=lambda *_args: "Banana"),
                "c": GraphQLField(GraphQLString, resolve=lambda *_args: "Cherry"),
                "deep": GraphQLField(Type, resolve=lambda *_args: {}),
            },
        )
        schema = GraphQLSchema(Type)

        ast = parse(
            """
            { a, ...FragOne, ...FragTwo }

            fragment FragOne on Type {
              b
              deep { b, deeper: deep { b } }
            }

            fragment FragTwo on Type {
              c
              deep { c, deeper: deep { c } }
            }
            """
        )

        result = execute_sync(schema, ast)
        assert result == (
            {
                "a": "Apple",
                "b": "Banana",
                "c": "Cherry",
                "deep": {
                    "b": "Banana",
                    "c": "Cherry",
                    "deeper": {"b": "Banana", "c": "Cherry"},
                },
            },
            None,
        )

    def provides_info_about_current_execution_state():
        resolved_infos = []

        def resolve(_obj, info):
            resolved_infos.append(info)

        test_type = GraphQLObjectType(
            "Test", {"test": GraphQLField(GraphQLString, resolve=resolve)}
        )

        schema = GraphQLSchema(test_type)

        document = parse("query ($var: String) { result: test }")
        root_value = {"root": "val"}
        variable_values = {"var": "abc"}
        execute_sync(schema, document, root_value, variable_values=variable_values)

        assert len(resolved_infos) == 1
        operation = cast(OperationDefinitionNode, document.definitions[0])
        assert operation
        assert operation.kind == "operation_definition"
        field = cast(FieldNode, operation.selection_set.selections[0])

        assert resolved_infos[0] == GraphQLResolveInfo(
            field_name="test",
            field_nodes=[field],
            return_type=GraphQLString,
            parent_type=cast(GraphQLObjectType, schema.query_type),
            path=ResponsePath(None, "result", "Test"),
            schema=schema,
            fragments={},
            root_value=root_value,
            operation=operation,
            variable_values=variable_values,
            context=None,
            is_awaitable=resolved_infos[0].is_awaitable,
        )

    def it_populates_path_correctly_with_complex_types():
        path: ResponsePath | None = None

        def resolve(_val, info):
            nonlocal path
            path = info.path

        def resolve_type(_val, _info, _type):
            return "SomeObject"

        some_object = GraphQLObjectType(
            "SomeObject", {"test": GraphQLField(GraphQLString, resolve=resolve)}
        )
        some_union = GraphQLUnionType(
            "SomeUnion", [some_object], resolve_type=resolve_type
        )
        test_type = GraphQLObjectType(
            "SomeQuery",
            {
                "test": GraphQLField(
                    GraphQLNonNull(GraphQLList(GraphQLNonNull(some_union)))
                )
            },
        )
        schema = GraphQLSchema(test_type)
        root_value: Any = {"test": [{}]}
        document = parse(
            """
            query {
              l1: test {
                ... on SomeObject {
                  l2: test
                }
              }
            }
            """
        )

        execute_sync(schema, document, root_value)

        assert path is not None
        prev, key, typename = path
        assert key == "l2"
        assert typename == "SomeObject"
        assert prev is not None
        prev, key, typename = prev
        assert key == 0
        assert typename is None
        assert prev is not None
        prev, key, typename = prev
        assert key == "l1"
        assert typename == "SomeQuery"
        assert prev is None

    def threads_root_value_context_correctly():
        resolved_values = []

        class Data:
            context_thing = "thing"

        def resolve(obj, _info):
            resolved_values.append(obj)

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type", {"a": GraphQLField(GraphQLString, resolve=resolve)}
            )
        )

        document = parse("query Example { a }")
        root_value = Data()
        execute_sync(schema, document, root_value)

        assert len(resolved_values) == 1
        assert resolved_values[0] is root_value

    def correctly_threads_arguments():
        resolved_args = []

        def resolve(_obj, _info, **args):
            resolved_args.append(args)

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type",
                {
                    "b": GraphQLField(
                        GraphQLString,
                        args={
                            "numArg": GraphQLArgument(GraphQLInt),
                            "stringArg": GraphQLArgument(GraphQLString),
                        },
                        resolve=resolve,
                    )
                },
            )
        )

        document = parse(
            """
            query Example {
              b(numArg: 123, stringArg: "foo")
            }
            """
        )

        execute_sync(schema, document)

        assert len(resolved_args) == 1
        assert resolved_args[0] == {"numArg": 123, "stringArg": "foo"}

    @pytest.mark.asyncio()
    async def nulls_out_error_subtrees():
        document = parse(
            """
            {
              syncOk
              syncError
              syncRawError
              syncReturnError
              syncReturnErrorList
              asyncOk
              asyncError
              asyncRawError
              asyncReturnError
              asyncReturnErrorWithExtensions
            }
            """
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type",
                {
                    "syncOk": GraphQLField(GraphQLString),
                    "syncError": GraphQLField(GraphQLString),
                    "syncRawError": GraphQLField(GraphQLString),
                    "syncReturnError": GraphQLField(GraphQLString),
                    "syncReturnErrorList": GraphQLField(GraphQLList(GraphQLString)),
                    "asyncOk": GraphQLField(GraphQLString),
                    "asyncError": GraphQLField(GraphQLString),
                    "asyncErrorWithExtensions": GraphQLField(GraphQLString),
                    "asyncRawError": GraphQLField(GraphQLString),
                    "asyncReturnError": GraphQLField(GraphQLString),
                    "asyncReturnErrorWithExtensions": GraphQLField(GraphQLString),
                },
            )
        )

        # noinspection PyPep8Naming,PyMethodMayBeStatic
        class Data:
            def syncOk(self, _info):
                return "sync ok"

            def syncError(self, _info):
                raise GraphQLError("Error getting syncError")

            def syncRawError(self, _info):
                raise Exception("Error getting syncRawError")

            def syncReturnError(self, _info):
                return Exception("Error getting syncReturnError")

            def syncReturnErrorList(self, _info):
                return [
                    "sync0",
                    Exception("Error getting syncReturnErrorList1"),
                    "sync2",
                    Exception("Error getting syncReturnErrorList3"),
                ]

            async def asyncOk(self, _info):
                return "async ok"

            async def asyncError(self, _info):
                raise GraphQLError("Error getting asyncError")

            async def asyncRawError(self, _info):
                raise Exception("Error getting asyncRawError")

            async def asyncReturnError(self, _info):
                return GraphQLError("Error getting asyncReturnError")

            async def asyncReturnErrorWithExtensions(self, _info):
                return GraphQLError(
                    "Error getting asyncReturnErrorWithExtensions",
                    extensions={"foo": "bar"},
                )

        awaitable_result = execute(schema, document, Data())
        assert isinstance(awaitable_result, Awaitable)
        result = await awaitable_result

        assert result == (
            {
                "syncOk": "sync ok",
                "syncError": None,
                "syncRawError": None,
                "syncReturnError": None,
                "syncReturnErrorList": ["sync0", None, "sync2", None],
                "asyncOk": "async ok",
                "asyncError": None,
                "asyncRawError": None,
                "asyncReturnError": None,
                "asyncReturnErrorWithExtensions": None,
            },
            [
                {
                    "message": "Error getting syncError",
                    "locations": [(4, 15)],
                    "path": ["syncError"],
                },
                {
                    "message": "Error getting syncRawError",
                    "locations": [(5, 15)],
                    "path": ["syncRawError"],
                },
                {
                    "message": "Error getting syncReturnError",
                    "locations": [(6, 15)],
                    "path": ["syncReturnError"],
                },
                {
                    "message": "Error getting syncReturnErrorList1",
                    "locations": [(7, 15)],
                    "path": ["syncReturnErrorList", 1],
                },
                {
                    "message": "Error getting syncReturnErrorList3",
                    "locations": [(7, 15)],
                    "path": ["syncReturnErrorList", 3],
                },
                {
                    "message": "Error getting asyncError",
                    "locations": [(9, 15)],
                    "path": ["asyncError"],
                },
                {
                    "message": "Error getting asyncRawError",
                    "locations": [(10, 15)],
                    "path": ["asyncRawError"],
                },
                {
                    "message": "Error getting asyncReturnError",
                    "locations": [(11, 15)],
                    "path": ["asyncReturnError"],
                },
                {
                    "message": "Error getting asyncReturnErrorWithExtensions",
                    "locations": [(12, 15)],
                    "path": ["asyncReturnErrorWithExtensions"],
                    "extensions": {"foo": "bar"},
                },
            ],
        )

    @pytest.mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    def handles_sync_errors_combined_with_async_ones():
        is_async_resolver_finished = False

        async def async_resolver(_obj, _info):
            nonlocal is_async_resolver_finished
            is_async_resolver_finished = True  # pragma: no cover

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "syncNullError": GraphQLField(
                        GraphQLNonNull(GraphQLString), resolve=lambda _obj, _info: None
                    ),
                    "asyncNullError": GraphQLField(
                        GraphQLNonNull(GraphQLString), resolve=async_resolver
                    ),
                },
            )
        )

        document = parse(
            """
            {
              asyncNullError
              syncNullError
            }
            """
        )

        result = execute(schema, document)

        assert is_async_resolver_finished is False

        assert result == (
            None,
            [
                {
                    "message": "Cannot return null"
                    " for non-nullable field Query.syncNullError.",
                    "locations": [(4, 15)],
                    "path": ["syncNullError"],
                }
            ],
        )

    @pytest.mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    def full_response_path_is_included_for_non_nullable_fields():
        def resolve_ok(*_args):
            return {}

        def resolve_error(*_args):
            raise Exception("Catch me if you can")

        A = GraphQLObjectType(
            "A",
            lambda: {
                "nullableA": GraphQLField(A, resolve=resolve_ok),
                "nonNullA": GraphQLField(GraphQLNonNull(A), resolve=resolve_ok),
                "throws": GraphQLField(GraphQLNonNull(A), resolve=resolve_error),
            },
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "query", lambda: {"nullableA": GraphQLField(A, resolve=resolve_ok)}
            )
        )

        document = parse(
            """
            query {
              nullableA {
                aliasedA: nullableA {
                  nonNullA {
                    anotherA: nonNullA {
                      throws
                    }
                  }
                }
              }
            }
            """
        )

        assert execute_sync(schema, document) == (
            {"nullableA": {"aliasedA": None}},
            [
                {
                    "message": "Catch me if you can",
                    "locations": [(7, 23)],
                    "path": ["nullableA", "aliasedA", "nonNullA", "anotherA", "throws"],
                }
            ],
        )

    def uses_the_inline_operation_if_no_operation_name_is_provided():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse("{ a }")

        class Data:
            a = "b"

        result = execute_sync(schema, document, Data())
        assert result == ({"a": "b"}, None)

    @pytest.mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    def uses_the_only_operation_if_no_operation_name_is_provided():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse("query Example { a }")

        class Data:
            a = "b"

        result = execute_sync(schema, document, Data())
        assert result == ({"a": "b"}, None)

    @pytest.mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    def uses_the_named_operation_if_operation_name_is_provided():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse(
            """
            query Example { first: a }
            query OtherExample { second: a }
            """
        )

        class Data:
            a = "b"

        result = execute_sync(schema, document, Data(), operation_name="OtherExample")
        assert result == ({"second": "b"}, None)

    def provides_error_if_no_operation_is_provided():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse("fragment Example on Type { a }")

        class Data:
            a = "b"

        result = execute_sync(schema, document, Data())
        assert result == (None, [{"message": "Must provide an operation."}])

    def errors_if_no_operation_name_is_provided_with_multiple_operations():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse(
            """
            query Example { a }
            query OtherExample { a }
            """
        )

        result = execute_sync(schema, document)
        assert result == (
            None,
            [
                {
                    "message": "Must provide operation name if query contains"
                    " multiple operations."
                }
            ],
        )

    def errors_if_unknown_operation_name_is_provided():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse(
            """
            query Example { a }
            query OtherExample { a }
            """
        )

        result = execute_sync(schema, document, operation_name="UnknownExample")
        assert result == (
            None,
            [{"message": "Unknown operation named 'UnknownExample'."}],
        )

    def errors_if_empty_string_is_provided_as_operation_name():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse("{ a }")

        result = execute_sync(schema, document, operation_name="")
        assert result == (
            None,
            [{"message": "Unknown operation named ''."}],
        )

    def uses_the_query_schema_for_queries():
        schema = GraphQLSchema(
            GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            GraphQLObjectType("M", {"c": GraphQLField(GraphQLString)}),
            GraphQLObjectType("S", {"a": GraphQLField(GraphQLString)}),
        )

        document = parse(
            """
            query Q { a }
            mutation M { c }
            subscription S { a }
            """
        )

        class Data:
            a = "b"
            c = "d"

        result = execute_sync(schema, document, Data(), operation_name="Q")
        assert result == ({"a": "b"}, None)

    def uses_the_mutation_schema_for_mutations():
        schema = GraphQLSchema(
            GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            GraphQLObjectType("M", {"c": GraphQLField(GraphQLString)}),
        )

        document = parse(
            """
            query Q { a }
            mutation M { c }
            """
        )

        class Data:
            a = "b"
            c = "d"

        result = execute_sync(schema, document, Data(), operation_name="M")
        assert result == ({"c": "d"}, None)

    def uses_the_subscription_schema_for_subscriptions():
        schema = GraphQLSchema(
            query=GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            subscription=GraphQLObjectType("S", {"a": GraphQLField(GraphQLString)}),
        )

        document = parse(
            """
            query Q { a }
            subscription S { a }
            """
        )

        class Data:
            a = "b"
            c = "d"

        result = execute_sync(schema, document, Data(), operation_name="S")
        assert result == ({"a": "b"}, None)

    def errors_when_using_original_execute_with_schemas_including_experimental_defer():
        schema = GraphQLSchema(
            query=GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            directives=[GraphQLDeferDirective],
        )
        document = parse("query Q { a }")

        with pytest.raises(GraphQLError) as exc_info:
            execute(schema, document)

        assert str(exc_info.value) == (
            "The provided schema unexpectedly contains experimental directives"
            " (@defer or @stream). These directives may only be utilized"
            " if experimental execution features are explicitly enabled."
        )

    def errors_when_using_original_execute_with_schemas_including_experimental_stream():
        schema = GraphQLSchema(
            query=GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            directives=[GraphQLStreamDirective],
        )
        document = parse("query Q { a }")

        with pytest.raises(GraphQLError) as exc_info:
            execute(schema, document)

        assert str(exc_info.value) == (
            "The provided schema unexpectedly contains experimental directives"
            " (@defer or @stream). These directives may only be utilized"
            " if experimental execution features are explicitly enabled."
        )

    def resolves_to_an_error_if_schema_does_not_support_operation():
        schema = GraphQLSchema(assume_valid=True)

        document = parse(
            """
            query Q { __typename }
            mutation M { __typename }
            subscription S { __typename }
            """
        )

        assert execute_sync(schema, document, operation_name="Q") == (
            None,
            [
                {
                    "message": "Schema is not configured to execute query operation.",
                    "locations": [(2, 13)],
                }
            ],
        )

        assert execute_sync(schema, document, operation_name="M") == (
            None,
            [
                {
                    "message": "Schema is not configured to execute"
                    " mutation operation.",
                    "locations": [(3, 13)],
                }
            ],
        )

        assert execute_sync(schema, document, operation_name="S") == (
            None,
            [
                {
                    "message": "Schema is not configured to execute"
                    " subscription operation.",
                    "locations": [(4, 13)],
                }
            ],
        )

    @pytest.mark.asyncio()
    async def correct_field_ordering_despite_execution_order():
        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type",
                {
                    "a": GraphQLField(GraphQLString),
                    "b": GraphQLField(GraphQLString),
                    "c": GraphQLField(GraphQLString),
                    "d": GraphQLField(GraphQLString),
                    "e": GraphQLField(GraphQLString),
                },
            )
        )

        document = parse("{ a, b, c, d, e}")

        # noinspection PyMethodMayBeStatic,PyMethodMayBeStatic
        class Data:
            def a(self, _info):
                return "a"

            async def b(self, _info):
                return "b"

            def c(self, _info):
                return "c"

            async def d(self, _info):
                return "d"

            def e(self, _info):
                return "e"

        awaitable_result = execute(schema, document, Data())
        assert isinstance(awaitable_result, Awaitable)
        result = await awaitable_result

        assert result == ({"a": "a", "b": "b", "c": "c", "d": "d", "e": "e"}, None)

    def avoids_recursion():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        document = parse(
            """
            query Q {
              a
              ...Frag
              ...Frag
            }

            fragment Frag on Type {
              a,
              ...Frag
            }
            """
        )

        class Data:
            a = "b"

        result = execute_sync(schema, document, Data(), operation_name="Q")

        assert result == ({"a": "b"}, None)

    def ignores_missing_sub_selections_on_fields():
        some_type = GraphQLObjectType("SomeType", {"b": GraphQLField(GraphQLString)})
        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"a": GraphQLField(some_type)})
        )
        document = parse("{ a }")
        root_value = {"a": {"b": "c"}}

        result = execute_sync(schema, document, root_value)
        assert result == ({"a": {}}, None)

    def does_not_include_illegal_fields_in_output():
        schema = GraphQLSchema(
            GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)})
        )

        document = parse("{ thisIsIllegalDoNotIncludeMe }")

        result = execute_sync(schema, document)

        assert result == ({}, None)

    def does_not_include_arguments_that_were_not_set():
        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type",
                {
                    "field": GraphQLField(
                        GraphQLString,
                        args={
                            "a": GraphQLArgument(GraphQLBoolean),
                            "b": GraphQLArgument(GraphQLBoolean),
                            "c": GraphQLArgument(GraphQLBoolean),
                            "d": GraphQLArgument(GraphQLInt),
                            "e": GraphQLArgument(GraphQLInt),
                        },
                        resolve=lambda _source, _info, **args: inspect(args),
                    )
                },
            )
        )

        document = parse("{ field(a: true, c: false, e: 0) }")

        assert execute_sync(schema, document) == (
            {"field": "{'a': True, 'c': False, 'e': 0}"},
            None,
        )

    @pytest.mark.asyncio()
    async def fails_when_is_type_of_check_is_not_met():
        class Special:
            value: str

            def __init__(self, value):
                self.value = value

        class NotSpecial:
            value: str

            def __init__(self, value):
                self.value = value

        def is_type_of_special(obj, _info):
            is_special = isinstance(obj, Special)
            if not _info.context["async"]:
                return is_special

            async def async_is_special():
                return is_special

            return async_is_special()

        SpecialType = GraphQLObjectType(
            "SpecialType",
            {"value": GraphQLField(GraphQLString)},
            is_type_of=is_type_of_special,
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query", {"specials": GraphQLField(GraphQLList(SpecialType))}
            )
        )

        document = parse("{ specials { value } }")
        root_value = {"specials": [Special("foo"), NotSpecial("bar")]}

        result = execute_sync(schema, document, root_value, {"async": False})
        assert not isinstance(result, Awaitable)
        assert result == (
            {"specials": [{"value": "foo"}, None]},
            [
                {
                    "message": "Expected value of type 'SpecialType' but got:"
                    " <NotSpecial instance>.",
                    "locations": [(1, 3)],
                    "path": ["specials", 1],
                }
            ],
        )

        async_result = execute(schema, document, root_value, {"async": True})
        assert isinstance(async_result, Awaitable)
        awaited_result = await async_result
        assert awaited_result == result

    def fails_when_serialize_of_custom_scalar_does_not_return_a_value():
        custom_scalar = GraphQLScalarType(
            "CustomScalar",
            serialize=lambda _value: Undefined,  # returns nothing
        )
        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "customScalar": GraphQLField(
                        custom_scalar, resolve=lambda *_args: "CUSTOM_VALUE"
                    )
                },
            )
        )

        result = execute_sync(schema, parse("{ customScalar }"))
        assert result == (
            {"customScalar": None},
            [
                {
                    "message": "Expected `CustomScalar.serialize('CUSTOM_VALUE')`"
                    " to return non-nullable value, returned: Undefined",
                    "locations": [(1, 3)],
                    "path": ["customScalar"],
                }
            ],
        )

    def executes_ignoring_invalid_non_executable_definitions():
        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)})
        )

        document = parse(
            """
            { foo }

            type Query { bar: String }
            """
        )

        result = execute_sync(schema, document)
        assert result == ({"foo": None}, None)

    def uses_a_custom_field_resolver():
        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)})
        )
        document = parse("{ foo }")

        def field_resolver(_source, info):
            # For the purposes of test, just return the name of the field!
            return info.field_name

        result = execute_sync(schema, document, field_resolver=field_resolver)
        assert result == ({"foo": "foo"}, None)

    def uses_a_custom_type_resolver():
        document = parse("{ foo { bar } }")

        foo_interface = GraphQLInterfaceType(
            "FooInterface", {"bar": GraphQLField(GraphQLString)}
        )

        foo_object = GraphQLObjectType(
            "FooObject", {"bar": GraphQLField(GraphQLString)}, [foo_interface]
        )

        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"foo": GraphQLField(foo_interface)}),
            types=[foo_object],
        )

        possible_types = None

        def type_resolver(_source, info, abstract_type):
            # Resolver should be able to figure out all possible types on its own
            nonlocal possible_types
            possible_types = info.schema.get_possible_types(abstract_type)
            return "FooObject"

        root_value = {"foo": {"bar": "bar"}}
        result = execute_sync(schema, document, root_value, type_resolver=type_resolver)

        assert result == ({"foo": {"bar": "bar"}}, None)
        assert possible_types == [foo_object]
