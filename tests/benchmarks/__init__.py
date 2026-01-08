"""Benchmarks for graphql

Benchmarks are disabled (only executed as tests) by default in pyproject.toml.
You can enable them with --benchmark-enable if your want to execute them.

E.g. in order to execute all the benchmarks with tox using Python 3.14::

    tox -e py314 -- -k benchmarks --benchmark-enable
"""
