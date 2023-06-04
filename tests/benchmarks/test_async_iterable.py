import asyncio

from graphql import ExecutionResult, build_schema, execute, parse
from graphql.pyutils import is_awaitable


schema = build_schema("type Query { listField: [String] }")
document = parse("{ listField }")


class Data:
    # noinspection PyPep8Naming
    @staticmethod
    async def listField(info_):
        for index in range(1000):
            yield index


async def execute_async() -> ExecutionResult:
    result = execute(schema, document, Data())
    assert is_awaitable(result)
    return await result


def test_execute_async_iterable_list_field(benchmark):
    # Note: we are creating the async loop outside of the benchmark code so that
    # the setup is not included in the benchmark timings
    loop = asyncio.events.new_event_loop()
    asyncio.events.set_event_loop(loop)
    result = benchmark(lambda: loop.run_until_complete(execute_async()))
    asyncio.events.set_event_loop(None)
    loop.close()
    assert not result.errors
    assert result.data == {"listField": [str(index) for index in range(1000)]}
