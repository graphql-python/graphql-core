Extending a Schema
------------------

.. currentmodule:: graphql.utilities

With GraphQL-core 3 you can also extend a given schema using type extensions. For
example, we might want to add a ``lastName`` property to our ``Human`` data type to
retrieve only the last name of the person.

This can be achieved with the :func:`extend_schema` function as follows::

    from graphql import extend_schema, parse

    schema = extend_schema(schema, parse("""
        extend type Human {
         lastName: String
        }
        """))

Note that this function expects the extensions as an AST, which we can get using the
:func:`~graphql.language.parse` function. Also note that the :func:`extend_schema`
function does not alter the original schema, but returns a new schema object.

We also need to attach a resolver function to the new field::

    def get_last_name(human, info):
        return human['name'].rsplit(None, 1)[-1]

    schema.get_type('Human').fields['lastName'].resolve = get_last_name

Now we can query only the last name of a human::

    from graphql import graphql_sync

    result = graphql_sync(schema, """
        {
          human(id: "1000") {
            lastName
            homePlanet
          }
        }
        """)
    print(result)

This query will give the following result::

    ExecutionResult(
        data={'human': {'lastName': 'Skywalker', 'homePlanet': 'Tatooine'}},
        errors=None)

