from anyio import sleep
from inspect import isawaitable

from pytest import mark, raises

from graphql.pyutils import SimplePubSub


def describe_simple_pub_sub():
    @mark.parametrize("anyio_backend", ["asyncio"])
    async def subscribe_async_iterator_mock(anyio_backend):
        pubsub = SimplePubSub()
        iterator = pubsub.get_subscriber()

        assert iterator.__aiter__() == iterator
        # Queue up publishes
        assert pubsub.emit("Apple") is True
        assert pubsub.emit("Banana") is True

        # Read payloads
        assert await iterator.__anext__() == "Apple"
        assert await iterator.__anext__() == "Banana"

        # Read ahead
        i3 = await iterator.__anext__()
        assert isawaitable(i3)
        i4 = await iterator.__anext__()
        assert isawaitable(i4)

        # Publish
        assert pubsub.emit("Coconut") is True
        assert pubsub.emit("Durian") is True

        # Await out of order to get correct results
        assert await i4 == "Durian"
        assert await i3 == "Coconut"

        # Read ahead
        i5 = iterator.__anext__()

        # Terminate queue
        await iterator.aclose()

        # Publish is not caught after terminate
        assert pubsub.emit("Fig") is False

        # Find that cancelled read-ahead got a "done" result
        with raises(StopAsyncIteration):
            await i5

        # And next returns empty completion value
        with raises(StopAsyncIteration):
            await iterator.__anext__()

    @mark.parametrize("anyio_backend", ["asyncio"])
    async def iterator_aclose_empties_push_queue(anyio_backend):
        pubsub = SimplePubSub()
        assert not pubsub.subscribers
        iterator = pubsub.get_subscriber()
        assert len(pubsub.subscribers) == 1
        assert iterator.listening
        for value in range(3):
            pubsub.emit(value)
        await sleep(0)
        assert iterator.push_queue.qsize() == 3
        assert iterator.pull_queue.qsize() == 0
        await iterator.aclose()
        assert not pubsub.subscribers
        assert iterator.push_queue.qsize() == 0
        assert iterator.pull_queue.qsize() == 0
        assert not iterator.listening

    @mark.parametrize("anyio_backend", ["asyncio"])
    async def iterator_aclose_empties_pull_queue(anyio_backend):
        pubsub = SimplePubSub()
        assert not pubsub.subscribers
        iterator = pubsub.get_subscriber()
        assert len(pubsub.subscribers) == 1
        assert iterator.listening
        for _n in range(3):
            await iterator.__anext__()
        assert iterator.push_queue.qsize() == 0
        assert iterator.pull_queue.qsize() == 3
        await iterator.aclose()
        assert not pubsub.subscribers
        assert iterator.push_queue.qsize() == 0
        assert iterator.pull_queue.qsize() == 0
        assert not iterator.listening

    @mark.parametrize("anyio_backend", ["asyncio"])
    async def iterator_aclose_is_idempotent(anyio_backend):
        pubsub = SimplePubSub()
        iterator = pubsub.get_subscriber()
        assert iterator.listening
        for n in range(3):
            await iterator.aclose()
            assert not iterator.listening

    @mark.parametrize("anyio_backend", ["asyncio"])
    async def non_async_subscriber(anyio_backend):
        message = "test message"
        received_message = False

        def get_msg(evt):
            nonlocal received_message
            assert evt == message
            received_message = True

        pubsub = SimplePubSub()
        pubsub.subscribers.add(get_msg)
        pubsub.emit(message)
        assert received_message
