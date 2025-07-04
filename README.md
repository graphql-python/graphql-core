# GraphQL-core 3

GraphQL-core 3 is a Python 3.6+ port of [GraphQL.js](https://github.com/graphql/graphql-js),
the JavaScript reference implementation for [GraphQL](https://graphql.org/),
a query language for APIs created by Facebook.

[![PyPI version](https://badge.fury.io/py/graphql-core.svg)](https://badge.fury.io/py/graphql-core)
[![Documentation Status](https://readthedocs.org/projects/graphql-core-3/badge/)](https://graphql-core-3.readthedocs.io)
[![Test Status](https://github.com/graphql-python/graphql-core/actions/workflows/test.yml/badge.svg)](https://github.com/graphql-python/graphql-core/actions/workflows/test.yml)
[![Lint Status](https://github.com/graphql-python/graphql-core/actions/workflows/lint.yml/badge.svg)](https://github.com/graphql-python/graphql-core/actions/workflows/lint.yml)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/graphql-python/graphql-core)
[![Code style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

An extensive test suite with over 2500 unit tests and 100% coverage replicates the
complete test suite of GraphQL.js, ensuring that this port is reliable and compatible
with GraphQL.js.

The current stable version 3.2.6 of GraphQL-core is up-to-date with GraphQL.js
version 16.8.2 and supports Python versions 3.6 to 3.13.

You can also try out the latest alpha version 3.3.0a9 of GraphQL-core,
which is up-to-date with GraphQL.js version 17.0.0a3.
Please note that this new minor version of GraphQL-core does not support
Python 3.6 anymore.

Note that for various reasons, GraphQL-core does not use SemVer like GraphQL.js.
Changes in the major version of GraphQL.js are reflected in the minor version of
GraphQL-core instead. This means there can be breaking changes in the API
when the minor version changes, and only patch releases are fully backward compatible.
Therefore, we recommend using something like `~= 3.2.0` as the version specifier
when including GraphQL-core as a dependency.

## Documentation

More detailed documentation for GraphQL-core 3 can be found at
[graphql-core-3.readthedocs.io](https://graphql-core-3.readthedocs.io/).

The documentation for GraphQL.js can be found at [graphql.org/graphql-js/](https://graphql.org/graphql-js/).

The documentation for GraphQL itself can be found at [graphql.org](https://graphql.org/).

There will be also [blog articles](https://cito.github.io/tags/graphql/) with more usage
examples.


## Getting started

A general overview of GraphQL is available in the
[README](https://github.com/graphql/graphql-spec/blob/main/README.md) for the
[Specification for GraphQL](https://github.com/graphql/graphql-spec). This overview
includes a simple set of GraphQL examples that are also available as [tests](tests)
in this repository. A good way to get started with this repository is to walk through
that README and the corresponding tests in parallel.


## Installation

GraphQL-core 3 can be installed from PyPI using the built-in pip command:

    python -m pip install graphql-core

You can also use [poetry](https://github.com/python-poetry/poetry) for installation in a
virtual environment:

    poetry install


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

source = '{ hello }'

print(graphql_sync(schema, source))
```

This runs a query fetching the one field defined, and then prints the result:

```python
ExecutionResult(data={'hello': 'world'}, errors=None)
```

The `graphql_sync` function will first ensure the query is syntactically and
semantically valid before executing it, reporting errors otherwise.

```python
from graphql import graphql_sync

source = '{ BoyHowdy }'

print(graphql_sync(schema, source))
```

Because we queried a non-existing field, we will get the following result:

```python
ExecutionResult(data=None, errors=[GraphQLError(
    "Cannot query field 'BoyHowdy' on type 'RootQueryType'.",
    locations=[SourceLocation(line=1, column=3)])])
```

The `graphql_sync` function assumes that all resolvers return values synchronously.
By  using coroutines as resolvers, you can also create results in an asynchronous
fashion with the `graphql` function.

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

GraphQL-core aims to reproduce the code of the reference implementation GraphQL.js
in Python as closely as possible while staying up-to-date with the latest development
of GraphQL.js.

GraphQL-core 3 (formerly known as GraphQL-core-next) was created as a modern
alternative to [GraphQL-core 2](https://github.com/graphql-python/graphql-core-legacy),
a prior work by Syrus Akbary based on an older version of GraphQL.js that still
supported legacy Python versions. While some parts of GraphQL-core 3 were inspired by
GraphQL-core 2 or directly taken over with slight modifications, most of the code has
been re-implemented from scratch. This re-implementation closely replicates the latest
code in GraphQL.js and adds type hints for Python.

Design goals for the GraphQL-core 3 library were:

* to be a simple, cruft-free, state-of-the-art GraphQL implementation for current
  Python versions
* to be very close to the GraphQL.js reference implementation, while still providing
  a Pythonic API and code style
* to make extensive use of Python type hints, similar to how GraphQL.js used Flow
  (and is now using TypeScript)
* to use [black](https://github.com/ambv/black) to achieve a consistent code style
  while saving time and mental energy for more important matters
  (we are now using [ruff](https://github.com/astral-sh/ruff) instead)
* to replicate the complete Mocha-based test suite of GraphQL.js
  using [pytest](https://docs.pytest.org/)
  with [pytest-describe](https://pypi.org/project/pytest-describe/)

Some restrictions (mostly in line with the design goals):

* requires Python 3.6 or newer (Python 3.7 and newer in latest version)
* does not support some already deprecated methods and options of GraphQL.js
* supports asynchronous operations only via async.io
  (does not support the additional executors in GraphQL-core)

Note that meanwhile we are using the amazing [ruff](https://docs.astral.sh/ruff/) tool
to both format and check the code of GraphQL-core 3,
in addition to using [mypy](https://mypy-lang.org/) as type checker.


## Integration with other libraries and roadmap

* [Graphene](http://graphene-python.org/) is a more high-level framework for building
  GraphQL APIs in Python, and there is already a whole ecosystem of libraries, server
  integrations and tools built on top of Graphene. Most of this Graphene ecosystem has
  also been created by Syrus Akbary, who meanwhile has handed over the maintenance
  and future development to members of the GraphQL-Python community.

  Graphene 3 is now using Graphql-core 3 as core library for much of the heavy lifting.

* [Ariadne](https://github.com/mirumee/ariadne) is a Python library for implementing
  GraphQL servers using schema-first approach created by Mirumee Software.

  Ariadne is also using GraphQL-core 3 as its GraphQL implementation.

* [Strawberry](https://github.com/strawberry-graphql/strawberry), created by Patrick
  Arminio, is a new GraphQL library for Python 3, inspired by dataclasses,
  that is also using GraphQL-core 3 as underpinning.

* [Typed GraphQL](https://github.com/willemt/typed-graphql), thin layer over GraphQL-core that uses native Python types for creating GraphQL schemas.


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
