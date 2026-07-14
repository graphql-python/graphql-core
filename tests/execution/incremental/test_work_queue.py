from __future__ import annotations

from asyncio import CancelledError, Event, Future, ensure_future, sleep
from typing import TYPE_CHECKING, Any

import pytest

from graphql.execution.incremental import Computation
from graphql.execution.incremental.work_queue import (
    GroupFailureEvent,
    GroupSuccessEvent,
    GroupValuesEvent,
    StreamFailureEvent,
    StreamQueue,
    StreamSuccessEvent,
    StreamValuesEvent,
    Work,
    WorkQueue,
    WorkQueueTerminationEvent,
    WorkResult,
    WorkTask,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

pytestmark = pytest.mark.anyio


class Spy:
    """Wrap a function, counting its calls."""

    def __init__(self, fn: Callable[..., Any]) -> None:
        self.fn = fn
        self.call_count = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.call_count += 1
        return self.fn(*args, **kwargs)


class Group:
    """A test group with an optional parent and a name for debugging."""

    def __init__(self, parent: Group | None = None, name: str = "group") -> None:
        self.parent = parent
        self.name = name

    def __repr__(self) -> str:
        return f"<Group {self.name}>"


class FakeStreamQueue:
    """A fake stream queue yielding predefined batches of stream items."""

    def __init__(
        self,
        item_batches: Sequence[Sequence[WorkResult]] = (),
        error: BaseException | None = None,
        on_abort: Callable[[BaseException | None], Awaitable[None] | None]
        | None = None,
        never_stops: bool = False,
    ) -> None:
        self.item_batches = item_batches
        self.error = error
        self.on_abort = on_abort
        self.never_stops = never_stops
        self.aborted_with: list[BaseException | None] = []

    async def batches(self) -> AsyncIterator[Sequence[WorkResult]]:
        for item_batch in self.item_batches:
            yield item_batch
        if self.error:
            raise self.error
        if self.never_stops:
            await Event().wait()

    def abort(self, reason: BaseException | None = None) -> Awaitable[None] | None:
        self.aborted_with.append(reason)
        if self.on_abort:
            return self.on_abort(reason)
        return None


class Stream:
    """A test stream with a name for debugging."""

    def __init__(self, queue: FakeStreamQueue, name: str = "stream") -> None:
        self.queue: StreamQueue = queue
        self.name = name

    def __repr__(self) -> str:
        return f"<Stream {self.name}>"


def make_task(
    groups: Sequence[Group],
    value_or_fn: Any,
    work: Work | None = None,
) -> WorkTask:
    if callable(value_or_fn):
        return WorkTask(groups, Computation(value_or_fn))
    return WorkTask(groups, Computation(lambda: WorkResult(value_or_fn, work)))


def stream_from(
    items: Sequence[WorkResult],
    error: BaseException | None = None,
    batched: bool = False,
    name: str = "stream",
) -> Stream:
    item_batches = [items] if batched else [[item] for item in items]
    return Stream(FakeStreamQueue(item_batches, error=error), name)


async def collect_work_run(work: Work) -> tuple[Any, Any, list[Any]]:
    events: list[Any] = []
    work_queue = WorkQueue(work)
    async for batch in work_queue.events():
        events.extend(batch)
    return work_queue.initial_groups, work_queue.initial_streams, events


def describe_work_queue():
    async def runs_parent_and_child_groups_sequentially():
        root = Group(name="root")
        child = Group(root, name="child")

        child_ran_spy = Spy(lambda: WorkResult("child"))
        child_task = make_task([child], child_ran_spy)
        root_task = make_task([root], "root", Work(groups=[child], tasks=[child_task]))

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[root], tasks=[root_task])
        )

        assert initial_groups == [root]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(root, ["root"]),
            GroupSuccessEvent(root, [child], []),
            GroupValuesEvent(child, ["child"]),
            GroupSuccessEvent(child, [], []),
            WorkQueueTerminationEvent(),
        ]
        assert child_ran_spy.call_count == 1

    async def can_handle_child_groups_passed_prior_to_parents():
        root = Group(name="root")
        child = Group(root, name="child")

        child_task = make_task([child], "child", Work())
        root_task = make_task([root], "root", Work())

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[child, root], tasks=[root_task, child_task])
        )

        assert initial_groups == [root]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(root, ["root"]),
            GroupSuccessEvent(root, [child], []),
            GroupValuesEvent(child, ["child"]),
            GroupSuccessEvent(child, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def propagates_task_failures_and_skips_descendant_groups():
        root = Group(name="root")
        child = Group(root, name="child")
        grandchild = Group(child, name="grandchild")
        grandchild_ran_spy = Spy(lambda: WorkResult("grandchild"))
        grandchild_task = make_task([grandchild], grandchild_ran_spy)

        boom = RuntimeError("boom")

        def fail() -> WorkResult:
            raise boom

        child_ran_spy = Spy(fail)
        failing_child_task = make_task([child], child_ran_spy)

        root_task = make_task(
            [root],
            "root",
            Work(
                groups=[child, grandchild], tasks=[failing_child_task, grandchild_task]
            ),
        )

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[root], tasks=[root_task])
        )

        assert initial_groups == [root]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(root, ["root"]),
            GroupSuccessEvent(root, [child], []),
            GroupFailureEvent(child, boom),
            WorkQueueTerminationEvent(),
        ]
        assert grandchild_ran_spy.call_count == 0
        assert child_ran_spy.call_count == 1

    async def integrates_work_object_returned_by_task():
        root = Group(name="root")
        child = Group(root, name="child")

        child_task = make_task([child], lambda: WorkResult("child"))
        root_task = make_task(
            [root],
            lambda: WorkResult("root", Work(groups=[child], tasks=[child_task])),
        )

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[root], tasks=[root_task])
        )

        assert initial_groups == [root]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(root, ["root"]),
            GroupSuccessEvent(root, [child], []),
            GroupValuesEvent(child, ["child"]),
            GroupSuccessEvent(child, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def purges_shared_tasks_so_sibling_groups_finish_without_rerunning_work():
        group_a = Group(name="a")
        group_b = Group(name="b")

        shared_task = make_task([group_a, group_b], "shared")

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group_a, group_b], tasks=[shared_task])
        )

        assert initial_groups == [group_a, group_b]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(group_a, ["shared"]),
            GroupSuccessEvent(group_a, [], []),
            GroupSuccessEvent(group_b, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def ignores_task_emitted_groups_without_a_valid_parent():
        root = Group(name="root")
        orphan_group = Group(name="orphan")

        task = make_task([root], "root", Work(groups=[orphan_group]))

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[root], tasks=[task])
        )

        assert initial_groups == [root]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(root, ["root"]),
            GroupSuccessEvent(root, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def skips_child_groups_with_only_completed_tasks_when_parent_finishes_later():
        parent1 = Group(name="parent1")
        parent2 = Group(name="parent2")
        child1 = Group(parent1, name="child1")
        child2 = Group(parent2, name="child2")

        parent1_task = make_task([parent1], "parent1")

        async def slow_parent2() -> WorkResult:
            await sleep(0)
            return WorkResult("parent2-slow")

        slow_parent2_task = make_task([parent2], slow_parent2)
        shared_child_task = make_task([child1, child2], "child-shared")

        async def slow_child1_follow_up() -> WorkResult:
            await sleep(0)
            await sleep(0)
            await sleep(0)
            return WorkResult("child1-slow")

        slow_child1_follow_up_task = make_task([child1], slow_child1_follow_up)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[parent1, parent2, child1, child2],
                tasks=[
                    parent1_task,
                    slow_parent2_task,
                    shared_child_task,
                    slow_child1_follow_up_task,
                ],
            )
        )

        assert initial_groups == [parent1, parent2]
        assert initial_streams == []
        # Note: the upstream test expects these events for `child2`, but its
        # deep equality cannot distinguish the structurally identical groups;
        # the events are actually emitted for `child1` (`child2` is pruned).
        assert events == [
            GroupValuesEvent(parent1, ["parent1"]),
            GroupSuccessEvent(parent1, [child1], []),
            GroupValuesEvent(parent2, ["parent2-slow"]),
            GroupSuccessEvent(parent2, [], []),
            GroupValuesEvent(child1, ["child-shared", "child1-slow"]),
            GroupSuccessEvent(child1, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def skips_promoted_child_groups_that_already_completed_shared_tasks():
        parent = Group(name="parent")
        child = Group(parent, name="child")

        async def slow_parent() -> WorkResult:
            await sleep(0)
            await sleep(0)
            return WorkResult("parent")

        parent_task = make_task([parent], slow_parent)
        shared_task = make_task([parent, child], "shared")

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[parent, child], tasks=[parent_task, shared_task])
        )

        assert initial_groups == [parent]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(parent, ["parent", "shared"]),
            GroupSuccessEvent(parent, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def skips_child_groups_with_shared_tasks_completed_by_a_parent():
        parent = Group(name="parent")
        child = Group(parent, name="child")
        other_root = Group(name="other_root")

        async def slow_parent() -> WorkResult:
            await sleep(0)
            await sleep(0)
            return WorkResult("parent")

        parent_task = make_task([parent], slow_parent)
        shared_task = make_task([child, other_root], "shared")

        async def slow_other_root() -> WorkResult:
            await sleep(0)
            await sleep(0)
            await sleep(0)
            await sleep(0)
            return WorkResult("other-root")

        slow_other_root_task = make_task([other_root], slow_other_root)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[parent, other_root, child],
                tasks=[parent_task, shared_task, slow_other_root_task],
            )
        )

        assert initial_groups == [parent, other_root]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(parent, ["parent"]),
            GroupSuccessEvent(parent, [], []),
            GroupValuesEvent(other_root, ["shared", "other-root"]),
            GroupSuccessEvent(other_root, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def does_not_promote_child_groups_that_only_share_work_with_the_parent():
        parent = Group(name="parent")
        child = Group(parent, name="child")

        shared_task = make_task([parent, child], "shared")

        async def slow_parent_only() -> WorkResult:
            await sleep(0)
            return WorkResult("parent-only")

        parent_only_task = make_task([parent], slow_parent_only)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[parent, child], tasks=[shared_task, parent_only_task])
        )

        assert initial_groups == [parent]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(parent, ["shared", "parent-only"]),
            GroupSuccessEvent(parent, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def ignores_work_returned_by_tasks_whose_groups_already_failed():
        group = Group(name="group")
        late_group = Group(name="late_group")

        fail_early = RuntimeError("fail early")

        def fail() -> WorkResult:
            raise fail_early

        failing = make_task([group], fail)

        async def slow() -> WorkResult:
            await sleep(0)
            return WorkResult("late", Work(groups=[late_group]))

        slow_task = make_task([group], slow)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group], tasks=[failing, slow_task])
        )

        assert initial_groups == [group]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(group, fail_early),
            WorkQueueTerminationEvent(),
        ]

    async def defers_task_emitted_streams_until_the_parent_group_succeeds():
        parent = Group(name="parent")
        deferred_stream = stream_from([WorkResult(7)], name="deferred")

        parent_task = make_task([parent], "parent", Work(streams=[deferred_stream]))

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[parent], tasks=[parent_task])
        )

        assert initial_groups == [parent]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(parent, ["parent"]),
            GroupSuccessEvent(parent, [], [deferred_stream]),
            StreamValuesEvent(deferred_stream, [7], [], []),
            StreamSuccessEvent(deferred_stream),
            WorkQueueTerminationEvent(),
        ]

    async def only_promotes_shared_streams_after_all_parent_groups_finish():
        group_a = Group(name="a")
        group_b = Group(name="b")
        shared_stream = stream_from([WorkResult(1)], name="shared")

        shared_task = make_task(
            [group_a, group_b], "shared", Work(streams=[shared_stream])
        )

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group_a, group_b], tasks=[shared_task])
        )

        assert initial_groups == [group_a, group_b]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(group_a, ["shared"]),
            GroupSuccessEvent(group_a, [], [shared_stream]),
            GroupSuccessEvent(group_b, [], []),
            StreamValuesEvent(shared_stream, [1], [], []),
            StreamSuccessEvent(shared_stream),
            WorkQueueTerminationEvent(),
        ]

    async def starts_a_shared_stream_once_even_when_the_second_parent_is_slower():
        group_a = Group(name="a")
        group_b = Group(name="b")
        shared_stream = stream_from([WorkResult(5)], name="shared")

        shared_task = make_task(
            [group_a, group_b], "shared", Work(streams=[shared_stream])
        )
        fast_task_a = make_task([group_a], "A-only")

        async def slow_b() -> WorkResult:
            await sleep(0)
            await sleep(0)
            await sleep(0)
            return WorkResult("B-slow")

        slow_task_b = make_task([group_b], slow_b)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[group_a, group_b], tasks=[shared_task, fast_task_a, slow_task_b]
            )
        )

        assert initial_groups == [group_a, group_b]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(group_a, ["shared", "A-only"]),
            GroupSuccessEvent(group_a, [], [shared_stream]),
            StreamValuesEvent(shared_stream, [5], [], []),
            StreamSuccessEvent(shared_stream),
            GroupValuesEvent(group_b, ["B-slow"]),
            GroupSuccessEvent(group_b, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def does_not_promote_a_child_stream_if_the_parent_fails():
        group = Group(name="group")
        stream = stream_from([WorkResult(99)])

        task = make_task([group], "task", Work(streams=[stream]))
        boom = RuntimeError("boom")

        def fail() -> WorkResult:
            raise boom

        failing_task = make_task([group], fail)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group], tasks=[task, failing_task])
        )

        assert initial_groups == [group]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(group, boom),
            WorkQueueTerminationEvent(),
        ]

    async def promotes_a_stream_with_multiple_parents_when_only_a_single_parent_fails():
        group_a = Group(name="a")
        group_b = Group(name="b")
        shared_stream = stream_from([WorkResult(99)], name="shared")

        shared_task = make_task(
            [group_a, group_b], "shared", Work(streams=[shared_stream])
        )
        boom = RuntimeError("boom")

        def fail() -> WorkResult:
            raise boom

        failing_task = make_task([group_a], fail)

        async def slow_b() -> WorkResult:
            await sleep(0)
            return WorkResult("B-resolved")

        slow_task_b = make_task([group_b], slow_b)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[group_a, group_b],
                tasks=[shared_task, failing_task, slow_task_b],
            )
        )

        assert initial_groups == [group_a, group_b]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(group_a, boom),
            GroupValuesEvent(group_b, ["shared", "B-resolved"]),
            GroupSuccessEvent(group_b, [], [shared_stream]),
            StreamValuesEvent(shared_stream, [99], [], []),
            StreamSuccessEvent(shared_stream),
            WorkQueueTerminationEvent(),
        ]

    async def emits_stream_items_followed_by_success():
        stream = stream_from([WorkResult(1), WorkResult(2), WorkResult(3)])

        initial_groups, initial_streams, events = await collect_work_run(
            Work(streams=[stream])
        )

        assert initial_groups == []
        assert initial_streams == [stream]
        assert events == [
            StreamValuesEvent(stream, [1], [], []),
            StreamValuesEvent(stream, [2], [], []),
            StreamValuesEvent(stream, [3], [], []),
            StreamSuccessEvent(stream),
            WorkQueueTerminationEvent(),
        ]

    async def handles_batched_stream_items():
        spawned = Group(name="spawned")
        spawned_task = make_task([spawned], "spawned-from-stream")

        stream = stream_from(
            [
                WorkResult(1),
                WorkResult(2, Work(groups=[spawned], tasks=[spawned_task])),
            ],
            batched=True,
        )

        initial_groups, initial_streams, events = await collect_work_run(
            Work(streams=[stream])
        )

        assert initial_groups == []
        assert initial_streams == [stream]
        assert events == [
            StreamValuesEvent(stream, [1, 2], [spawned], []),
            GroupValuesEvent(spawned, ["spawned-from-stream"]),
            GroupSuccessEvent(spawned, [], []),
            StreamSuccessEvent(stream),
            WorkQueueTerminationEvent(),
        ]

    async def emits_stream_failure_when_the_iterator_throws():
        broken_stream_error = RuntimeError("broken stream")
        failing_stream = stream_from([WorkResult(42)], error=broken_stream_error)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(streams=[failing_stream])
        )

        assert initial_groups == []
        assert initial_streams == [failing_stream]
        assert events == [
            StreamValuesEvent(failing_stream, [42], [], []),
            StreamFailureEvent(failing_stream, broken_stream_error),
            WorkQueueTerminationEvent(),
        ]

    async def emits_stream_success_in_a_later_payload_when_stream_is_slow_to_stop():
        proceed: Future[None] = Future()

        class SlowToStopQueue(FakeStreamQueue):
            async def batches(self) -> AsyncIterator[Sequence[WorkResult]]:
                yield [WorkResult(1)]
                await proceed

        stream = Stream(SlowToStopQueue())

        events: list[Any] = []
        work_queue = WorkQueue(Work(streams=[stream]))
        iterator = work_queue.events()
        events.extend(await anext(iterator))
        proceed.set_result(None)
        async for batch in iterator:
            events.extend(batch)

        assert events == [
            StreamValuesEvent(stream, [1], [], []),
            StreamSuccessEvent(stream),
            WorkQueueTerminationEvent(),
        ]

    async def emits_late_root_groups_and_streams_triggered_from_stream():
        initial = Group(name="initial")
        late_group = Group(name="late_group")

        late_task = make_task([late_group], "late")
        secondary_stream = stream_from([WorkResult(9)], name="secondary")
        trigger_stream = stream_from(
            [
                WorkResult(
                    0,
                    Work(
                        groups=[late_group],
                        tasks=[late_task],
                        streams=[secondary_stream],
                    ),
                )
            ],
            name="trigger",
        )

        initial_task = make_task([initial], "initial")

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[initial], tasks=[initial_task], streams=[trigger_stream])
        )

        assert initial_groups == [initial]
        assert initial_streams == [trigger_stream]
        assert events == [
            GroupValuesEvent(initial, ["initial"]),
            GroupSuccessEvent(initial, [], []),
            StreamValuesEvent(trigger_stream, [0], [late_group], [secondary_stream]),
            GroupValuesEvent(late_group, ["late"]),
            GroupSuccessEvent(late_group, [], []),
            StreamValuesEvent(secondary_stream, [9], [], []),
            StreamSuccessEvent(trigger_stream),
            StreamSuccessEvent(secondary_stream),
            WorkQueueTerminationEvent(),
        ]

    async def handles_tasks_that_are_started_manually_before_they_complete():
        group = Group(name="group")

        async def primed() -> WorkResult:
            await sleep(0)
            return WorkResult("primed")

        computation: Computation[WorkResult] = Computation(primed)
        primed_task = WorkTask([group], computation)

        computation.prime()

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group], tasks=[primed_task])
        )

        assert initial_groups == [group]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(group, ["primed"]),
            GroupSuccessEvent(group, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def propagates_failures_for_tasks_started_manually():
        group = Group(name="group")
        primed_failure = RuntimeError("primed failure")

        async def primed() -> WorkResult:
            await sleep(0)
            raise primed_failure

        computation: Computation[WorkResult] = Computation(primed)
        primed_task = WorkTask([group], computation)

        computation.prime()

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group], tasks=[primed_task])
        )

        assert initial_groups == [group]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(group, primed_failure),
            WorkQueueTerminationEvent(),
        ]

    async def skips_groups_with_no_tasks_and_promotes_descendants():
        root = Group(name="root")
        empty_parent = Group(root, name="empty_parent")
        leaf = Group(empty_parent, name="leaf")

        leaf_task = make_task([leaf], "leaf")

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[root, empty_parent, leaf], tasks=[leaf_task])
        )

        assert initial_groups == [leaf]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(leaf, ["leaf"]),
            GroupSuccessEvent(leaf, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def handles_tasks_that_are_already_settled_before_being_queued():
        group = Group(name="group")
        computation: Computation[WorkResult] = Computation(lambda: WorkResult("eager"))
        eager_task = WorkTask([group], computation)

        computation.prime()

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group], tasks=[eager_task])
        )

        assert initial_groups == [group]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(group, ["eager"]),
            GroupSuccessEvent(group, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def cancels_nested_work_when_the_work_queue_is_cancelled():
        root = Group(name="root")
        child = Group(root, name="child")
        root_stream = stream_from([WorkResult(1)], name="root_stream")

        child_stream_cancelled = False
        child_stream_cleanup: Future[None] = Future()

        def cancel_child_stream(_reason: BaseException | None) -> Future[None]:
            nonlocal child_stream_cancelled
            child_stream_cancelled = True
            return child_stream_cleanup

        child_stream = Stream(
            FakeStreamQueue(never_stops=True, on_abort=cancel_child_stream),
            name="child_stream",
        )

        child_task_cancelled = False
        child_task_cleanup: Future[None] = Future()

        def cancel_child_task(_reason: BaseException | None) -> Future[None]:
            nonlocal child_task_cancelled
            child_task_cancelled = True
            return child_task_cleanup

        async def never() -> WorkResult:
            await Event().wait()
            raise AssertionError("never resolves")

        child_task = WorkTask([root], Computation(never, cancel_child_task))

        root_task = make_task(
            [root], lambda: WorkResult("root", Work(streams=[child_stream]))
        )

        work_queue = WorkQueue(
            Work(
                groups=[root, child],
                tasks=[root_task, child_task],
                streams=[root_stream],
            )
        )

        assert work_queue.initial_groups == [root]
        assert work_queue.initial_streams == [root_stream]
        iterator = work_queue.events()
        assert await anext(iterator) == [
            StreamValuesEvent(root_stream, [1], [], []),
        ]

        cancelled = ensure_future(work_queue.cancel())
        await sleep(0)
        assert child_task_cancelled is True
        assert child_stream_cancelled is True
        assert not cancelled.done()  # cancellation awaits async cleanup

        child_stream_cleanup.set_result(None)
        child_task_cleanup.set_result(None)
        await cancelled

        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

    async def forwards_cancellation_reason_when_cancelling_nested_work():
        root = Group(name="root")
        root_stream = stream_from([WorkResult(1)], name="root_stream")
        abort_reason = RuntimeError("Abort nested work")

        child_stream_cancel_reasons: list[BaseException | None] = []
        child_stream = Stream(
            FakeStreamQueue(
                never_stops=True, on_abort=child_stream_cancel_reasons.append
            ),
            name="child_stream",
        )

        child_task_cancel_reasons: list[BaseException | None] = []

        async def never() -> WorkResult:
            await Event().wait()
            raise AssertionError("never resolves")

        child_task = WorkTask(
            [root], Computation(never, child_task_cancel_reasons.append)
        )

        root_task = make_task(
            [root], lambda: WorkResult("root", Work(streams=[child_stream]))
        )

        work_queue = WorkQueue(
            Work(groups=[root], tasks=[root_task, child_task], streams=[root_stream])
        )

        iterator = work_queue.events()
        await anext(iterator)

        await work_queue.cancel(abort_reason)

        assert child_task_cancel_reasons == [abort_reason]
        assert child_stream_cancel_reasons == [abort_reason]

    async def ends_iteration_when_cancelled_while_waiting_for_events():
        group = Group(name="group")

        async def never() -> WorkResult:
            await Event().wait()
            raise AssertionError("never resolves")

        never_task = make_task([group], never)
        work_queue = WorkQueue(Work(groups=[group], tasks=[never_task]))

        events: list[Any] = []

        async def consume() -> None:
            async for batch in work_queue.events():
                events.extend(batch)  # pragma: no cover

        consumer = ensure_future(consume())
        await sleep(0)  # park the consumer on the event channel
        await work_queue.cancel()
        await consumer  # the stop sentinel ends the iteration

        assert events == []

    async def aborts_unstarted_tasks_of_pending_child_groups_when_cancelled():
        parent = Group(name="parent")
        child = Group(parent, name="child")

        async def never() -> WorkResult:
            await Event().wait()
            raise AssertionError("never resolves")

        never_task = make_task([parent], never)
        run_spy = Spy(lambda: WorkResult("child"))
        lazy_child_task = make_task([child], run_spy)

        work_queue = WorkQueue(
            Work(groups=[parent, child], tasks=[never_task, lazy_child_task])
        )
        iterator = work_queue.events()
        consumer = ensure_future(anext(iterator))
        await sleep(0)
        await work_queue.cancel()
        with pytest.raises(StopAsyncIteration):
            await consumer

        assert run_spy.call_count == 0  # poisoned before running
        with pytest.raises(CancelledError):
            lazy_child_task.computation.result()

    async def ignores_tasks_and_streams_emitted_for_already_failed_groups():
        group = Group(name="group")

        fail_early = RuntimeError("fail early")

        def fail() -> WorkResult:
            raise fail_early

        failing = make_task([group], fail)

        run_spy = Spy(lambda: WorkResult("more"))
        late_stream = stream_from([WorkResult(1)], name="late")

        async def slow() -> WorkResult:
            await sleep(0)
            return WorkResult(
                "late",
                Work(tasks=[make_task([group], run_spy)], streams=[late_stream]),
            )

        slow_task = make_task([group], slow)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group], tasks=[failing, slow_task])
        )

        assert initial_groups == [group]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(group, fail_early),
            WorkQueueTerminationEvent(),
        ]
        assert run_spy.call_count == 0

    async def promotes_multiple_streams_from_the_same_task_together():
        parent = Group(name="parent")
        stream1 = stream_from([WorkResult(1)], name="stream1")
        stream2 = stream_from([WorkResult(2)], name="stream2")

        parent_task = make_task([parent], "parent", Work(streams=[stream1, stream2]))

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[parent], tasks=[parent_task])
        )

        assert initial_groups == [parent]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(parent, ["parent"]),
            GroupSuccessEvent(parent, [], [stream1, stream2]),
            StreamValuesEvent(stream1, [1], [], []),
            StreamValuesEvent(stream2, [2], [], []),
            StreamSuccessEvent(stream1),
            StreamSuccessEvent(stream2),
            WorkQueueTerminationEvent(),
        ]

    async def finishes_shared_tasks_that_settle_after_one_of_their_groups_failed():
        group_a = Group(name="a")
        group_b = Group(name="b")

        boom = RuntimeError("boom")

        def fail() -> WorkResult:
            raise boom

        failing_task = make_task([group_a], fail)

        async def slow_shared() -> WorkResult:
            await sleep(0)
            await sleep(0)
            return WorkResult("shared-slow")

        slow_shared_task = make_task([group_a, group_b], slow_shared)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group_a, group_b], tasks=[failing_task, slow_shared_task])
        )

        assert initial_groups == [group_a, group_b]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(group_a, boom),
            GroupValuesEvent(group_b, ["shared-slow"]),
            GroupSuccessEvent(group_b, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def fails_all_pending_groups_when_a_shared_task_fails():
        group_a = Group(name="a")
        group_b = Group(name="b")

        boom = RuntimeError("boom")

        def fail_a() -> WorkResult:
            raise boom

        failing_task_a = make_task([group_a], fail_a)

        async def slow_fail_shared() -> WorkResult:
            await sleep(0)
            raise boom

        slow_failing_shared_task = make_task([group_a, group_b], slow_fail_shared)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[group_a, group_b],
                tasks=[failing_task_a, slow_failing_shared_task],
            )
        )

        assert initial_groups == [group_a, group_b]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(group_a, boom),
            GroupFailureEvent(group_b, boom),
            WorkQueueTerminationEvent(),
        ]

    async def removes_failed_subtrees_with_already_removed_children():
        parent = Group(name="parent")
        child_a = Group(parent, name="child_a")
        child_b = Group(parent, name="child_b")

        boom = RuntimeError("boom")

        def fail() -> WorkResult:
            raise boom

        failing_shared_task = make_task([child_a, parent], fail)
        child_b_ran_spy = Spy(lambda: WorkResult("child_b"))
        child_b_task = make_task([child_b], child_b_ran_spy)

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[parent, child_a, child_b],
                tasks=[failing_shared_task, child_b_task],
            )
        )

        assert initial_groups == [parent]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(child_a, boom),
            GroupFailureEvent(parent, boom),
            WorkQueueTerminationEvent(),
        ]
        assert child_b_ran_spy.call_count == 0

    async def integrates_late_work_referencing_dead_groups_gracefully():
        dead1 = Group(name="dead1")
        dead2 = Group(name="dead2")
        alive = Group(name="alive")

        boom1 = RuntimeError("boom1")
        boom2 = RuntimeError("boom2")

        def fail1() -> WorkResult:
            raise boom1

        def fail2() -> WorkResult:
            raise boom2

        run_spy = Spy(lambda: WorkResult("never"))
        late_stream = stream_from([WorkResult(1)], name="late")

        async def slow_dead() -> WorkResult:
            await sleep(0)
            await sleep(0)
            return WorkResult(
                "late",
                Work(
                    groups=[Group(dead1, name="child_of_dead")],
                    tasks=[make_task([dead1, dead2], run_spy)],
                    streams=[late_stream],
                ),
            )

        async def slow_alive() -> WorkResult:
            await sleep(0)
            await sleep(0)
            await sleep(0)
            await sleep(0)
            return WorkResult("alive")

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[dead1, dead2, alive],
                tasks=[
                    make_task([dead1], fail1),
                    make_task([dead2], fail2),
                    make_task([dead1], slow_dead),
                    make_task([alive], slow_alive),
                ],
            )
        )

        assert initial_groups == [dead1, dead2, alive]
        assert initial_streams == []
        assert events == [
            GroupFailureEvent(dead1, boom1),
            GroupFailureEvent(dead2, boom2),
            GroupValuesEvent(alive, ["alive"]),
            GroupSuccessEvent(alive, [], []),
            WorkQueueTerminationEvent(),
        ]
        assert run_spy.call_count == 0

    async def starts_tasks_added_to_a_pending_root_group_immediately():
        group = Group(name="group")

        async def slow() -> WorkResult:
            await sleep(0)
            await sleep(0)
            return WorkResult("slow")

        extra_task = make_task([group], "extra")
        stream = stream_from([WorkResult(1, Work(tasks=[extra_task]))])

        initial_groups, initial_streams, events = await collect_work_run(
            Work(groups=[group], tasks=[make_task([group], slow)], streams=[stream])
        )

        assert initial_groups == [group]
        assert initial_streams == [stream]
        assert events == [
            StreamValuesEvent(stream, [1], [], []),
            StreamSuccessEvent(stream),
            GroupValuesEvent(group, ["slow", "extra"]),
            GroupSuccessEvent(group, [], []),
            WorkQueueTerminationEvent(),
        ]

    async def prunes_duplicate_empty_child_group_entries():
        group = Group(name="group")
        child = Group(group, name="child")

        async def slow_two() -> WorkResult:
            await sleep(0)
            return WorkResult("two", Work(groups=[child]))

        initial_groups, initial_streams, events = await collect_work_run(
            Work(
                groups=[group],
                tasks=[
                    make_task([group], "one", Work(groups=[child])),
                    make_task([group], slow_two),
                ],
            )
        )

        assert initial_groups == [group]
        assert initial_streams == []
        assert events == [
            GroupValuesEvent(group, ["one", "two"]),
            GroupSuccessEvent(group, [], []),
            WorkQueueTerminationEvent(),
        ]
