import re

from graphql.utilities import get_introspection_query


def describe_get_introspection_query():
    def skips_all_description_fields():
        has_descriptions = re.compile(r"\bdescription\b").search

        assert has_descriptions(get_introspection_query())

        assert has_descriptions(get_introspection_query(descriptions=True))

        assert not has_descriptions(get_introspection_query(descriptions=False))

    def includes_is_repeatable_field():
        has_repeatability = re.compile(r"\bisRepeatable\b").search

        assert not has_repeatability(get_introspection_query())

        assert has_repeatability(get_introspection_query(directive_is_repeatable=True))

        assert not has_repeatability(
            get_introspection_query(directive_is_repeatable=False)
        )
