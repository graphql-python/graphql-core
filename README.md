# GraphQL-core 3

GraphQL-core 3 is a Python 3.6+ port of [GraphQL.js](https://github.com/graphql/graphql-js),
the JavaScript reference implementation for [GraphQL](https://graphql.org/),
a query language for APIs created by Facebook.

[![PyPI version](https://badge.fury.io/py/graphql-core.svg)](https://badge.fury.io/py/graphql-core)
[![Documentation Status](https://readthedocs.org/projects/graphql-core-3/badge/)](https://graphql-core-3.readthedocs.io)
[![Build Status](https://travis-ci.com/graphql-python/graphql-core.svg?branch=main)](https://travis-ci.com/graphql-python/graphql-core)
[![Coverage Status](https://codecov.io/gh/graphql-python/graphql-core/branch/main/graph/badge.svg)](https://codecov.io/gh/graphql-python/graphql-core)
[![Dependency Updates](https://pyup.io/repos/github/graphql-python/graphql-core/shield.svg)](https://pyup.io/repos/github/graphql-python/graphql-core/)
[![Python 3 Status](https://pyup.io/repos/github/graphql-python/graphql-core/python-3-shield.svg)](https://pyup.io/repos/github/graphql-python/graphql-core/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

The current version 3.1.7 of GraphQL-core is up-to-date with GraphQL.js version 15.8.0.

An extensive test suite with over 2200 unit tests and 100% coverage comprises a
replication of the complete test suite of GraphQL.js, making sure this port is
reliable and compatible with GraphQL.js.


## Documentation

A more detailed documentation for GraphQL-core 3 can be found at
[graphql-core-3.readthedocs.io](https://graphql-core-3.readthedocs.io/).

The documentation for GraphQL.js can be found at [graphql.org/graphql-js/](https://graphql.org/graphql-js/).

The documentation for GraphQL itself can be found at [graphql.org](https://graphql.org/).

There will be also [blog articles](https://cito.github.io/tags/graphql/) with more usage
examples.


## Getting started

A general overview of GraphQL is available in the
[README](https://github.com/graphql/graphql-spec/blob/main/README.md) for the
[Specification for GraphQL](https://github.com/graphql/graphql-spec). That overview
describes a simple set of GraphQL examples that exist as [tests](tests) in this
repository. A good way to get started with this repository is to walk through that
README and the corresponding tests in parallel.


## Installation

GraphQL-core 3 can be installed from PyPI using the built-in pip command:

    python -m pip install graphql-core

You can also use [pipenv](https://docs.pipenv.org/) for installation in a
virtual environment:

    pipenv install graphql-core


## Usage

GraphQL-core provides two important capabilities: building a type schema and
serving queries against that type schema.

First, build a GraphQL type schema which maps to your codebase:

```python
from graphql import (
    GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString)

schema = GraphQLSchema(
    query=GraphQLObjectType(
        name='RootQueryType',
        fields={
            'hello': GraphQLField(
                GraphQLString,
                resolve=lambda obj, info: 'world')
        }))
```

This defines a simple schema, with one type and one field, that resolves to a fixed
value. The `resolve` function can return a value, a co-routine object or a list of
these. It takes two positional arguments; the first one provides the root or the
resolved parent field, the second one provides a `GraphQLResolveInfo` object which
contains information about the execution state of the query, including a `context`
attribute holding per-request state such as authentication information or database
session. Any GraphQL arguments are passed to the `resolve` functions as individual
keyword arguments.

Note that the signature of the resolver functions is a bit different in GraphQL.js,
where the context is passed separately and arguments are passed as a single object.
Also note that GraphQL fields must be passed as a `GraphQLField` object explicitly.
Similarly, GraphQL arguments must be passed as `GraphQLArgument` objects.

A more complex example is included in the top-level [tests](tests) directory.

Then, serve the result of a query against that type schema.

```python
from graphql import graphql_sync

query = '{ hello }'

print(graphql_sync(schema, query))
```

This runs a query fetching the one field defined, and then prints the result:

```python
ExecutionResult(data={'hello': 'world'}, errors=None)
```

The `graphql_sync` function will first ensure the query is syntactically and
semantically valid before executing it, reporting errors otherwise.

```python
from graphql import graphql_sync

query = '{ BoyHowdy }'

print(graphql_sync(schema, query))
```

Because we queried a non-existing field, we will get the following result:

```python
ExecutionResult(data=None, errors=[GraphQLError(
    "Cannot query field 'BoyHowdy' on type 'RootQueryType'.",
    locations=[SourceLocation(line=1, column=3)])])
```

The `graphql_sync` function assumes that all resolvers return values synchronously. By
using coroutines as resolvers, you can also create results in an asynchronous fashion
with the `graphql` function.

```python
import asyncio
from graphql import (
    graphql, GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString)


async def resolve_hello(obj, info):
    await asyncio.sleep(3)
    return 'world'

schema = GraphQLSchema(
    query=GraphQLObjectType(
        name='RootQueryType',
        fields={
            'hello': GraphQLField(
                GraphQLString,
                resolve=resolve_hello)
        }))


async def main():
    query = '{ hello }'
    print('Fetching the result...')
    result = await graphql(schema, query)
    print(result)


asyncio.run(main())
```


## Goals and restrictions

GraphQL-core tries to reproduce the code of the reference implementation GraphQL.js
in Python as closely as possible and to stay up-to-date with the latest development of
GraphQL.js.

GraphQL-core 3 (formerly known as GraphQL-core-next) has been created as a modern
alternative to [GraphQL-core 2](https://github.com/graphql-python/graphql-core-legacy),
a prior work by Syrus Akbary, based on an older version of GraphQL.js and also
targeting older Python versions. Some parts of GraphQL-core 3 have been inspired by
GraphQL-core 2 or directly taken over with only slight modifications, but most of the
code has been re-implemented from scratch, replicating the latest code in GraphQL.js
very closely and adding type hints for Python.

Design goals for the GraphQL-core 3 library are:

* to be a simple, cruft-free, state-of-the-art implementation of GraphQL using current
  library and language versions
* to be very close to the GraphQL.js reference implementation, while still using a
  Pythonic API and code style
* to make extensive use of Python type hints, similar to how GraphQL.js makes uses Flow
* to use [black](https://github.com/ambv/black) for automatic code formatting
* to replicate the complete Mocha-based test suite of GraphQL.js using
  [pytest](https://docs.pytest.org/)

Some restrictions (mostly in line with the design goals):

* requires Python 3.6 or newer
* does not support some already deprecated methods and options of GraphQL.js
* supports asynchronous operations only via async.io
  (does not support the additional executors in GraphQL-core)


## Integration with other libraries and roadmap

* [Graphene](http://graphene-python.org/) is a more high-level framework for building
  GraphQL APIs in Python, and there is already a whole ecosystem of libraries, server
  integrations and tools built on top of Graphene. Most of this Graphene ecosystem has
  also been created by Syrus Akbary, who meanwhile has handed over the maintenance
  and future development to members of the GraphQL-Python community.

  The current version 2 of Graphene is using Graphql-core 2 as core library for much of
  the heavy lifting. Note that Graphene 2 is not compatible with GraphQL-core 3.
  The  new version 3 of Graphene will use GraphQL-core 3 instead of GraphQL-core 2.

* [Ariadne](https://github.com/mirumee/ariadne) is a Python library for implementing
  GraphQL servers using schema-first approach created by Mirumee Software.

  Ariadne is already using GraphQL-core 3 as its GraphQL implementation.

* [Strawberry](https://github.com/strawberry-graphql/strawberry), created by Patrick
  Arminio, is a new GraphQL library for Python 3, inspired by dataclasses,
  that is also using GraphQL-core 3 as underpinning.


## Changelog

Changes are tracked as
[GitHub releases](https://github.com/graphql-python/graphql-core/releases).


## Credits and history

The GraphQL-core 3 library
* has been created and is maintained by Christoph Zwerschke
* uses ideas and code from GraphQL-core 2, a prior work by Syrus Akbary
* is a Python port of GraphQL.js which has been developed by Lee Byron and others
  at Facebook, Inc. and is now maintained
  by the [GraphQL foundation](https://gql.foundation/join/)

Please watch the recording of Lee Byron's short keynote on the
[history of GraphQL](https://www.youtube.com/watch?v=VjHWkBr3tjI)
at the open source leadership summit 2019 to better understand
how and why GraphQL was created at Facebook and then became open sourced
and ported to many different programming languages.


## License

GraphQL-core 3 is
[MIT-licensed](./LICENSE),
just like GraphQL.js.
