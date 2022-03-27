# pytest configuration

import sys

import pytest

if sys.version_info >= (3, 7):
    event_loops = [
        pytest.param(("asyncio"), id="asyncio"),
        pytest.param(("trio"), id="trio"),
    ]
else:
    event_loops = [pytest.param(("asyncio"), id="asyncio")]


@pytest.fixture(params=event_loops)
def anyio_backend(request):
    return request.param


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-slow"):
        # without --run-slow option: skip all slow tests
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
