"""Simple public-subscribe system"""

from __future__ import annotations

from asyncio import Future, Queue, create_task, get_running_loop, sleep
from typing import Any, AsyncIterator, Callable

from .is_awaitable import is_awaitable

__all__ = ["SimplePubSub", "SimplePubSubIterator"]


class SimplePubSub:
    """A very simple publish-subscript system.

    Creates an AsyncIterator from an EventEmitter.

    Useful for mocking a PubSub system for tests.
    """

    subscribers: set[Callable]

    def __init__(self) -> None:
        self.subscribers = set()

    def emit(self, event: Any) -> bool:
        """Emit an event."""
        for subscriber in self.subscribers:
            result = subscriber(event)
            if is_awaitable(result):
                create_task(result)  # type: ignore # noqa: RUF006
        return bool(self.subscribers)

    def get_subscriber(self, transform: Callable | None = None) -> SimplePubSubIterator:
        """Return subscriber iterator"""
        return SimplePubSubIterator(self, transform)


class SimplePubSubIterator(AsyncIterator):
    """Async iterator used for subscriptions."""

    def __init__(self, pubsub: SimplePubSub, transform: Callable | None) -> None:
        self.pubsub = pubsub
        self.transform = transform
        self.pull_queue: Queue[Future] = Queue()
        self.push_queue: Queue[Any] = Queue()
        self.listening = True
        pubsub.subscribers.add(self.push_value)

    def __aiter__(self) -> SimplePubSubIterator:
        return self

    async def __anext__(self) -> Any:
        if not self.listening:
            raise StopAsyncIteration
        await sleep(0)
        if not self.push_queue.empty():
            return await self.push_queue.get()
        future = get_running_loop().create_future()
        await self.pull_queue.put(future)
        return future

    async def aclose(self) -> None:
        """Close the iterator."""
        if self.listening:
            await self.empty_queue()

    async def empty_queue(self) -> None:
        """Empty the queue."""
        self.listening = False
        self.pubsub.subscribers.remove(self.push_value)
        while not self.pull_queue.empty():
            future = await self.pull_queue.get()
            future.cancel()
        while not self.push_queue.empty():
            await self.push_queue.get()

    async def push_value(self, event: Any) -> None:
        """Push a new value."""
        value = event if self.transform is None else self.transform(event)
        if self.pull_queue.empty():
            await self.push_queue.put(value)
        else:
            (await self.pull_queue.get()).set_result(value)
