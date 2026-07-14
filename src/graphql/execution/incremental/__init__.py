"""Incremental delivery execution

The :mod:`graphql.execution.incremental` package contains the incremental
delivery engine that schedules and publishes deferred and streamed payloads.
For internal use only.
"""

from .computation import Computation

__all__ = ["Computation"]
