Differences from GraphQL.js
===========================

The goal of GraphQL-core 3 is to be a faithful replication of `GraphQL.js`_,  the JavaScript reference implementation for GraphQL, in Python 3, and to keep it aligned and up to date with the ongoing development of GraphQL.js. Therefore, we strive to be as compatible as possible to the original JavaScript library, sometimes at the cost of being less Pythonic than other libraries written particularly for Python. We also avoid incorporating additional features that do not exist in the JavaScript library, in order to keep the task of maintaining the Python code and keeping it in line with the JavaScript code manageable. The preferred way of getting new features into GraphQL-core is to propose and discuss them on the `GraphQL.js issue tracker`_ first, try to get them included into GraphQL.js, and from there ported to GraphQL-core.

.. _GraphQL.js: https://github.com/graphql/graphql-js
.. _GraphQL.js issue tracker: https://github.com/graphql/graphql-js/issues
.. _Graphene: https://graphene-python.org/

.. currentmodule:: graphql

Having said this, in a few places we allowed the API to be a bit more Pythonic than the direct equivalent would have been. We also added a few features that do not exist in the JavaScript library, mostly to support existing higher level libraries such as Graphene_ and the different naming conventions in Python. The most notable differences are the following:


Direct attribute access in GraphQL types
----------------------------------------

You can access

* the **fields** of GraphQLObjectTypes, GraphQLInterfaceTypes and GraphQLInputObjectTypes,
* the **interfaces** of GraphQLObjectTypes,
* the **types** of GraphQLUnionTypes,
* the **values** of GraphQLEnumTypes and
* the **query**, **mutation**, **subscription** and **type_map** of GraphQLSchemas

directly as attributes, instead of using getters.

For example, to get the fields of a GraphQLObjectType ``obj``, you write ``obj.fields`` instead of ``obj.getFields()``.


Arguments, fields and values are dictionaries
---------------------------------------------

* The **arguments** of GraphQLDirectives and GraphQLFields,
* the **fields** of GraphQLObjectTypes, GraphQLInterfaceTypes and GraphQLInputObjectTypes, and
* the **values** of GraphQLEnumTypes

are always Python dictionaries in GraphQL-core, while they are returned as Arrays in GraphQL.js. Also, the values of these dictionaries do not have ``name`` attributes, since the names are already used as the keys of these dictionaries.


Shorthand notation for creating GraphQL types
---------------------------------------------

The following shorthand notations are possible:

* Where you need to pass a GraphQLArgumentMap, i.e. a dictionary with names as keys and GraphQLArguments as values, you can also pass GraphQLInputTypes as values. The GraphQLInputTypes are then automatically wrapped into GraphQLArguments.
* Where you need to pass a GraphQLFieldMap, i.e. a dictionary with names as keys and GraphQLFields as values, you can also pass GraphQLOutputTypes as values. The GraphQLOutputTypes are then automatically wrapped into GraphQLFields.
* Where you need to pass a GraphQLInputFieldMap, i.e. a dictionary with names as keys and GraphQLInputFields as values, you can also pass GraphQLInputTypes as values. The GraphQLInputTypes are then automatically wrapped into GraphQLInputFields.
* Where you need to pass a GraphQLEnumValueMap, i.e. a dictionary with names as keys and GraphQLEnumValues as values, you can pass any other Python objects as values. These will be automatically wrapped into GraphQLEnumValues. You can also pass a Python Enum type as GraphQLEnumValueMap.


.. currentmodule:: graphql.type

Custom output names of arguments and input fields
-------------------------------------------------

You can pass a custom ``out_name`` argument to :class:`GraphQLArgument` and :class:`GraphQLInputField` that allows using JavaScript naming conventions (camelCase) on ingress and Python naming conventions (snake_case) on egress. This feature is used by Graphene.


Custom output types of input object types
-----------------------------------------

You can also pass a custom ``out_type`` argument to :class:`GraphQLInputObjectType` that allows conversion to any Python type on egress instead of conversion to a dictionary, which is the default. This is used to support the container feature of Graphene InputObjectTypes.


.. currentmodule:: graphql.execution

Custom middleware
-----------------

The :func:`execute` function takes an additional ``middleware`` argument which must be a sequence of middleware functions or a :class:`MiddlewareManager` object. This feature is used by Graphene to affect the evaluation of fields using custom middleware. There has been a `request <https://github.com/graphql/graphql-js/issues/1516>`_ to add this to GraphQL.js as well, but so far this feature only exists in GraphQL-core.


Custom execution context
------------------------

The :func:`execute` function takes an additional ``execution_context_class`` argument which allows specifying a custom execution context class instead of the default :class:`ExecutionContext` used by GraphQL-core.


.. currentmodule:: graphql

Registering special types for descriptions
------------------------------------------

Normally, descriptions for GraphQL types must be strings. However, sometimes you may want to use other kinds of objects which are not strings, but are only resolved to strings at runtime. This is possible if you register the classes of such objects with :func:`pyutils.register_description`.


If you notice any other important differences, please let us know so that they can be either removed or listed here.
