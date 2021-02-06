from typing import List

from graphql.error import GraphQLError
from graphql.language import parse, Source
from graphql.validation import validate

from .star_wars_schema import star_wars_schema


def validation_errors(query: str) -> List[GraphQLError]:
    """Helper function to test a query and the expected response."""
    source = Source(query, "StarWars.graphql")
    ast = parse(source)
    return validate(star_wars_schema, ast)


def describe_star_wars_validation_tests():
    def describe_basic_queries():
        def validates_a_complex_but_valid_query():
            query = """
                query NestedQueryWithFragment {
                  hero {
                    ...NameAndAppearances
                    friends {
                      ...NameAndAppearances
                      friends {
                        ...NameAndAppearances
                      }
                    }
                  }
                }

                fragment NameAndAppearances on Character {
                  name
                  appearsIn
                }
                """
            assert not validation_errors(query)

        def notes_that_non_existent_fields_are_invalid():
            query = """
                query HeroSpaceshipQuery {
                  hero {
                    favoriteSpaceship
                  }
                }
                """
            assert validation_errors(query)

        def requires_fields_on_object():
            query = """
                query HeroNoFieldsQuery {
                  hero
                }
                """
            assert validation_errors(query)

        def disallows_fields_on_scalars():
            query = """
                query HeroFieldsOnScalarQuery {
                  hero {
                    name {
                      firstCharacterOfName
                    }
                  }
                }
                """
            assert validation_errors(query)

        def disallows_object_fields_on_interfaces():
            query = """
                query DroidFieldOnCharacter {
                  hero {
                    name
                    primaryFunction
                  }
                }
                """
            assert validation_errors(query)

        def allows_object_fields_in_fragments():
            query = """
                query DroidFieldInFragment {
                  hero {
                    name
                    ...DroidFields
                  }
                }

                fragment DroidFields on Droid {
                  primaryFunction
                }
                """
            assert not validation_errors(query)

        def allows_object_fields_in_inline_fragments():
            query = """
                query DroidFieldInFragment {
                  hero {
                    name
                    ...DroidFields
                  }
                }

                fragment DroidFields on Droid {
                    primaryFunction
                }
                """
            assert not validation_errors(query)
