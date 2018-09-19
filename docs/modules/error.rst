Error
=====

.. automodule:: graphql.error

.. autoexception:: GraphQLError
.. autoexception:: GraphQLSyntaxError

.. autofunction:: located_error
.. autofunction:: print_error
.. autofunction:: format_error

The :mod:`graphql.error` module also contains the :const:`INVALID` singleton that is
used to describe invalid or undefined values and corresponds to the ``undefined``
value in GraphQL.js.
