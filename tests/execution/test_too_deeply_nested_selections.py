import gc
import weakref
from functools import lru_cache
from importlib import import_module
from typing import Dict, List

from pytest import mark

from graphql.execution import (
    ExecutionResult,
    create_source_event_stream,
    execute,
    execute_sync,
    subscribe,
)
from graphql.language import parse
from graphql.utilities import build_schema

schema = build_schema("""
    type Query {
      name: String
      nested: Query
    }

    type Subscription {
      name: String
    }
    """)

# Far beyond the recursion limit on all interpreters.
DEPTH = 10_000

MESSAGE = "Selections are nested too deeply. Execution aborted."


@lru_cache(maxsize=None)
def _chain_document(root_type: str, selection: str = "...F{next}"):
    operation = "query" if root_type == "Query" else "subscription"
    chain = "\n".join(
        f"fragment F{i} on {root_type} {{ {selection.format(next=i + 1)} }}"
        for i in range(DEPTH)
    )
    last = f"fragment F{DEPTH} on {root_type} {{ name }}"
    return parse(f"{operation} {{ ...F0 }}\n{chain}\n{last}", no_location=True)


def _assert_nested_too_deeply(result: object) -> None:
    assert isinstance(result, ExecutionResult)
    assert result.data is None
    assert result.errors
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.message == MESSAGE
    assert error.__context__ is None
    assert error.__cause__ is None


def describe_too_deeply_nested_selections_at_the_root():
    def execute_sync_returns_a_result_with_the_error():
        _assert_nested_too_deeply(execute_sync(schema, _chain_document("Query")))

    def execute_returns_a_result_with_the_error():
        _assert_nested_too_deeply(execute(schema, _chain_document("Query")))

    @mark.asyncio
    async def subscribe_returns_a_result_with_the_error():
        _assert_nested_too_deeply(
            await subscribe(schema, _chain_document("Subscription"))
        )

    @mark.asyncio
    async def create_source_event_stream_returns_a_result_with_the_error():
        result = await create_source_event_stream(
            schema, _chain_document("Subscription")
        )
        _assert_nested_too_deeply(result)
        assert isinstance(result, ExecutionResult)
        assert result.errors
        assert result.errors[0].__traceback__ is None

    def still_executes_a_depth_that_fits():
        document = parse(
            "{ ...F0 } "
            + " ".join(f"fragment F{i} on Query {{ ...F{i + 1} }}" for i in range(100))
            + " fragment F100 on Query { name }"
        )
        assert execute_sync(schema, document, {"name": "x"}) == ({"name": "x"}, None)

    def reports_a_too_deep_chain_inside_a_field_as_a_field_error():
        document = _chain_document("Query", "nested {{ ...F{next} }}")
        root: Dict = {"name": "x"}
        root["nested"] = root
        result = execute_sync(schema, document, root)
        assert result.errors
        assert result.errors[0].message != MESSAGE
        assert isinstance(result.data, dict)

    def _track_collect_fields_impl(monkeypatch) -> List[weakref.ref]:
        refs: List[weakref.ref] = []
        module = import_module("graphql.execution.collect_fields")
        collect_fields_impl = module.collect_fields_impl

        class Tracked:
            pass

        def tracked_collect_fields_impl(*args, **kwargs):
            tracked = Tracked()
            refs.append(weakref.ref(tracked))
            return collect_fields_impl(*args, **kwargs)

        monkeypatch.setattr(module, "collect_fields_impl", tracked_collect_fields_impl)
        return refs

    def execute_does_not_keep_the_frames_of_the_recursion_alive(monkeypatch):
        refs = _track_collect_fields_impl(monkeypatch)
        result = execute_sync(schema, _chain_document("Query"))
        gc.collect()
        assert len(refs) > 10
        assert all(ref() is None for ref in refs)
        _assert_nested_too_deeply(result)

    @mark.asyncio
    async def subscribe_does_not_keep_the_frames_of_the_recursion_alive(monkeypatch):
        refs = _track_collect_fields_impl(monkeypatch)
        result = await subscribe(schema, _chain_document("Subscription"))
        gc.collect()
        assert len(refs) > 10
        assert all(ref() is None for ref in refs)
        _assert_nested_too_deeply(result)
