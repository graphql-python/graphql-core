"""Test all code snippets in the documentation"""

from pathlib import Path
from typing import Any, Dict, List

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
        pipenv_install = intro.pop(0)
        assert "pipenv install" in pipenv_install and "graphql-core" in pipenv_install
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
        assert build_schema_sdl == sdl

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
