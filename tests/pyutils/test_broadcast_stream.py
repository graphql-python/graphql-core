from anyio import (
    sleep,
    fail_after,
    create_task_group,
    Event,
    ClosedResourceError,
    WouldBlock,
    BrokenResourceError,
)
import math

from pytest import mark, raises

from graphql.pyutils import create_broadcast_stream


def describe_broadcast_stream():
    @mark.anyio
    async def subscribe_async_iterator_mock():
        pubsub = create_broadcast_stream(math.inf)
        iterator = pubsub.get_listener()

        with fail_after(1):
            # Queue up publishes
            assert pubsub.send_nowait("Apple") is True
            assert pubsub.send_nowait("Banana") is True

            # Read payloads
            assert await iterator.__anext__() == "Apple"
            assert await iterator.__anext__() == "Banana"

            # Waiting for data
            is_waiting = Event()
            i3 = None
            i4 = None

            async def wait_for_next():
                nonlocal i3, i4
                is_waiting.set()
                i3 = await iterator.__anext__()
                i4 = await iterator.__anext__()

            async with create_task_group() as tg:
                tg.start_soon(wait_for_next)
                await is_waiting.wait()
                await sleep(0.1)
                # Publish
                assert pubsub.send_nowait("Coconut") is True
                assert pubsub.send_nowait("Durian") is True

            assert i3 == "Coconut"
            assert i4 == "Durian"

            # Terminate queue
            await iterator.aclose()

            # Publish is not caught after terminate
            assert pubsub.send_nowait("Fig") is False

            with raises(ClosedResourceError):
                await iterator.__anext__()

    @mark.anyio
    async def iterator_aclose_closes_listeners():
        pubsub = create_broadcast_stream(math.inf)
        assert not pubsub._state.listeners
        iterator = pubsub.get_listener()
        assert len(pubsub._state.listeners) == 1

        for value in range(3):
            pubsub.send_nowait(value)
        await sleep(0)
        await iterator.aclose()
        assert pubsub.send_nowait(value) is False  # listeners closed on next send
        assert not pubsub._state.listeners

    @mark.anyio
    async def stream_aclose_closes_listeners():
        pubsub = create_broadcast_stream(math.inf)
        iterator = pubsub.get_listener()
        await pubsub.aclose()
        with fail_after(1):
            async for el in iterator:
                pass

    @mark.anyio
    async def multiple_listeners_get_object():
        pubsub = create_broadcast_stream(math.inf)
        iterator1 = pubsub.get_listener()
        pubsub.send_nowait("A")
        iterator2 = pubsub.get_listener()
        pubsub.send_nowait("B")
        pubsub.send_nowait("C")
        await pubsub.aclose()
        await pubsub.aclose()  # idempotent
        with fail_after(1):
            assert ["A", "B", "C"] == [el async for el in iterator1]
            assert ["B", "C"] == [el async for el in iterator2]

    @mark.anyio
    async def cloned_broadcast():
        pubsub1 = create_broadcast_stream(math.inf)
        pubsub2 = pubsub1.clone()
        iterator1 = pubsub1.get_listener()
        pubsub2.send_nowait("A")
        iterator2 = pubsub2.get_listener()
        pubsub1.send_nowait("B")
        pubsub2.send_nowait("C")

        assert pubsub2._state.ref_counter == 2
        await pubsub1.aclose()
        assert pubsub2._state.ref_counter == 1
        # check expected errors after close
        with raises(ClosedResourceError):
            pubsub1.send_nowait("D")
        with raises(ClosedResourceError):
            await pubsub1.send("D")
        with raises(ClosedResourceError):
            pubsub1.clone()

        # idempotent close
        assert pubsub2._state.ref_counter == 1
        await pubsub1.aclose()
        assert pubsub2._state.ref_counter == 1
        pubsub2.send_nowait("E")

        await pubsub2.aclose()
        with fail_after(1):
            assert ["A", "B", "C", "E"] == [el async for el in iterator1]
            assert ["B", "C", "E"] == [el async for el in iterator2]

    def blocking_stream():
        pubsub = create_broadcast_stream(0)
        pubsub.send_nowait("A")  # no listener

        pubsub.get_listener()
        with raises(WouldBlock):
            pubsub.send_nowait("B")

    @mark.anyio
    async def close_listeners():
        pubsub = create_broadcast_stream(math.inf)
        iterator = pubsub.get_listener()
        assert pubsub._state.listeners
        await iterator.aclose()
        pubsub.send_nowait("A")
        assert not pubsub._state.listeners

    @mark.anyio
    async def requires_listeners():
        pubsub = create_broadcast_stream(math.inf, requires_listeners=True)
        with raises(BrokenResourceError):
            pubsub.send_nowait("A")

        iterator = pubsub.get_listener()
        assert pubsub._state.listeners
        await iterator.aclose()
        with raises(BrokenResourceError):
            pubsub.send_nowait("B")
        assert not pubsub._state.listeners

        iterator = pubsub.get_listener()
        assert pubsub._state.listeners
        await iterator.aclose()
        with raises(BrokenResourceError):
            await pubsub.send("C")
        assert not pubsub._state.listeners

    @mark.anyio
    async def transformation():
        pubsub = create_broadcast_stream(math.inf)
        iterator1 = pubsub.get_listener(transform=lambda el: 2 * el)
        pubsub.send_nowait(1)
        iterator2 = pubsub.get_listener(transform=lambda el: 3 * el)
        pubsub.send_nowait(2)
        pubsub.send_nowait(3)
        await pubsub.aclose()
        with fail_after(1):
            assert [2, 4, 6] == [el async for el in iterator1]
            assert [6, 9] == [el async for el in iterator2]

    @mark.anyio
    async def context_manager():
        pubsub = create_broadcast_stream(math.inf)
        async with pubsub as context:
            assert pubsub is context
        assert pubsub._closed

        pubsub = create_broadcast_stream(math.inf)
        with pubsub as context:
            assert pubsub is context
        assert pubsub._closed
