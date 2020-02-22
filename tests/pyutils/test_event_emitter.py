from asyncio import sleep

from pytest import mark, raises  # type: ignore

from graphql.pyutils import EventEmitter, EventEmitterAsyncIterator


def describe_event_emitter():
    def add_and_remove_listeners():
        emitter = EventEmitter()

        def listener1(_value):
            pass

        def listener2(_value):
            pass

        emitter.add_listener("foo", listener1)
        emitter.add_listener("foo", listener2)
        emitter.add_listener("bar", listener1)
        assert emitter.listeners["foo"] == [listener1, listener2]
        assert emitter.listeners["bar"] == [listener1]
        emitter.remove_listener("foo", listener1)
        assert emitter.listeners["foo"] == [listener2]
        assert emitter.listeners["bar"] == [listener1]
        emitter.remove_listener("foo", listener2)
        assert emitter.listeners["foo"] == []
        assert emitter.listeners["bar"] == [listener1]
        emitter.remove_listener("bar", listener1)
        assert emitter.listeners["bar"] == []

    def emit_sync():
        emitter = EventEmitter()
        emitted = []

        def listener(value):
            emitted.append(value)

        emitter.add_listener("foo", listener)
        assert emitter.emit("foo", "bar") is True
        assert emitted == ["bar"]
        assert emitter.emit("bar", "baz") is False
        assert emitted == ["bar"]

    @mark.asyncio
    async def emit_async():
        emitter = EventEmitter()
        emitted = []

        async def listener(value):
            emitted.append(value)

        emitter.add_listener("foo", listener)
        emitter.emit("foo", "bar")
        emitter.emit("bar", "baz")
        await sleep(0)
        assert emitted == ["bar"]


def describe_event_emitter_async_iterator():
    @mark.asyncio
    async def subscribe_async_iterator_mock():
        # Create an AsyncIterator from an EventEmitter
        emitter = EventEmitter()
        iterator = EventEmitterAsyncIterator(emitter, "publish")

        # Make sure it works as an async iterator
        assert iterator.__aiter__() is iterator
        assert callable(iterator.__anext__)

        # Queue up publishes
        assert emitter.emit("publish", "Apple") is True
        assert emitter.emit("publish", "Banana") is True

        # Read payloads
        assert await iterator.__anext__() == "Apple"
        assert await iterator.__anext__() == "Banana"

        # Read ahead
        i3 = iterator.__anext__()
        i4 = iterator.__anext__()

        # Publish
        assert emitter.emit("publish", "Coconut") is True
        assert emitter.emit("publish", "Durian") is True

        # Await results
        assert await i3 == "Coconut"
        assert await i4 == "Durian"

        # Read ahead
        i5 = iterator.__anext__()

        # Terminate emitter
        await iterator.aclose()

        # Publish is not caught after terminate
        assert emitter.emit("publish", "Fig") is False

        # Find that cancelled read-ahead got a "done" result
        with raises(StopAsyncIteration):
            await i5

        # And next returns empty completion value
        with raises(StopAsyncIteration):
            await iterator.__anext__()

    @mark.asyncio
    async def aclose_cleans_up():
        emitter = EventEmitter()
        assert emitter.listeners["publish"] == []
        iterator = EventEmitterAsyncIterator(emitter, "publish")
        assert emitter.listeners["publish"] == [iterator.queue.put]
        assert not iterator.closed
        for value in range(3):
            emitter.emit("publish", value)
        await sleep(0)
        assert iterator.queue.qsize() == 3
        await iterator.aclose()
        assert emitter.listeners["publish"] == []
        assert iterator.queue.empty()
        assert iterator.closed
