from asyncio import AbstractEventLoop, Queue, ensure_future
from collections import defaultdict
from inspect import isawaitable
from typing import cast, Any, Callable, Dict, List, Optional

__all__ = ["EventEmitter", "EventEmitterAsyncIterator"]


class EventEmitter:
    """A very simple EventEmitter."""

    def __init__(self, loop: Optional[AbstractEventLoop] = None) -> None:
        self.loop = loop
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)

    def add_listener(self, event_name: str, listener: Callable) -> "EventEmitter":
        """Add a listener."""
        self.listeners[event_name].append(listener)
        return self

    def remove_listener(self, event_name: str, listener: Callable) -> "EventEmitter":
        """Removes a listener."""
        self.listeners[event_name].remove(listener)
        return self

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> bool:
        """Emit an event."""
        listeners = list(self.listeners[event_name])
        if not listeners:
            return False
        for listener in listeners:
            result = listener(*args, **kwargs)
            if isawaitable(result):
                ensure_future(result, loop=self.loop)
        return True


class EventEmitterAsyncIterator:
    """Create an AsyncIterator from an EventEmitter.

    Useful for mocking a PubSub system for tests.
    """

    def __init__(self, event_emitter: EventEmitter, event_name: str) -> None:
        self.queue: Queue = Queue(loop=cast(AbstractEventLoop, event_emitter.loop))
        event_emitter.add_listener(event_name, self.queue.put)
        self.remove_listener = lambda: event_emitter.remove_listener(
            event_name, self.queue.put
        )
        self.closed = False

    def __aiter__(self) -> "EventEmitterAsyncIterator":
        return self

    async def __anext__(self) -> Any:
        if self.closed:
            raise StopAsyncIteration
        return await self.queue.get()

    async def aclose(self) -> None:
        self.remove_listener()
        while not self.queue.empty():
            await self.queue.get()
        self.closed = True
