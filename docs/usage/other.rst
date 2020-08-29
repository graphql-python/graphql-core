Subscriptions
-------------

.. currentmodule:: graphql.subscription

Sometimes you need to not only query data from a server, but you also want to push data
from the server to the client. GraphQL-core 3 has you also covered here, because it
implements the "Subscribe" algorithm described in the GraphQL spec. To execute a GraphQL
subscription, you must use the :func:`subscribe` method from the
:mod:`graphql.subscription` module. Instead of a single
:class:`~graphql.execution.ExecutionResult`, this function returns an asynchronous
iterator yielding a stream of those, unless there was an immediate error.
Of course you will then also need to maintain a persistent channel to the client
(often realized via WebSockets) to push these results back.


Other Usages
------------

.. currentmodule:: graphql.utilities

GraphQL-core 3 provides many more low-level functions that can be used to work with
GraphQL schemas and queries. We encourage you to explore the contents of the various
:ref:`sub-packages`, particularly :mod:`graphql.utilities`, and to look into the source
code and tests of `GraphQL-core 3`_ in order to find all the functionality that is
provided and understand it in detail.

.. _GraphQL-core 3: https://github.com/graphql-python/graphql-core
