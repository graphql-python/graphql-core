from pytest import mark

from graphql import graphql, graphql_sync

from .star_wars_schema import star_wars_schema as schema


def describe_star_wars_query_tests():
    def describe_basic_queries():
        @mark.asyncio
        async def correctly_identifies_r2_d2_as_hero_of_the_star_wars_saga():
            source = """
                query HeroNameQuery {
                  hero {
                    name
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == ({"hero": {"name": "R2-D2"}}, None)

        @mark.asyncio
        async def accepts_positional_arguments_to_graphql():
            source = """
                query HeroNameQuery {
                  hero {
                    name
                  }
                }
                """
            result = await graphql(schema, source)
            assert result == ({"hero": {"name": "R2-D2"}}, None)

            sync_result = graphql_sync(schema, source)
            assert sync_result == result

        @mark.asyncio
        async def allows_us_to_query_for_the_id_and_friends_of_r2_d2():
            source = """
                query HeroNameAndFriendsQuery {
                  hero {
                    id
                    name
                    friends {
                      name
                    }
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {
                    "hero": {
                        "id": "2001",
                        "name": "R2-D2",
                        "friends": [
                            {"name": "Luke Skywalker"},
                            {"name": "Han Solo"},
                            {"name": "Leia Organa"},
                        ],
                    }
                },
                None,
            )

    def describe_nested_queries():
        @mark.asyncio
        async def allows_us_to_query_for_the_friends_of_friends_of_r2_d2():
            source = """
                query NestedQuery {
                  hero {
                    name
                    friends {
                      name
                      appearsIn
                      friends {
                        name
                      }
                    }
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {
                    "hero": {
                        "name": "R2-D2",
                        "friends": [
                            {
                                "name": "Luke Skywalker",
                                "appearsIn": ["NEW_HOPE", "EMPIRE", "JEDI"],
                                "friends": [
                                    {"name": "Han Solo"},
                                    {"name": "Leia Organa"},
                                    {"name": "C-3PO"},
                                    {"name": "R2-D2"},
                                ],
                            },
                            {
                                "name": "Han Solo",
                                "appearsIn": ["NEW_HOPE", "EMPIRE", "JEDI"],
                                "friends": [
                                    {"name": "Luke Skywalker"},
                                    {"name": "Leia Organa"},
                                    {"name": "R2-D2"},
                                ],
                            },
                            {
                                "name": "Leia Organa",
                                "appearsIn": ["NEW_HOPE", "EMPIRE", "JEDI"],
                                "friends": [
                                    {"name": "Luke Skywalker"},
                                    {"name": "Han Solo"},
                                    {"name": "C-3PO"},
                                    {"name": "R2-D2"},
                                ],
                            },
                        ],
                    }
                },
                None,
            )

    def describe_using_ids_and_query_parameters_to_refetch_objects():
        @mark.asyncio
        async def allows_us_to_query_for_r2_d2_directly_using_his_id():
            source = """
                query {
                  droid(id: "2001") {
                    name
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == ({"droid": {"name": "R2-D2"}}, None)

        @mark.asyncio
        async def allows_us_to_query_characters_directly_using_their_id():
            source = """
                query FetchLukeAndC3POQuery {
                  human(id: "1000") {
                    name
                  }
                  droid(id: "2000") {
                    name
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {"human": {"name": "Luke Skywalker"}, "droid": {"name": "C-3PO"}},
                None,
            )

        @mark.asyncio
        async def allows_creating_a_generic_query_to_fetch_luke_using_his_id():
            source = """
                query FetchSomeIDQuery($someId: String!) {
                  human(id: $someId) {
                    name
                  }
                }
                """
            variable_values = {"someId": "1000"}
            result = await graphql(
                schema=schema, source=source, variable_values=variable_values
            )
            assert result == ({"human": {"name": "Luke Skywalker"}}, None)

        @mark.asyncio
        async def allows_creating_a_generic_query_to_fetch_han_using_his_id():
            source = """
                query FetchSomeIDQuery($someId: String!) {
                  human(id: $someId) {
                    name
                  }
                }
                """
            variable_values = {"someId": "1002"}
            result = await graphql(
                schema=schema, source=source, variable_values=variable_values
            )
            assert result == ({"human": {"name": "Han Solo"}}, None)

        @mark.asyncio
        async def generic_query_that_gets_null_back_when_passed_invalid_id():
            source = """
                query humanQuery($id: String!) {
                  human(id: $id) {
                    name
                  }
                }
                """
            variable_values = {"id": "not a valid id"}
            result = await graphql(
                schema=schema, source=source, variable_values=variable_values
            )
            assert result == ({"human": None}, None)

    def describe_using_aliases_to_change_the_key_in_the_response():
        @mark.asyncio
        async def allows_us_to_query_for_luke_changing_his_key_with_an_alias():
            source = """
                query FetchLukeAliased {
                  luke: human(id: "1000") {
                    name
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == ({"luke": {"name": "Luke Skywalker"}}, None)

        @mark.asyncio
        async def query_for_luke_and_leia_using_two_root_fields_and_an_alias():
            source = """
                query FetchLukeAndLeiaAliased {
                  luke: human(id: "1000") {
                    name
                  }
                  leia: human(id: "1003") {
                    name
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {"luke": {"name": "Luke Skywalker"}, "leia": {"name": "Leia Organa"}},
                None,
            )

    def describe_uses_fragments_to_express_more_complex_queries():
        @mark.asyncio
        async def allows_us_to_query_using_duplicated_content():
            source = """
                query DuplicateFields {
                  luke: human(id: "1000") {
                    name
                    homePlanet
                  }
                  leia: human(id: "1003") {
                    name
                    homePlanet
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {
                    "luke": {"name": "Luke Skywalker", "homePlanet": "Tatooine"},
                    "leia": {"name": "Leia Organa", "homePlanet": "Alderaan"},
                },
                None,
            )

        @mark.asyncio
        async def allows_us_to_use_a_fragment_to_avoid_duplicating_content():
            source = """
                query UseFragment {
                  luke: human(id: "1000") {
                    ...HumanFragment
                  }
                  leia: human(id: "1003") {
                    ...HumanFragment
                  }
                }
                fragment HumanFragment on Human {
                  name
                  homePlanet
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {
                    "luke": {"name": "Luke Skywalker", "homePlanet": "Tatooine"},
                    "leia": {"name": "Leia Organa", "homePlanet": "Alderaan"},
                },
                None,
            )

    def describe_using_typename_to_find_the_type_of_an_object():
        @mark.asyncio
        async def allows_us_to_verify_that_r2_d2_is_a_droid():
            source = """
                query CheckTypeOfR2 {
                  hero {
                    __typename
                    name
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == ({"hero": {"__typename": "Droid", "name": "R2-D2"}}, None)

        @mark.asyncio
        async def allows_us_to_verify_that_luke_is_a_human():
            source = """
                query CheckTypeOfLuke {
                  hero(episode: EMPIRE) {
                    __typename
                    name
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {"hero": {"__typename": "Human", "name": "Luke Skywalker"}},
                None,
            )

    def describe_reporting_errors_raised_in_resolvers():
        @mark.asyncio
        async def correctly_reports_error_on_accessing_secret_backstory():
            source = """
                query HeroNameQuery {
                  hero {
                    name
                    secretBackstory
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {"hero": {"name": "R2-D2", "secretBackstory": None}},
                [
                    {
                        "message": "secretBackstory is secret.",
                        "locations": [(5, 21)],
                        "path": ["hero", "secretBackstory"],
                    }
                ],
            )

        @mark.asyncio
        async def correctly_reports_error_on_accessing_backstory_in_a_list():
            source = """
                query HeroNameQuery {
                  hero {
                    name
                    friends {
                      name
                      secretBackstory
                    }
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {
                    "hero": {
                        "name": "R2-D2",
                        "friends": [
                            {"name": "Luke Skywalker", "secretBackstory": None},
                            {"name": "Han Solo", "secretBackstory": None},
                            {"name": "Leia Organa", "secretBackstory": None},
                        ],
                    }
                },
                [
                    {
                        "message": "secretBackstory is secret.",
                        "locations": [(7, 23)],
                        "path": ["hero", "friends", 0, "secretBackstory"],
                    },
                    {
                        "message": "secretBackstory is secret.",
                        "locations": [(7, 23)],
                        "path": ["hero", "friends", 1, "secretBackstory"],
                    },
                    {
                        "message": "secretBackstory is secret.",
                        "locations": [(7, 23)],
                        "path": ["hero", "friends", 2, "secretBackstory"],
                    },
                ],
            )

        @mark.asyncio
        async def correctly_reports_error_on_accessing_through_an_alias():
            source = """
                query HeroNameQuery {
                  mainHero: hero {
                    name
                    story: secretBackstory
                  }
                }
                """
            result = await graphql(schema=schema, source=source)
            assert result == (
                {"mainHero": {"name": "R2-D2", "story": None}},
                [
                    {
                        "message": "secretBackstory is secret.",
                        "locations": [(5, 21)],
                        "path": ["mainHero", "story"],
                    }
                ],
            )
