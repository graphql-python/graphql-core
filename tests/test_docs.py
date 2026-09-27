"""Test all code snippets in the documentation"""

import ast
import doctest
import importlib
import inspect
import pkgutil
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterator, List, Set, Tuple

import pytest

import graphql

from .utils import dedent

Scope = Dict[str, Any]


def get_snippets(source, indent=4):
    """Get all code snippets from a given documentation source file."""
    if not source.endswith(".rst"):  # pragma: no cover
        source += ".rst"
    source_path = Path(__file__).parents[1] / "docs" / source
    lines = open(source_path).readlines()
    snippets: List[str] = []
    snippet: List[str] = []
    snippet_start = " " * indent
    for line in lines:
        if not line.rstrip() and snippet:
            snippet.append(line)
        elif line.startswith(snippet_start):
            snippet.append(line[indent:])
        else:
            if snippet:
                snippets.append("".join(snippet).rstrip() + "\n")
                snippet = []
    if snippet:
        snippets.append("".join(snippet).rstrip() + "\n")
    return snippets


def expected_result(snippets):
    """Get and normalize expected result from snippet."""
    out = snippets.pop(0)
    assert out.startswith("ExecutionResult(")
    return " ".join(out.split()).replace("( ", "(") + "\n"


def expected_errors(snippets):
    """Get and normalize expected errors from snippet."""
    out = snippets.pop(0)
    assert out.startswith("[GraphQLError(")
    return " ".join(out.split()).replace("( ", "(").replace('" "', "")


def describe_introduction():
    def getting_started(capsys):
        intro = get_snippets("intro")
        pip_install = intro.pop(0)
        assert "pip install" in pip_install and "graphql-core" in pip_install
        poetry_install = intro.pop(0)
        assert "poetry install" in poetry_install
        create_schema = intro.pop(0)
        assert "schema = GraphQLSchema(" in create_schema
        scope: Scope = {}
        exec(create_schema, scope)
        schema = scope.get("schema")
        schema_class = scope.get("GraphQLSchema")
        assert schema and schema_class and isinstance(schema, schema_class)
        query = intro.pop(0)
        assert "graphql_sync" in query
        exec(query, scope)
        out, err = capsys.readouterr()
        assert out.startswith("ExecutionResult")
        assert not err
        expected_out = intro.pop(0)
        assert out == expected_out


def describe_usage():
    sdl = get_snippets("usage/schema")[0]
    resolvers = get_snippets("usage/resolvers")[0]

    def building_a_type_schema():
        schema = get_snippets("usage/schema")
        assert schema.pop(0) == sdl
        assert "enum Episode { NEWHOPE, EMPIRE, JEDI }" in sdl
        import_blocks = schema.pop(0)
        assert "from graphql import" in import_blocks
        assert "GraphQLObjectType" in import_blocks
        scope: Scope = {}
        exec(import_blocks, scope)
        assert "GraphQLObjectType" in scope
        build_enum = schema.pop(0)
        assert "episode_enum = " in build_enum
        exec(build_enum, scope)
        assert scope["episode_enum"].values["EMPIRE"].value == 5
        scope2 = scope.copy()
        build_enum2 = schema.pop(0)
        assert "episode_enum = " in build_enum2
        exec(build_enum2, scope2)
        assert scope["episode_enum"].values["EMPIRE"].value == 5
        scope3 = scope.copy()
        build_enum3 = schema.pop(0)
        assert "episode_enum = " in build_enum3
        exec(build_enum3, scope3)
        assert scope["episode_enum"].values["EMPIRE"].value == 5
        build_character = schema.pop(0)
        assert "character_interface = " in build_character
        exec(resolvers, scope)
        exec(build_character, scope)
        assert "character_interface" in scope
        build_human_and_droid = schema.pop(0)
        assert "human_type = " in build_human_and_droid
        assert "droid_type = " in build_human_and_droid
        exec(build_human_and_droid, scope)
        assert "human_type" in scope
        assert "droid_type" in scope
        build_query_type = schema.pop(0)
        assert "query_type = " in build_query_type
        exec(build_query_type, scope)
        assert "query_type" in scope
        define_schema = schema.pop(0)
        assert "schema = " in define_schema
        exec(define_schema, scope)

    def implementing_resolvers():
        assert "luke = dict(" in resolvers
        assert "def get_human(" in resolvers
        scope: Scope = {}
        exec(resolvers, scope)
        get_human = scope["get_human"]
        human = get_human(None, None, "1000")
        assert human["name"] == "Luke Skywalker"

    def executing_queries(capsys):
        scope: Scope = {}
        exec(resolvers, scope)
        schema = "\n".join(get_snippets("usage/schema")[1:])
        exec(schema, scope)
        queries = get_snippets("usage/queries")

        async_query = queries.pop(0)
        assert "asyncio" in async_query and "graphql_sync" not in async_query
        assert "asyncio.run" in async_query
        try:  # pragma: no cover
            from asyncio import run  # noqa: F401
        except ImportError:  # Python < 3.7
            assert "ExecutionResult" in expected_result(queries)
        else:  # pragma: no cover
            exec(async_query, scope)
            out, err = capsys.readouterr()
            assert not err
            assert "R2-D2" in out
            assert out == expected_result(queries)

        sync_query = queries.pop(0)
        assert "graphql_sync" in sync_query and "asyncio" not in sync_query
        exec(sync_query, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "Luke" in out
        assert out == expected_result(queries)

        bad_query = queries.pop(0)
        assert "homePlace" in bad_query
        exec(bad_query, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "Cannot query" in out
        assert out == expected_result(queries)

        typename_query = queries.pop(0)
        assert "__typename" in typename_query
        exec(typename_query, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "__typename" in out and "Human" in out
        assert out == expected_result(queries)

        backstory_query = queries.pop(0)
        assert "secretBackstory" in backstory_query
        exec(backstory_query, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "errors" in out and "secretBackstory" in out
        assert out == expected_result(queries)

    def using_the_sdl(capsys):
        use_sdl = get_snippets("usage/sdl")
        build_schema = use_sdl.pop(0)
        build_schema_sdl = dedent(
            build_schema.partition('build_schema("""\n')[2].partition('""")')[0]
        )
        assert build_schema_sdl == sdl.rstrip()

        scope: Scope = {}
        exec(build_schema, scope)
        schema = scope["schema"]
        assert list(schema.query_type.fields) == ["hero", "human", "droid"]
        exec(resolvers, scope)
        assert schema.query_type.fields["hero"].resolve is None
        attach_functions = use_sdl.pop(0)
        exec(attach_functions, scope)
        assert schema.query_type.fields["hero"].resolve is scope["get_hero"]
        define_enum_values = use_sdl.pop(0)
        define_episode_enum = get_snippets("usage/schema")[3]
        define_episode_enum = define_episode_enum.partition("episode_enum =")[0]
        assert "class EpisodeEnum" in define_episode_enum
        exec(define_episode_enum, scope)
        exec(define_enum_values, scope)
        assert schema.get_type("Episode").values["EMPIRE"].value == 5

        query = use_sdl.pop(0)
        assert "graphql_sync" in query and "print(result)" in query
        exec(query, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "Luke" in out and "appearsIn" in out and "EMPIRE" in out
        assert out == expected_result(use_sdl)

    def using_resolver_methods(capsys):
        scope: Scope = {}
        exec(resolvers, scope)
        build_schema = get_snippets("usage/sdl")[0]
        exec(build_schema, scope)

        methods = get_snippets("usage/methods")
        root_class = methods.pop(0)
        assert root_class.startswith("class Root:")
        assert "def human(self, info, id):" in root_class
        exec(root_class, scope)
        assert "Root" in scope

        query = methods.pop(0)
        assert "graphql_sync" in query and "Root()" in query
        exec(query, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "R2-D2" in out and "primaryFunction" in out and "Astromech" in out
        assert out == expected_result(methods)

    def using_introspection(capsys):
        introspect = get_snippets("usage/introspection")
        get_query = introspect.pop(0)
        assert "import get_introspection_query" in get_query
        assert "descriptions=True" in get_query
        scope: Scope = {}
        exec(get_query, scope)
        query = scope["query"]
        assert query.lstrip().startswith("query IntrospectionQuery")
        assert "description" in query
        get_query = introspect.pop(0)
        assert "descriptions=False" in get_query
        scope2 = scope.copy()
        exec(get_query, scope2)
        query = scope2["query"]
        assert query.lstrip().startswith("query IntrospectionQuery")
        assert "description" not in query

        exec(resolvers, scope)
        create_schema = "\n".join(get_snippets("usage/schema")[1:])
        exec(create_schema, scope)
        get_result = introspect.pop(0)
        assert "result = graphql_sync(" in get_result
        exec(get_result, scope)
        query_result = scope["introspection_query_result"]
        assert query_result.errors is None
        result = str(query_result.data)
        result = "".join(result.split())
        expected_result = introspect.pop(0)
        result = "".join(result.split())
        expected_result = "\n".join(expected_result.splitlines()[:7])
        expected_result = "".join(expected_result.split())
        assert result.startswith(expected_result)

        build_schema = introspect.pop(0)
        assert "schema = build_client_schema(" in build_schema
        scope = {"introspection_query_result": query_result}
        exec(build_schema, scope)
        schema = scope["client_schema"]
        assert list(schema.query_type.fields) == ["hero", "human", "droid"]
        print_schema = introspect.pop(0)
        scope = {"client_schema": schema}
        assert "print_schema(" in print_schema
        exec(print_schema, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "enum Episode {" in out
        assert "id: String!" in out
        assert "interface Character {" in out
        assert "type Droid implements Character {" in out
        assert "type Human implements Character {" in out
        assert '"""A character in the Star Wars Trilogy"""' in out
        assert '"""A humanoid creature in the Star Wars universe."""' in out

    def parsing_graphql():
        parser = get_snippets("usage/parser")

        parse_document = parser.pop(0)
        assert "document = parse(" in parse_document
        scope: Scope = {}
        exec(parse_document, scope)
        document = scope["document"]
        name = document.definitions[0].fields[0].name
        assert name.value == "me"
        assert str(name.loc) == "24:26"

        parse_document2 = parser.pop(0)
        assert "document = parse(" in parse_document2
        assert "..., no_location=True" in parse_document2
        parse_document = parse_document.replace('""")', '""", no_location=True)')
        scope.clear()
        exec(parse_document, scope)
        document = scope["document"]
        name = document.definitions[0].fields[0].name
        assert name.value == "me"
        assert name.loc is None

        create_document = parser.pop(0)
        assert "document = DocumentNode(" in create_document
        assert "FieldDefinitionNode(" in create_document
        assert "name=NameNode(value='me')," in create_document
        scope = {}
        exec(create_document, scope)
        assert scope["document"] == document

    def extending_a_schema(capsys):
        scope: Scope = {}
        exec(resolvers, scope)
        create_schema = "\n".join(get_snippets("usage/schema")[1:])
        exec(create_schema, scope)

        extension = get_snippets("usage/extension")
        extend_schema = extension.pop(0)
        assert "extend_schema(" in extend_schema
        exec(extend_schema, scope)
        schema = scope["schema"]
        human_type = schema.get_type("Human")
        assert "lastName" in human_type.fields
        attach_resolver = extension.pop(0)
        exec(attach_resolver, scope)
        assert human_type.fields["lastName"].resolve is scope["get_last_name"]

        query = extension.pop(0)
        assert "graphql_sync(" in query
        exec(query, scope)
        out, err = capsys.readouterr()
        assert not err
        assert "lastName" in out and "Skywalker" in out
        assert out == expected_result(extension)

    def validating_queries():
        scope: Scope = {}
        exec(resolvers, scope)
        create_schema = "\n".join(get_snippets("usage/schema")[1:])
        exec(create_schema, scope)

        validator = get_snippets("usage/validator")
        validate = validator.pop(0)
        assert "errors = validate(" in validate
        exec(validate, scope)
        errors = str(scope["errors"])
        assert errors == expected_errors(validator)


PUBLIC_PACKAGES = [
    "graphql",
    "graphql.error",
    "graphql.execution",
    "graphql.language",
    "graphql.subscription",
    "graphql.type",
    "graphql.utilities",
    "graphql.validation",
]


def public_api() -> Iterator[Tuple[str, Any]]:
    """Get all public classes and functions with their qualified names."""
    seen: Set[int] = set()
    for package_name in PUBLIC_PACKAGES:
        package = importlib.import_module(package_name)
        for name in package.__all__:
            obj = getattr(package, name)
            if not (inspect.isclass(obj) or inspect.isfunction(obj)):
                continue  # constants and type aliases cannot carry docstrings
            if not obj.__module__.startswith("graphql.") or id(obj) in seen:
                continue
            seen.add(id(obj))
            yield f"{obj.__module__}.{obj.__qualname__}", obj
            if inspect.isclass(obj):
                for attr_name, attr in vars(obj).items():
                    if attr_name.startswith("_") or not inspect.isfunction(attr):
                        continue
                    yield f"{obj.__module__}.{attr.__qualname__}", attr


def documented_params(doc: str) -> Set[str]:
    """Get the names of all parameters documented with a ``:param`` field."""
    return set(re.findall(r"^\s*:param (\w+):", doc, re.MULTILINE))


def signature_params(func: Any) -> Set[str]:
    """Get the names of all named parameters of the given function."""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover
        return set()
    return {
        name
        for name, param in signature.parameters.items()
        if name not in ("self", "cls")
        and param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
    }


def returns_value(func: Any) -> bool:
    """Check whether the given function is annotated to return a value."""
    annotation = inspect.signature(func).return_annotation
    return annotation not in (None, type(None), "None", inspect.Signature.empty)


def undocumented_attributes(cls: type) -> Iterator[str]:
    """Get the names of all public class attributes without a docstring."""
    try:
        source = textwrap.dedent(inspect.getsource(cls))
    except (OSError, TypeError):  # pragma: no cover
        return
    body = ast.parse(source).body[0].body  # type: ignore
    for index, node in enumerate(body):
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        if name.startswith("_"):
            continue
        following = body[index + 1] if index + 1 < len(body) else None
        if not isinstance(following, ast.Expr):
            yield name
            continue
        value = following.value
        # Python 3.7 parses strings as ast.Str with an "s" attribute
        if not isinstance(getattr(value, "value", getattr(value, "s", None)), str):
            yield name  # pragma: no cover


def docs_problems(name: str, obj: Any) -> Iterator[str]:
    """Get all problems with the documentation of the given API member."""
    doc = obj.__doc__
    if inspect.isclass(obj):
        doc = vars(obj).get("__doc__")
        if doc == "An enumeration.":  # pragma: no cover
            doc = None  # auto-generated before Python 3.11
        init = vars(obj).get("__init__")
        func = init if inspect.isfunction(init) else None
    else:
        func = obj
    if inspect.isclass(obj):
        for attr in undocumented_attributes(obj):
            yield f"{name}: attribute {attr}"
    if not doc or not doc.strip():
        yield f"{name}: docstring"
        return
    if ":meta private:" in doc:
        return  # internal API, only a description is required
    if func is not None:
        documented = documented_params(doc)
        expected = signature_params(func)
        for param in sorted(expected - documented):
            yield f"{name}: param {param}"
        for param in sorted(documented - expected):
            yield f"{name}: unknown param {param}"
        if not inspect.isclass(obj) and returns_value(func):
            if not re.search(r"^\s*:returns:", doc, re.MULTILINE):
                yield f"{name}: returns"
    if func is not None and ">>> " not in doc:
        yield f"{name}: example"


def all_docs_problems() -> Set[str]:
    """Get all problems with the documentation of the public API."""
    return {
        problem for name, obj in public_api() for problem in docs_problems(name, obj)
    }


def all_modules() -> List[str]:
    """Get the names of all modules in the graphql package."""
    return sorted(
        module.name for module in pkgutil.walk_packages(graphql.__path__, "graphql.")
    )


def describe_docstrings():
    def docs_problems_are_detected():
        def documented(a: int, b: int = 0, *args: Any, **kwargs: Any) -> int:
            """Add two numbers.

            :param a: the first number
            :param b: the second number
            :returns: the sum

            >>> documented(1, 2)
            3
            """
            return a + b  # pragma: no cover

        def undocumented(a: int) -> int:
            """Do nothing.

            :param c: an unknown parameter
            """
            return a  # pragma: no cover

        class Documented:
            """A class.

            :param a: the value

            >>> Documented(1).a
            1
            """

            a: int
            """The value."""

            def __init__(self, a: int):
                self.a = a

        class Undocumented:
            """A class without constructor."""

            _private: int
            b: int
            c = 0

        def internal(a: int) -> int:
            """Do something internal.

            :meta private:
            """
            return a  # pragma: no cover

        assert not list(docs_problems("documented", documented))
        assert Documented(1).a == 1
        assert not list(docs_problems("Documented", Documented))
        assert list(docs_problems("undocumented", undocumented)) == [
            "undocumented: param a",
            "undocumented: unknown param c",
            "undocumented: returns",
            "undocumented: example",
        ]
        assert list(docs_problems("Undocumented", Undocumented)) == [
            "Undocumented: attribute b"
        ]
        assert not list(docs_problems("internal", internal))
        assert list(docs_problems("undocumented", lambda: None)) == [
            "undocumented: docstring"
        ]

    def public_api_is_documented():
        problems = all_docs_problems()
        assert not problems, "Undocumented:\n" + "\n".join(sorted(problems))

    @pytest.mark.parametrize("module_name", all_modules())
    def doctests_pass(module_name):
        module = importlib.import_module(module_name)
        finder = doctest.DocTestFinder(exclude_empty=True)
        runner = doctest.DocTestRunner(
            optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
        )
        for test in finder.find(module, module_name):
            runner.run(test)
        results = runner.summarize(verbose=False)
        assert not results.failed
