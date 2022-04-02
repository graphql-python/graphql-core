from dataclasses import dataclass, field
from typing import Any, List, Optional, Type, Callable
from types import TracebackType

import anyio
from anyio.streams.memory import MemoryObjectSendStream, MemoryObjectReceiveStream

__all__ = ["MemoryObjectBroadcastStream", "create_broadcast_stream"]


def create_broadcast_stream(
    max_buffer_size: float, requires_listeners: bool = False
) -> "MemoryObjectBroadcastStream":
    return MemoryObjectBroadcastStream(
        BroadcastStreamState(max_buffer_size, requires_listeners)
    )


@dataclass
class BroadcastStreamListener:
    stream: MemoryObjectSendStream
    transform: Optional[Callable[[Any], Any]] = None


@dataclass
class BroadcastStreamState:
    max_buffer_size: float
    requires_listeners: bool
    listeners: List[BroadcastStreamListener] = field(default_factory=list)
    ref_counter: int = 0


class MemoryObjectBroadcastStream:
    _state: BroadcastStreamState
    _closed: bool

    def __init__(self, state: BroadcastStreamState):
        self._state = state
        self._closed = False
        self._state.ref_counter += 1

    async def aclose(self) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._state.ref_counter -= 1
            if self._state.ref_counter == 0:
                for listener in self._state.listeners:
                    listener.stream.close()
                self._state.listeners = []

    def clone(self) -> "MemoryObjectBroadcastStream":
        if self._closed:
            raise anyio.ClosedResourceError
        return MemoryObjectBroadcastStream(self._state)

    async def _send_to_listener(
        self, listener: BroadcastStreamListener, item: Any
    ) -> None:
        try:
            if listener.transform is not None:
                item = listener.transform(item)
            await listener.stream.send(item)
        except (anyio.ClosedResourceError, anyio.BrokenResourceError):
            with anyio.CancelScope(shield=True):
                await listener.stream.aclose()
                self._state.listeners.remove(listener)

    async def send(self, item: Any) -> bool:
        if self._closed:
            raise anyio.ClosedResourceError
        async with anyio.create_task_group() as tg:
            for listener in self._state.listeners:
                tg.start_soon(self._send_to_listener, listener, item)
        if not self._state.listeners:
            if self._state.requires_listeners:
                raise anyio.BrokenResourceError
            return False
        return True

    def send_nowait(self, item: Any) -> bool:
        if self._closed:
            raise anyio.ClosedResourceError
        for listener in list(self._state.listeners):
            stats = listener.stream.statistics()
            if stats.open_receive_streams == 0:
                listener.stream.close()
                self._state.listeners.remove(listener)
            # We raise WouldBlock before sending anything
            if (
                stats.max_buffer_size <= stats.current_buffer_used
                and not stats.tasks_waiting_send
            ):
                raise anyio.WouldBlock

        for listener in self._state.listeners:
            try:
                if listener.transform is not None:
                    listener.stream.send_nowait(listener.transform(item))
                else:
                    listener.stream.send_nowait(item)
            except (
                anyio.ClosedResourceError,
                anyio.BrokenResourceError,
            ):  # pragma: no cover
                # we checked all listeners beforehand, this should not happen
                listener.stream.close()
                self._state.listeners.remove(listener)
            except anyio.WouldBlock:  # pragma: no cover
                assert (
                    False  # we checked all listeners beforehand, this should not happen
                )
        if not self._state.listeners:
            if self._state.requires_listeners:
                raise anyio.BrokenResourceError
            return False
        return True

    def get_listener(
        self, transform: Optional[Callable[[Any], Any]] = None
    ) -> MemoryObjectReceiveStream:
        send, receive = anyio.create_memory_object_stream(self._state.max_buffer_size)
        self._state.listeners.append(BroadcastStreamListener(send, transform))
        return receive

    def __enter__(self) -> "MemoryObjectBroadcastStream":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.close()

    async def __aenter__(self) -> "MemoryObjectBroadcastStream":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.close()
