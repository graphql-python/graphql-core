"""Work queue scheduling incremental delivery"""

from __future__ import annotations

from asyncio import (
    CancelledError,
    Event,
    Queue,
    QueueEmpty,
    ensure_future,
    gather,
)
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol, TypeAlias, cast

from ...pyutils.is_awaitable import is_awaitable

if TYPE_CHECKING:
    from asyncio import Future, Task
    from collections.abc import AsyncIterator, Awaitable, Sequence

    from .computation import Computation

__all__ = [
    "Group",
    "GroupFailureEvent",
    "GroupSuccessEvent",
    "GroupValuesEvent",
    "Stream",
    "StreamFailureEvent",
    "StreamItem",
    "StreamQueue",
    "StreamSuccessEvent",
    "StreamValuesEvent",
    "TaskResult",
    "Work",
    "WorkQueue",
    "WorkQueueEvent",
    "WorkQueueTerminationEvent",
    "WorkResult",
    "WorkTask",
]

_UNSET: Any = object()

_STOP: Any = object()  # sentinel waking up the event consumer on cancellation


class Group(Protocol):
    """A group of work with an optional parent group. For internal use only."""

    parent: Any  # the parent Group or None


class StreamQueue(Protocol):
    """The queue interface a stream must provide. For internal use only."""

    def batches(self) -> AsyncIterator[Sequence[Any]]:
        """Iterate over the batches of settled stream items."""
        ...

    def is_stopped(self) -> bool:
        """Check whether the stream is known to have stopped normally."""
        ...

    def abort(self, reason: BaseException | None = None) -> Awaitable[None] | None:
        """Abort the stream with an optional reason."""
        ...


class Stream(Protocol):
    """A stream of work items backed by a queue. For internal use only."""

    queue: StreamQueue


class WorkResult(NamedTuple):
    """The value produced by a task or stream item, with new nested work."""

    value: Any
    work: Work | None = None


StreamItem = WorkResult
TaskResult = WorkResult


class WorkTask:
    """A computation belonging to one or more groups.

    Compared and hashed by identity, like all graph nodes.
    """

    __slots__ = "computation", "groups"

    groups: Sequence[Group]
    computation: Computation[WorkResult]

    def __init__(
        self, groups: Sequence[Group], computation: Computation[WorkResult]
    ) -> None:
        self.groups = groups
        self.computation = computation


class Work(NamedTuple):
    """New work produced during execution."""

    groups: Sequence[Group] = ()
    tasks: Sequence[WorkTask] = ()
    streams: Sequence[Stream] = ()


# internal graph events


class _TaskSuccess(NamedTuple):
    task: WorkTask
    result: WorkResult


class _TaskFailure(NamedTuple):
    task: WorkTask
    error: BaseException


class _StreamItems(NamedTuple):
    stream: Stream
    items: Sequence[StreamItem]
    handled: Event  # pacing: the pump proceeds only after handling


class _StreamSuccess(NamedTuple):
    stream: Stream


class _StreamFailure(NamedTuple):
    stream: Stream
    error: BaseException


# public work queue events


class GroupValuesEvent(NamedTuple):
    """All values produced for a completed group."""

    group: Group
    values: Sequence[Any]


class GroupSuccessEvent(NamedTuple):
    """A group completed successfully, promoting new work."""

    group: Group
    new_groups: Sequence[Group]
    new_streams: Sequence[Stream]


class GroupFailureEvent(NamedTuple):
    """A group failed with an error."""

    group: Group
    error: BaseException


class StreamValuesEvent(NamedTuple):
    """New values produced by a stream, promoting new work."""

    stream: Stream
    values: Sequence[Any]
    new_groups: Sequence[Group]
    new_streams: Sequence[Stream]


class StreamSuccessEvent(NamedTuple):
    """A stream completed successfully."""

    stream: Stream


class StreamFailureEvent(NamedTuple):
    """A stream failed with an error."""

    stream: Stream
    error: BaseException


class WorkQueueTerminationEvent(NamedTuple):
    """All work has been delivered; the work queue terminates."""


WorkQueueEvent: TypeAlias = (
    GroupValuesEvent
    | GroupSuccessEvent
    | GroupFailureEvent
    | StreamValuesEvent
    | StreamSuccessEvent
    | StreamFailureEvent
    | WorkQueueTerminationEvent
)


class _GroupNode:
    """Bookkeeping for a group in the work graph."""

    __slots__ = "child_groups", "pending", "tasks"

    child_groups: list[Group]
    tasks: dict[WorkTask, None]  # used as ordered set
    pending: int

    def __init__(self) -> None:
        self.child_groups = []
        self.tasks = {}
        self.pending = 0


class _TaskNode:
    """Bookkeeping for a started task in the work graph."""

    __slots__ = "child_streams", "value"

    value: Any
    child_streams: list[Stream]

    def __init__(self) -> None:
        self.value = _UNSET
        self.child_streams = []


class WorkQueue:
    """Dependency-graph scheduler for incremental delivery.

    Integrates the work produced during execution into a dependency graph,
    starts tasks and streams when their group becomes deliverable, prunes
    empty groups, removes failed subtrees, and translates task and stream
    completions into an asynchronous sequence of work queue event batches.

    For internal use only.
    """

    initial_groups: Sequence[Group]
    initial_streams: Sequence[Stream]

    def __init__(self, initial_work: Work | None = None) -> None:
        """Initialize the work queue with the initially produced work."""
        self._root_groups: dict[Group, None] = {}  # used as ordered set
        self._root_streams: dict[Stream, None] = {}  # used as ordered set
        self._group_nodes: dict[Group, _GroupNode] = {}
        self._task_nodes: dict[WorkTask, _TaskNode] = {}
        self._channel: Queue[Any] = Queue()
        self._stopped = False
        self._pump_tasks: set[Task[None]] = set()

        new_groups, new_streams = self._maybe_integrate_work(initial_work)
        non_empty_initial_root_groups = self._prune_empty_groups(new_groups)
        # Initialize root groups and streams at startup to prepare for
        # cancellation prior to starting the work queue.
        for group in non_empty_initial_root_groups:
            self._root_groups[group] = None
        for stream in new_streams:
            self._root_streams[stream] = None
        self.initial_groups = non_empty_initial_root_groups
        self.initial_streams = new_streams

    async def events(self) -> AsyncIterator[Sequence[WorkQueueEvent]]:
        """Iterate over the batches of work queue events.

        Starts the root groups and streams on the first iteration step.
        """
        for group in list(self._root_groups):
            self._start_group(group)
        for stream in list(self._root_streams):
            self._start_stream(stream)
        channel = self._channel
        while not self._stopped:
            work_queue_events: list[WorkQueueEvent] = []
            graph_event = await channel.get()
            while True:
                if graph_event is not _STOP:
                    # Handling a graph event may synchronously push further
                    # graph events (e.g. when a completed group releases a
                    # child group whose tasks complete synchronously); these
                    # are picked up and handled within the same batch.
                    work_queue_events.extend(self._handle_graph_event(graph_event))
                try:
                    graph_event = channel.get_nowait()
                except QueueEmpty:
                    break
            if not self._root_groups and not self._root_streams:
                self._stopped = True
                work_queue_events.append(WorkQueueTerminationEvent())
            if work_queue_events:
                yield work_queue_events

    async def cancel(self, reason: BaseException | None = None) -> None:
        """Cancel all pending work, awaiting any asynchronous cleanup."""
        self._stopped = True
        self._channel.put_nowait(_STOP)  # wake up a parked event consumer
        cancel_awaitables: list[Awaitable[Any]] = []
        for group in list(self._root_groups):
            self._cancel_group(group, reason, cancel_awaitables)
        for stream in list(self._root_streams):
            self._cancel_stream(stream, reason, cancel_awaitables)
        for pump_task in self._pump_tasks:
            pump_task.cancel()
        cancel_awaitables.extend(self._pump_tasks)
        if cancel_awaitables:
            await gather(*cancel_awaitables, return_exceptions=True)

    def _cancel_group(
        self,
        group: Group,
        reason: BaseException | None,
        cancel_awaitables: list[Awaitable[Any]],
    ) -> None:
        """Recursively cancel a group with its tasks and child groups."""
        group_node = self._group_nodes.get(group)
        # defensive guard mirroring the JS version; while pending groups are
        # never cancelled twice, their nodes always exist
        if group_node:  # pragma: no branch
            for task in group_node.tasks:
                self._cancel_task(task, reason, cancel_awaitables)
            for child_group in group_node.child_groups:
                self._cancel_group(child_group, reason, cancel_awaitables)

    def _cancel_task(
        self,
        task: WorkTask,
        reason: BaseException | None,
        cancel_awaitables: list[Awaitable[Any]],
    ) -> None:
        """Cancel a task with the streams produced by it."""
        abort_result = task.computation.abort(reason)
        if is_awaitable(abort_result):
            cancel_awaitables.append(abort_result)
        task_node = self._task_nodes.get(task)
        if task_node:
            for child_stream in task_node.child_streams:
                self._cancel_stream(child_stream, reason, cancel_awaitables)

    def _cancel_stream(
        self,
        stream: Stream,
        reason: BaseException | None,
        cancel_awaitables: list[Awaitable[Any]],
    ) -> None:
        """Cancel a stream."""
        abort_result = stream.queue.abort(reason)
        if is_awaitable(abort_result):
            cancel_awaitables.append(abort_result)

    def _push(self, graph_event: Any) -> None:
        """Push a graph event to the channel unless already stopped."""
        if not self._stopped:
            self._channel.put_nowait(graph_event)

    def _maybe_integrate_work(
        self, work: Work | None, parent_task: WorkTask | None = None
    ) -> tuple[list[Group], Sequence[Stream]]:
        """Integrate new work into the graph, returning new root work."""
        if not work:
            return [], []
        groups, tasks, streams = work
        new_groups = self._add_groups(groups, parent_task) if groups else []
        for task in tasks:
            self._add_task(task)
        new_streams = self._add_streams(streams, parent_task) if streams else []
        return new_groups, new_streams

    def _add_groups(
        self, original_groups: Sequence[Group], parent_task: WorkTask | None = None
    ) -> list[Group]:
        """Add new groups to the graph, returning the new root groups."""
        group_set = set(original_groups)
        visited: set[Group] = set()
        new_root_groups: list[Group] = []
        for group in original_groups:
            self._add_group(group, group_set, new_root_groups, visited, parent_task)
        return new_root_groups

    def _add_group(
        self,
        group: Group,
        group_set: set[Group],
        new_root_groups: list[Group],
        visited: set[Group],
        parent_task: WorkTask | None = None,
    ) -> None:
        """Add a new group to the graph, parents first."""
        if group in visited:
            return
        visited.add(group)
        parent = group.parent
        if parent is not None and parent in group_set:
            self._add_group(parent, group_set, new_root_groups, visited, parent_task)

        self._group_nodes[group] = _GroupNode()

        if parent_task is None and not parent:
            new_root_groups.append(group)
        elif parent:
            parent_node = self._group_nodes.get(parent)
            if parent_node:
                parent_node.child_groups.append(group)

    def _add_task(self, task: WorkTask) -> None:
        """Add a new task to the graph, starting it if its group is a root."""
        for group in task.groups:
            group_node = self._group_nodes.get(group)
            if group_node:
                group_node.tasks[task] = None
                group_node.pending += 1
                if group in self._root_groups:
                    self._start_task(task)

    def _add_streams(
        self, streams: Sequence[Stream], parent_task: WorkTask | None = None
    ) -> Sequence[Stream]:
        """Add new streams, attaching them to the producing task if any."""
        if not parent_task:
            return streams
        task_node = self._task_nodes.get(parent_task)
        if task_node:
            task_node.child_streams.extend(streams)
        return []

    def _prune_empty_groups(
        self,
        new_groups: Sequence[Group],
        non_empty_new_groups: list[Group] | None = None,
    ) -> list[Group]:
        """Prune empty groups, promoting their non-empty descendants."""
        if non_empty_new_groups is None:
            non_empty_new_groups = []
        group_nodes = self._group_nodes
        for new_group in new_groups:
            new_group_node = group_nodes.get(new_group)
            if new_group_node:
                if new_group_node.pending:
                    non_empty_new_groups.append(new_group)
                else:
                    del group_nodes[new_group]
                    self._prune_empty_groups(
                        new_group_node.child_groups, non_empty_new_groups
                    )
        return non_empty_new_groups

    def _start_new_work(
        self, new_groups: Sequence[Group], new_streams: Sequence[Stream]
    ) -> None:
        """Promote new groups and streams to root and start them."""
        for group in new_groups:
            self._root_groups[group] = None
            self._start_group(group)
        for stream in new_streams:
            self._root_streams[stream] = None
            self._start_stream(stream)

    def _start_group(self, group: Group) -> None:
        """Start all tasks of a group."""
        group_node = self._group_nodes.get(group)
        # defensive guard mirroring the JS version; groups are only
        # promoted right after pruning, when their nodes always exist
        if group_node:  # pragma: no branch
            for task in list(group_node.tasks):
                self._start_task(task)

    def _start_task(self, task: WorkTask) -> None:
        """Start a task, pushing a graph event when its computation settles."""
        task_nodes = self._task_nodes
        if task in task_nodes:
            return
        task_nodes[task] = _TaskNode()
        try:
            result = task.computation.result()
        except Exception as error:
            self._push(_TaskFailure(task, error))
            return
        if is_awaitable(result):
            future: Future[WorkResult] = ensure_future(result)

            def settle_task(future: Future[WorkResult]) -> None:
                if future.cancelled():
                    self._push(_TaskFailure(task, CancelledError()))
                    return
                error = future.exception()
                if error is None:
                    self._push(_TaskSuccess(task, future.result()))
                else:
                    self._push(_TaskFailure(task, error))

            future.add_done_callback(settle_task)
        else:
            self._push(_TaskSuccess(task, cast("WorkResult", result)))

    def _start_stream(self, stream: Stream) -> None:
        """Start pumping the batches of a stream into the channel."""

        async def pump() -> None:
            try:
                async for items in stream.queue.batches():
                    handled = Event()
                    self._push(_StreamItems(stream, list(items), handled))
                    # Wait until the items were handled before proceeding, so
                    # that work spawned by them is scheduled before the next
                    # batch and before the success of this stream.
                    await handled.wait()
            except Exception as error:
                self._push(_StreamFailure(stream, error))
            else:
                self._push(_StreamSuccess(stream))

        pump_task = ensure_future(pump())
        pump_tasks = self._pump_tasks
        pump_tasks.add(pump_task)
        pump_task.add_done_callback(pump_tasks.discard)

    def _handle_graph_event(self, graph_event: Any) -> Sequence[WorkQueueEvent]:
        """Translate a single graph event into work queue events."""
        if isinstance(graph_event, _TaskSuccess):
            return self._task_success(graph_event)
        if isinstance(graph_event, _TaskFailure):
            return self._task_failure(graph_event)
        if isinstance(graph_event, _StreamItems):
            return self._stream_items(graph_event)
        root_streams = self._root_streams
        if isinstance(graph_event, _StreamSuccess):
            stream = graph_event.stream
            # check whether already delivered within _stream_items()
            if stream in root_streams:
                del root_streams[stream]
                return [StreamSuccessEvent(stream)]
            return []
        # _StreamFailure
        stream, error = graph_event
        root_streams.pop(stream, None)
        return [StreamFailureEvent(stream, error)]

    def _task_success(
        self, graph_event: _TaskSuccess
    ) -> Sequence[GroupValuesEvent | GroupSuccessEvent]:
        """Handle a task success, finishing groups that become complete."""
        task, result = graph_event
        value, work = result
        task_node = self._task_nodes.get(task)
        if task_node:
            task_node.value = value
        self._maybe_integrate_work(work, task)

        group_events: list[GroupValuesEvent | GroupSuccessEvent] = []
        new_groups: list[Group] = []
        new_streams: list[Stream] = []
        root_groups = self._root_groups
        for group in task.groups:
            group_node = self._group_nodes.get(group)
            if group_node:
                group_node.pending -= 1
                if group in root_groups and not group_node.pending:
                    (
                        group_values_event,
                        group_success_event,
                        child_new_groups,
                        child_new_streams,
                    ) = self._finish_group_success(group, group_node)
                    if group_values_event:
                        group_events.append(group_values_event)
                    group_events.append(group_success_event)
                    new_groups.extend(child_new_groups)
                    new_streams.extend(child_new_streams)

        self._start_new_work(new_groups, new_streams)
        return group_events

    def _task_failure(self, graph_event: _TaskFailure) -> Sequence[GroupFailureEvent]:
        """Handle a task failure, removing all groups it belongs to."""
        task, error = graph_event
        self._task_nodes.pop(task, None)
        group_failure_events: list[GroupFailureEvent] = []
        for group in task.groups:
            group_node = self._group_nodes.get(group)
            if group_node:
                group_failure_events.append(
                    self._finish_group_failure(group, group_node, error)
                )
        return group_failure_events

    def _stream_items(
        self, graph_event: _StreamItems
    ) -> Sequence[StreamValuesEvent | StreamSuccessEvent]:
        """Handle new stream items, integrating the work they produced."""
        stream, items, handled = graph_event
        values: list[Any] = []
        new_groups: list[Group] = []
        new_streams: list[Stream] = []
        for value, work in items:
            item_new_groups, item_new_streams = self._maybe_integrate_work(work)
            non_empty_new_groups = self._prune_empty_groups(item_new_groups)
            self._start_new_work(non_empty_new_groups, item_new_streams)
            values.append(value)
            new_groups.extend(non_empty_new_groups)
            new_streams.extend(item_new_streams)
        handled.set()  # resume the pump of this stream
        stream_values_event = StreamValuesEvent(stream, values, new_groups, new_streams)

        # queues allow peeking ahead to see if the stream has stopped
        if stream.queue.is_stopped():
            self._root_streams.pop(stream, None)
            return [stream_values_event, StreamSuccessEvent(stream)]
        return [stream_values_event]

    def _finish_group_success(
        self, group: Group, group_node: _GroupNode
    ) -> tuple[
        GroupValuesEvent | None,
        GroupSuccessEvent,
        Sequence[Group],
        Sequence[Stream],
    ]:
        """Finish a successfully completed group, promoting its children."""
        del self._group_nodes[group]
        values: list[Any] = []
        new_streams: list[Stream] = []
        task_nodes = self._task_nodes
        for task in list(group_node.tasks):
            task_node = task_nodes.get(task)
            if task_node:  # pragma: no branch
                value = task_node.value
                if value is not _UNSET:  # pragma: no branch
                    values.append(value)
                new_streams.extend(task_node.child_streams)
                self._remove_task(task)
        new_groups = self._prune_empty_groups(group_node.child_groups)
        del self._root_groups[group]
        return (
            GroupValuesEvent(group, values) if values else None,
            GroupSuccessEvent(group, new_groups, new_streams),
            new_groups,
            new_streams,
        )

    def _finish_group_failure(
        self, group: Group, group_node: _GroupNode, error: BaseException
    ) -> GroupFailureEvent:
        """Finish a failed group, removing its whole subtree."""
        self._remove_group(group, group_node)
        self._root_groups.pop(group, None)
        return GroupFailureEvent(group, error)

    def _remove_group(self, group: Group, group_node: _GroupNode) -> None:
        """Remove a group with its tasks and child groups from the graph."""
        group_nodes = self._group_nodes
        del group_nodes[group]
        for task in list(group_node.tasks):
            if all(task_group not in group_nodes for task_group in task.groups):
                self._remove_task(task)
        for child_group in group_node.child_groups:
            child_group_node = group_nodes.get(child_group)
            if child_group_node:
                self._remove_group(child_group, child_group_node)

    def _remove_task(self, task: WorkTask) -> None:
        """Remove a task from all its groups and from the graph."""
        group_nodes = self._group_nodes
        for group in task.groups:
            group_node = group_nodes.get(group)
            if group_node:
                group_node.tasks.pop(task, None)
        self._task_nodes.pop(task, None)
