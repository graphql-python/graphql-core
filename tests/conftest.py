# pytest configuration

import sys
from importlib import import_module

import pytest


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


@pytest.fixture
def without_nesting_limit(monkeypatch):
    """Let deep input run into the stack limit, to test how that is handled.

    PyPy does not handle a stack overflow in JIT-compiled code reliably, so the
    nesting limit stays in place there.
    """
    if sys.implementation.name == "pypy":  # pragma: no cover
        return
    for name in ("language.parser", "validation.validate", "execution.values"):
        module = import_module(f"graphql.{name}")
        monkeypatch.setattr(module, "MAX_NESTING_DEPTH", sys.maxsize)


@pytest.fixture
def anyio_backend():
    return "asyncio"
