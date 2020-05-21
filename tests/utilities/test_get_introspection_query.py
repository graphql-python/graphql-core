import re

from graphql.utilities import get_introspection_query


def describe_get_introspection_query():
    def skips_all_description_fields():
        has_descriptions = re.compile(r"\bdescription\b").search

        assert has_descriptions(get_introspection_query())

        assert has_descriptions(get_introspection_query(descriptions=True))

        assert not has_descriptions(get_introspection_query(descriptions=False))

    def includes_is_repeatable_field_on_directives():
        has_repeatability = re.compile(r"\bisRepeatable\b").search

        assert not has_repeatability(get_introspection_query())

        assert has_repeatability(get_introspection_query(directive_is_repeatable=True))

        assert not has_repeatability(
            get_introspection_query(directive_is_repeatable=False)
        )

    def includes_description_field_on_schema():
        all_descriptions = re.compile(r"\bdescription\b").findall

        assert len(all_descriptions(get_introspection_query())) == 5

        assert (
            len(all_descriptions(get_introspection_query(schema_description=False)))
            == 5
        )

        assert (
            len(all_descriptions(get_introspection_query(schema_description=True))) == 6
        )

        assert not all_descriptions(
            get_introspection_query(descriptions=False, schema_description=True)
        )

    def includes_specified_by_url_field():
        all_specified_by_urls = re.compile(r"\bspecifiedByUrl\b").findall

        assert not all_specified_by_urls(get_introspection_query())

        assert not all_specified_by_urls(
            get_introspection_query(specified_by_url=False)
        )

        assert (
            len(all_specified_by_urls(get_introspection_query(specified_by_url=True)))
            == 1
        )
