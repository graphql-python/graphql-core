Using resolver methods
----------------------

.. currentmodule:: graphql

Above we have attached resolver functions to the schema only. However, it is also
possible to define resolver methods on the resolved objects, starting with the
``root_value`` object that you can pass to the :func:`graphql` function when executing
a query.

In our case, we could create a ``Root`` class with three methods as root resolvers, like
so::

    class Root:
        """The root resolvers"""

        def hero(self, info, episode):
            return luke if episode == 5 else artoo

        def human(self, info, id):
            return human_data.get(id)

        def droid(self, info, id):
            return droid_data.get(id)


Since we have defined synchronous methods only, we will use the :func:`graphql_sync`
function to execute a query, passing a ``Root()`` object as the ``root_value``::

    from graphql import graphql_sync

    result = graphql_sync(schema, """
        {
          droid(id: "2001") {
            name
            primaryFunction
          }
        }
        """, Root())
    print(result)

Even if we haven't attached a resolver to the ``hero`` field as we did above, this would
now still resolve and give the following output::

    ExecutionResult(
        data={'droid': {'name': 'R2-D2', 'primaryFunction': 'Astromech'}},
        errors=None)

Of course you can also define asynchronous methods as resolvers, and execute queries
asynchronously with :func:`graphql`.

In a similar vein, you can also attach resolvers as methods to the resolved objects on
deeper levels than the root of the query. In that case, instead of resolving to
dictionaries with keys for all the fields, as we did above, you would resolve to objects
with attributes for all the fields. For instance, you would define a class ``Human``
with a method ``friends()`` for resolving the friends of a human. You can also make
use of inheritance in this case. The ``Human`` class and a ``Droid`` class could inherit
from a ``Character`` class and use its methods as resolvers for common fields.
