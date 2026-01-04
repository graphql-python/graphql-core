from __future__ import annotations

import weakref
from copy import copy, deepcopy

from graphql.language import Location, NameNode, Node, Source, Token, TokenKind
from graphql.pyutils import inspect


class SampleTestNode(Node):
    alpha: int
    beta: int


class SampleNamedNode(Node):
    foo: str | None = None
    name: NameNode | None = None


def make_loc(start: int = 1, end: int = 3) -> Location:
    """Create a Location for testing with the given start/end offsets."""
    source = Source("test source")
    start_token = Token(TokenKind.NAME, start, end, 1, start, "test")
    return Location(start_token, start_token, source)


def describe_token_class():
    def initializes():
        token = Token(
            kind=TokenKind.NAME,
            start=11,
            end=12,
            line=1,
            column=3,
            value="n",
        )
        assert token.kind == TokenKind.NAME
        assert token.start == 11
        assert token.end == 12
        assert token.line == 1
        assert token.column == 3
        assert token.prev is None
        assert token.value == "n"

    def can_stringify():
        token = Token(TokenKind.NAME, 1, 2, 1, 2, value="test")
        assert str(token) == "Name 'test'"
        assert token.desc == str(token)

    def has_representation_with_line_and_column():
        token = Token(TokenKind.NAME, 1, 2, 1, 2, value="test")
        assert repr(token) == "<Token Name 'test' 1:2>"
        assert inspect(token) == repr(token)

    def can_check_equality():
        token1 = Token(TokenKind.NAME, 1, 2, 1, 2, value="test")
        token2 = Token(TokenKind.NAME, 1, 2, 1, 2, value="test")
        assert token2 == token1
        assert token2 == token1
        token3 = Token(TokenKind.NAME, 1, 2, 1, 2, value="text")
        assert token3 != token1
        token4 = Token(TokenKind.NAME, 1, 4, 1, 2, value="test")
        assert token4 != token1
        token5 = Token(TokenKind.NAME, 1, 2, 1, 4, value="test")
        assert token5 != token1

    def can_compare_with_string():
        token = Token(TokenKind.NAME, 1, 2, 1, 2, value="test")
        assert token == "Name 'test'"  # noqa: S105
        assert token != "Name 'foo'"  # noqa: S105

    def does_not_equal_incompatible_object():
        token = Token(TokenKind.NAME, 1, 2, 1, 2, value="test")
        assert token != {"Name": "test"}

    def can_hash():
        token1 = Token(TokenKind.NAME, 1, 2, 1, 2, value="hash")
        token2 = Token(TokenKind.NAME, 1, 2, 1, 2, value="hash")
        assert token2 == token1
        assert hash(token2) == hash(token1)
        token3 = Token(TokenKind.NAME, 1, 2, 1, 2, value="bash")
        assert token3 != token1
        assert hash(token3) != hash(token1)

    def can_copy():
        token1 = Token(TokenKind.NAME, 1, 2, 1, 2, value="copy")
        token2 = copy(token1)
        assert token2 == token1
        assert token2 is not token1


def describe_location_class():
    token1 = Token(TokenKind.NAME, 1, 2, 1, 2)
    token2 = Token(TokenKind.NAME, 2, 3, 1, 3)
    source = Source("source")

    def initializes():
        loc = Location(token1, token2, source)
        assert loc.start == token1.start
        assert loc.end == token2.end
        assert loc.start_token is token1
        assert loc.end_token is token2
        assert loc.source is source

    def can_stringify_with_start_and_end():
        loc = Location(token1, token2, source)
        assert str(loc) == "1:3"

    def has_representation_with_start_and_end():
        loc = Location(token1, token2, source)
        assert repr(loc) == "<Location 1:3>"
        assert inspect(loc) == repr(loc)

    def can_check_equality():
        loc1 = Location(token1, token2, source)
        loc2 = Location(token1, token2, source)
        assert loc2 == loc1
        loc3 = Location(token1, token1, source)
        assert loc3 != loc1
        loc4 = Location(token2, token2, source)
        assert loc4 != loc1
        assert loc4 != loc3

    def can_check_equality_with_tuple_or_list():
        loc = Location(token1, token2, source)
        assert loc == (1, 3)
        assert loc == [1, 3]
        assert loc == (1, 3)
        assert loc == [1, 3]
        assert loc != (1, 2)
        assert loc != [2, 3]

    def does_not_equal_incompatible_object():
        loc = Location(token1, token2, source)
        assert loc != (1, 2, 3)
        assert loc != (1, 2, 3)
        assert loc != {1: 2}
        assert loc != {1: 2}

    def can_hash():
        loc1 = Location(token1, token2, source)
        loc2 = Location(token1, token2, source)
        assert loc2 == loc1
        assert hash(loc2) == hash(loc1)
        loc3 = Location(token1, token1, source)
        assert loc3 != loc1
        assert hash(loc3) != hash(loc1)
        loc4 = Location(token2, token2, source)
        assert loc4 != loc1
        assert hash(loc4) != hash(loc1)
        assert hash(loc4) != hash(loc3)


def describe_node_class():
    def initializes_with_keywords():
        node = SampleTestNode(alpha=1, beta=2)
        assert node.alpha == 1
        assert node.beta == 2
        assert node.loc is None

    def initializes_with_location():
        loc = make_loc()
        node = SampleTestNode(alpha=1, beta=2, loc=loc)
        assert node.alpha == 1
        assert node.beta == 2
        assert node.loc is loc

    def initializes_with_none_location():
        node = SampleTestNode(alpha=1, beta=2, loc=None)
        assert node.loc is None
        assert node.alpha == 1
        assert node.beta == 2

    def rejects_unknown_keywords():
        import pytest

        with pytest.raises(TypeError, match="Unexpected keyword argument"):
            SampleTestNode(alpha=1, beta=2, gamma=3)  # type: ignore[call-arg]

    def has_representation_with_loc():
        node = SampleTestNode(alpha=1, beta=2)
        assert repr(node) == "SampleTestNode"
        loc = make_loc(start=3, end=5)
        node = SampleTestNode(alpha=1, beta=2, loc=loc)
        assert repr(node) == "SampleTestNode at 3:5"

    def has_representation_when_named():
        name_node = NameNode(value="baz")
        node = SampleNamedNode(foo="bar", name=name_node)
        assert repr(node) == "SampleNamedNode(name='baz')"
        loc = make_loc(start=3, end=5)
        node = SampleNamedNode(foo="bar", name=name_node, loc=loc)
        assert repr(node) == "SampleNamedNode(name='baz') at 3:5"

    def has_representation_when_named_but_name_is_none():
        node = SampleNamedNode(foo="bar", name=None)
        assert repr(node) == "SampleNamedNode"
        loc = make_loc(start=3, end=5)
        node = SampleNamedNode(foo="bar", name=None, loc=loc)
        assert repr(node) == "SampleNamedNode at 3:5"

    def has_special_representation_when_it_is_a_name_node():
        node = NameNode(value="foo")
        assert repr(node) == "NameNode('foo')"
        loc = make_loc(start=3, end=5)
        node = NameNode(value="foo", loc=loc)
        assert repr(node) == "NameNode('foo') at 3:5"

    def can_check_equality():
        node = SampleTestNode(alpha=1, beta=2)
        node2 = SampleTestNode(alpha=1, beta=2)
        assert node2 == node
        assert node2 == node
        node2 = SampleTestNode(alpha=1, beta=1)
        assert node2 != node
        # Different node types are not equal even with same field values
        node3 = SampleNamedNode(foo="test")
        assert node3 != node

    def can_hash():
        node = SampleTestNode(alpha=1, beta=2)
        node2 = SampleTestNode(alpha=1, beta=2)
        assert node == node2
        assert node2 is not node
        assert hash(node2) == hash(node)
        node3 = SampleTestNode(alpha=1, beta=3)
        assert node3 != node
        assert hash(node3) != hash(node)

    def is_hashable():
        node = SampleTestNode(alpha=1, beta=2)
        hash1 = hash(node)
        # Hash should be stable
        hash2 = hash(node)
        assert hash1 == hash2
        # Equal nodes have equal hashes
        node2 = SampleTestNode(alpha=1, beta=2)
        assert hash(node2) == hash1
        # Different values produce different hashes
        node3 = SampleTestNode(alpha=2, beta=2)
        assert hash(node3) != hash1

    def can_create_weak_reference():
        node = SampleTestNode(alpha=1, beta=2)
        ref = weakref.ref(node)
        assert ref() is node

    def can_create_shallow_copy():
        node = SampleTestNode(alpha=1, beta=2)
        node2 = copy(node)
        assert node2 is not node
        assert node2 == node

    def shallow_copy_is_really_shallow():
        inner = SampleTestNode(alpha=1, beta=2)
        node = SampleTestNode(alpha=inner, beta=inner)  # type: ignore[arg-type]
        node2 = copy(node)
        assert node2 is not node
        assert node2 == node
        assert node2.alpha is node.alpha
        assert node2.beta is node.beta

    def can_create_deep_copy():
        alpha = SampleTestNode(alpha=1, beta=2)
        beta = SampleTestNode(alpha=3, beta=4)
        node = SampleTestNode(alpha=alpha, beta=beta)  # type: ignore[arg-type]
        node2 = deepcopy(node)
        assert node2 is not node
        assert node2 == node
        assert node2.alpha == alpha
        assert node2.alpha is not alpha
        assert node2.alpha == alpha
        assert node2.beta is not beta

    def provides_snake_cased_kind_as_class_attribute():
        assert SampleTestNode.kind == "sample_test"

    def provides_proper_kind_if_class_does_not_end_with_node():
        class Foo(Node, frozen=True, kw_only=True):
            pass

        assert Foo.kind == "foo"

    def provides_keys_as_property():
        node = SampleTestNode(alpha=1, beta=2)
        assert node.keys == ("alpha", "beta", "loc")

    def can_can_convert_to_dict():
        node = SampleTestNode(alpha=1, beta=2)
        res = node.to_dict()
        assert node.to_dict(locations=True) == res
        assert res == {"kind": "sample_test", "alpha": 1, "beta": 2}
        assert list(res) == ["kind", "alpha", "beta"]

    def can_can_convert_to_dict_with_locations():
        token = Token(
            kind=TokenKind.NAME,
            start=1,
            end=3,
            line=1,
            column=1,
            value="foo",
        )
        loc = Location(token, token, Source("foo"))
        node = SampleTestNode(alpha=1, beta=2, loc=loc)
        res = node.to_dict(locations=True)
        assert res == {
            "kind": "sample_test",
            "alpha": 1,
            "beta": 2,
            "loc": {"start": 1, "end": 3},
        }
        assert list(res) == ["kind", "alpha", "beta", "loc"]
        assert list(res["loc"]) == ["start", "end"]
