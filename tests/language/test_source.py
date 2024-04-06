from __future__ import annotations

import weakref
from typing import cast

import pytest
from graphql.language import Source, SourceLocation

from ..utils import dedent


def describe_source():
    def accepts_body_and_name():
        source = Source("foo", "bar")
        assert source.body == "foo"
        assert source.name == "bar"

    def accepts_location_offset():
        location_offset = SourceLocation(2, 3)
        source = Source("", "", location_offset)
        assert source.location_offset is location_offset

    def accepts_tuple_as_location_offset():
        # noinspection PyTypeChecker
        source = Source("", "", (2, 3))  # type: ignore
        assert isinstance(source.location_offset, SourceLocation)
        assert source.location_offset == (2, 3)

    def uses_default_arguments():
        source = Source("")
        assert source.name == "GraphQL request"
        assert isinstance(source.location_offset, SourceLocation)
        assert source.location_offset == (1, 1)

    def can_get_location():
        body = dedent(
            """
            line 1
            line 2
            line 3
            """
        )
        source = Source(body)
        assert source.body == body
        location = source.get_location(body.find("2"))
        assert isinstance(location, SourceLocation)
        assert location == (2, 6)

    def can_be_stringified():
        source = Source("")
        assert str(source) == "<Source name='GraphQL request'>"

        source = Source("", "Custom source name")
        assert str(source) == "<Source name='Custom source name'>"

    def can_be_compared():
        source = Source("foo")
        assert source == source  # noqa: PLR0124
        assert not source != source  # noqa: PLR0124, SIM202
        assert source == "foo"
        assert not source != "foo"  # noqa: SIM202
        same_source = Source("foo")
        assert source == same_source
        assert not source != same_source  # noqa: SIM202
        different_source = Source("bar")
        assert not source == different_source  # noqa: SIM201
        assert source != different_source
        assert not source == "bar"  # noqa: SIM201
        assert source != "bar"

    def can_create_weak_reference():
        source = Source("foo")
        ref = weakref.ref(source)
        assert ref() is source

    def can_create_custom_attribute():
        node = Source("foo")
        node.custom = "bar"  # type: ignore
        assert node.custom == "bar"  # type: ignore

    def rejects_invalid_location_offset():
        def create_source(location_offset: tuple[int, int]) -> Source:
            return Source("", "", cast(SourceLocation, location_offset))

        with pytest.raises(TypeError):
            create_source(None)  # type: ignore
        with pytest.raises(TypeError):
            create_source(1)  # type: ignore
        with pytest.raises(TypeError):
            create_source((1,))  # type: ignore
        with pytest.raises(TypeError):
            create_source((1, 2, 3))  # type: ignore

        with pytest.raises(
            ValueError,
            match="line in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((0, 1))
        with pytest.raises(
            ValueError,
            match="line in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((-1, 1))

        with pytest.raises(
            ValueError,
            match="column in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((1, 0))
        with pytest.raises(
            ValueError,
            match="column in location_offset is 1-indexed and must be positive\\.",
        ):
            create_source((1, -1))
