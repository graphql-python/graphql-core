import asyncio
from json import dumps
from typing import cast

from pytest import raises, mark

from graphql.error import GraphQLError
from graphql.execution import execute, ExecutionContext
from graphql.language import parse, OperationDefinitionNode, FieldNode
from graphql.type import (
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLString,
    GraphQLField,
    GraphQLArgument,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLBoolean,
    GraphQLResolveInfo,
    ResponsePath,
)


def describe_execute_handles_basic_execution_tasks():

    # noinspection PyTypeChecker
    def throws_if_no_document_is_provided():
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        with raises(TypeError) as exc_info:
            assert execute(schema, None)

        assert str(exc_info.value) == "Must provide document"

    # noinspection PyTypeChecker
    def throws_if_no_schema_is_provided():
        with raises(TypeError) as exc_info:
            assert execute(schema=None, document=parse("{ field }"))

        assert str(exc_info.value) == "Expected None to be a GraphQL schema."

    def accepts_an_object_with_named_properties_as_arguments():
        doc = "query Example { a }"

        data = "rootValue"

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type",
                {
                    "a": GraphQLField(
                        GraphQLString, resolve=lambda root_value, *args: root_value
                    )
                },
            )
        )

        assert execute(schema, document=parse(doc), root_value=data) == (
            {"a": "rootValue"},
            None,
        )

    @mark.asyncio
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

            def pic(self, _info, size=50):
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

        doc = """
            query Example($size: Int) {
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

        ast = parse(doc)
        expected = (
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
                "deeper": GraphQLList(DataType),
            },
        )

        schema = GraphQLSchema(DataType)

        assert (
            await execute(
                schema,
                ast,
                Data(),
                variable_values={"size": 100},
                operation_name="Example",
            )
            == expected
        )

    def merges_parallel_fragments():
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

        assert execute(schema, ast) == (
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
        ast = parse("query ($var: String) { result: test }")

        infos = []

        def resolve(_obj, info):
            infos.append(info)

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Test", {"test": GraphQLField(GraphQLString, resolve=resolve)}
            )
        )

        root_value = {"root": "val"}

        execute(schema, ast, root_value, variable_values={"var": "abc"})

        assert len(infos) == 1
        operation = cast(OperationDefinitionNode, ast.definitions[0])
        field = cast(FieldNode, operation.selection_set.selections[0])
        assert infos[0] == GraphQLResolveInfo(
            field_name="test",
            field_nodes=[field],
            return_type=GraphQLString,
            parent_type=schema.query_type,
            path=ResponsePath(None, "result"),
            schema=schema,
            fragments={},
            root_value=root_value,
            operation=operation,
            variable_values={"var": "abc"},
            context=None,
        )

    def threads_root_value_context_correctly():
        doc = "query Example { a }"

        class Data:
            context_thing = "thing"

        resolved_values = []

        def resolve(obj, _info):
            resolved_values.append(obj)

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type", {"a": GraphQLField(GraphQLString, resolve=resolve)}
            )
        )

        execute(schema, parse(doc), Data())

        assert len(resolved_values) == 1
        assert resolved_values[0].context_thing == "thing"

    def correctly_threads_arguments():
        doc = """
            query Example {
              b(numArg: 123, stringArg: "foo")
            }
            """

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

        execute(schema, parse(doc))

        assert len(resolved_args) == 1
        assert resolved_args[0] == {"numArg": 123, "stringArg": "foo"}

    @mark.asyncio
    async def nulls_out_error_subtrees():
        doc = """{
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
            }"""

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
                raise Exception("Error getting asyncError")

            async def asyncRawError(self, _info):
                raise Exception("Error getting asyncRawError")

            async def asyncReturnError(self, _info):
                return GraphQLError("Error getting asyncReturnError")

            async def asyncReturnErrorWithExtensions(self, _info):
                return GraphQLError(
                    "Error getting asyncReturnErrorWithExtensions",
                    extensions={"foo": "bar"},
                )

        ast = parse(doc)

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

        assert await execute(schema, ast, Data()) == (
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
                    "locations": [(3, 15)],
                    "path": ["syncError"],
                },
                {
                    "message": "Error getting syncRawError",
                    "locations": [(4, 15)],
                    "path": ["syncRawError"],
                },
                {
                    "message": "Error getting syncReturnError",
                    "locations": [(5, 15)],
                    "path": ["syncReturnError"],
                },
                {
                    "message": "Error getting syncReturnErrorList1",
                    "locations": [(6, 15)],
                    "path": ["syncReturnErrorList", 1],
                },
                {
                    "message": "Error getting syncReturnErrorList3",
                    "locations": [(6, 15)],
                    "path": ["syncReturnErrorList", 3],
                },
                {
                    "message": "Error getting asyncError",
                    "locations": [(8, 15)],
                    "path": ["asyncError"],
                },
                {
                    "message": "Error getting asyncRawError",
                    "locations": [(9, 15)],
                    "path": ["asyncRawError"],
                },
                {
                    "message": "Error getting asyncReturnError",
                    "locations": [(10, 15)],
                    "path": ["asyncReturnError"],
                },
                {
                    "message": "Error getting asyncReturnErrorWithExtensions",
                    "locations": [(11, 15)],
                    "path": ["asyncReturnErrorWithExtensions"],
                    "extensions": {"foo": "bar"},
                },
            ],
        )

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

        query_type = GraphQLObjectType(
            "query", lambda: {"nullableA": GraphQLField(A, resolve=resolve_ok)}
        )
        schema = GraphQLSchema(query_type)

        query = """
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

        assert execute(schema, parse(query)) == (
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
        doc = "{ a }"

        class Data:
            a = "b"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        assert execute(schema, ast, Data()) == ({"a": "b"}, None)

    def uses_the_only_operation_if_no_operation_name_is_provided():
        doc = "query Example { a }"

        class Data:
            a = "b"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        assert execute(schema, ast, Data()) == ({"a": "b"}, None)

    def uses_the_named_operation_if_operation_name_is_provided():
        doc = "query Example { first: a } query OtherExample { second: a }"

        class Data:
            a = "b"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        assert execute(schema, ast, Data(), operation_name="OtherExample") == (
            {"second": "b"},
            None,
        )

    def provides_error_if_no_operation_is_provided():
        doc = "fragment Example on Type { a }"

        class Data:
            a = "b"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        assert execute(schema, ast, Data()) == (
            None,
            [{"message": "Must provide an operation."}],
        )

    def errors_if_no_operation_name_is_provided_with_multiple_operations():
        doc = "query Example { a } query OtherExample { a }"

        class Data:
            a = "b"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        assert execute(schema, ast, Data()) == (
            None,
            [
                {
                    "message": "Must provide operation name if query contains"
                    " multiple operations."
                }
            ],
        )

    def errors_if_unknown_operation_name_is_provided():
        doc = "query Example { a } query OtherExample { a }"
        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        assert execute(schema, ast, operation_name="UnknownExample") == (
            None,
            [{"message": "Unknown operation named 'UnknownExample'."}],
        )

    def uses_the_query_schema_for_queries():
        doc = "query Q { a } mutation M { c } subscription S { a }"

        class Data:
            a = "b"
            c = "d"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            GraphQLObjectType("M", {"c": GraphQLField(GraphQLString)}),
            GraphQLObjectType("S", {"a": GraphQLField(GraphQLString)}),
        )

        assert execute(schema, ast, Data(), operation_name="Q") == ({"a": "b"}, None)

    def uses_the_mutation_schema_for_mutations():
        doc = "query Q { a } mutation M { c }"

        class Data:
            a = "b"
            c = "d"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            GraphQLObjectType("M", {"c": GraphQLField(GraphQLString)}),
        )

        assert execute(schema, ast, Data(), operation_name="M") == ({"c": "d"}, None)

    def uses_the_subscription_schema_for_subscriptions():
        doc = "query Q { a } subscription S { a }"

        class Data:
            a = "b"
            c = "d"

        ast = parse(doc)
        schema = GraphQLSchema(
            query=GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            subscription=GraphQLObjectType("S", {"a": GraphQLField(GraphQLString)}),
        )

        assert execute(schema, ast, Data(), operation_name="S") == ({"a": "b"}, None)

    @mark.asyncio
    async def correct_field_ordering_despite_execution_order():
        doc = "{ a, b, c, d, e}"

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

        ast = parse(doc)
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

        result = await execute(schema, ast, Data())

        assert result == ({"a": "a", "b": "b", "c": "c", "d": "d", "e": "e"}, None)

        assert list(result.data) == ["a", "b", "c", "d", "e"]

    def avoids_recursion():
        doc = """
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

        class Data:
            a = "b"

        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Type", {"a": GraphQLField(GraphQLString)})
        )

        query_result = execute(schema, ast, Data(), operation_name="Q")

        assert query_result == ({"a": "b"}, None)

    def does_not_include_illegal_fields_in_output():
        doc = "mutation M { thisIsIllegalDoNotIncludeMe }"
        ast = parse(doc)
        schema = GraphQLSchema(
            GraphQLObjectType("Q", {"a": GraphQLField(GraphQLString)}),
            GraphQLObjectType("M", {"c": GraphQLField(GraphQLString)}),
        )

        mutation_result = execute(schema, ast)

        assert mutation_result == ({}, None)

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
                        resolve=lambda _source, _info, **args: args and dumps(args),
                    )
                },
            )
        )

        query = parse("{ field(a: true, c: false, e: 0) }")

        assert execute(schema, query) == (
            {"field": '{"a": true, "c": false, "e": 0}'},
            None,
        )

    def fails_when_an_is_type_of_check_is_not_met():
        class Special:
            # noinspection PyShadowingNames
            def __init__(self, value):
                self.value = value

        class NotSpecial:
            # noinspection PyShadowingNames
            def __init__(self, value):
                self.value = value

            def __repr__(self):
                return f"{self.__class__.__name__}({self.value!r})"

        SpecialType = GraphQLObjectType(
            "SpecialType",
            {"value": GraphQLField(GraphQLString)},
            is_type_of=lambda obj, _info: isinstance(obj, Special),
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "specials": GraphQLField(
                        GraphQLList(SpecialType),
                        resolve=lambda root_value, *_args: root_value["specials"],
                    )
                },
            )
        )

        query = parse("{ specials { value } }")
        value = {"specials": [Special("foo"), NotSpecial("bar")]}

        assert execute(schema, query, value) == (
            {"specials": [{"value": "foo"}, None]},
            [
                {
                    "message": "Expected value of type 'SpecialType' but got:"
                    " NotSpecial('bar').",
                    "locations": [(1, 3)],
                    "path": ["specials", 1],
                }
            ],
        )

    def executes_ignoring_invalid_non_executable_definitions():
        query = parse(
            """
            { foo }

            type Query { bar: String }
            """
        )

        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)})
        )

        assert execute(schema, query) == ({"foo": None}, None)


def describe_customize_execution():
    def uses_a_custom_field_resolver():
        query = parse("{ foo }")

        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)})
        )

        # For the purposes of test, just return the name of the field!
        def custom_resolver(_source, info, **_args):
            return info.field_name

        assert execute(schema, query, field_resolver=custom_resolver) == (
            {"foo": "foo"},
            None,
        )

    def uses_a_custom_execution_context_class():
        query = parse("{ foo }")

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {"foo": GraphQLField(GraphQLString, resolve=lambda *_args: "bar")},
            )
        )

        class TestExecutionContext(ExecutionContext):
            def resolve_field(self, parent_type, source, field_nodes, path):
                result = super().resolve_field(parent_type, source, field_nodes, path)
                return result * 2

        assert execute(schema, query, execution_context_class=TestExecutionContext) == (
            {"foo": "barbar"},
            None,
        )


def describe_parallel_execution():
    class Barrier:
        """Barrier that makes progress only after a certain number of waits."""

        def __init__(self, number: int) -> None:
            self.event = asyncio.Event()
            self.number = number

        async def wait(self) -> bool:
            self.number -= 1
            if not self.number:
                self.event.set()
            return await self.event.wait()

    @mark.asyncio
    async def resolve_fields_in_parallel():
        barrier = Barrier(2)

        async def resolve(*_args):
            return await barrier.wait()

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "foo": GraphQLField(GraphQLBoolean, resolve=resolve),
                    "bar": GraphQLField(GraphQLBoolean, resolve=resolve),
                },
            )
        )

        ast = parse("{foo, bar}")
        # raises TimeoutError if not parallel
        result = await asyncio.wait_for(execute(schema, ast), 1.0)

        assert result == ({"foo": True, "bar": True}, None)

    @mark.asyncio
    async def resolve_list_in_parallel():
        barrier = Barrier(2)

        async def resolve(*_args):
            return await barrier.wait()

        async def resolve_list(*args):
            return [resolve(*args), resolve(*args)]

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "foo": GraphQLField(
                        GraphQLList(GraphQLBoolean), resolve=resolve_list
                    )
                },
            )
        )

        ast = parse("{foo}")
        # raises TimeoutError if not parallel
        result = await asyncio.wait_for(execute(schema, ast), 1.0)

        assert result == ({"foo": [True, True]}, None)
