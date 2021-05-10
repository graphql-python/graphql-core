"""GraphQL Subscription

The :mod:`graphql.subscription` package is responsible for subscribing to updates
on specific data.
"""

from .subscribe import subscribe, create_source_event_stream
from .map_async_iterator import MapAsyncIterator

__all__ = ["subscribe", "create_source_event_stream", "MapAsyncIterator"]
