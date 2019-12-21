Validating GraphQL Queries
--------------------------

.. currentmodule:: graphql.validation

When executing GraphQL queries, the second step that happens under the hood after
parsing the source code is a validation against the given schema using the rules of the
GraphQL specification. You can also run the validation step manually by calling the
:func:`graphql.validation.validate` function, passing the schema and the AST document::

    from graphql import parse, validate

    errors = validate(schema, parse("""
        {
          human(id: NEWHOPE) {
            name
            homeTown
            friends
          }
        }
        """))

As a result, you will get a complete list of all errors that the validators has found.
In this case, we will get::

    [GraphQLError(
        'String cannot represent a non string value: NEWHOPE',
        locations=[SourceLocation(line=3, column=17)]),
     GraphQLError(
        "Cannot query field 'homeTown' on type 'Human'."
         " Did you mean 'homePlanet'?",
         locations=[SourceLocation(line=5, column=9)]),
     GraphQLError(
        "Field 'friends' of type '[Character]' must have a selection of subfields."
         "  Did you mean 'friends { ... }'?",
         locations=[SourceLocation(line=6, column=9)])]

These rules are available in the :data:`specified_rules` list and implemented in the
``graphql.validation.rules`` subpackage. Instead of the default rules,
you can also use a subset or create custom rules. The rules are
based on the :class:`graphql.validation.ValidationRule` class which is based on the
:class:`graphql.language.Visitor` class which provides a way of walking through an AST
document using the visitor pattern.
