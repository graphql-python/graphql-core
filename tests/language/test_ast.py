from copy import copy, deepcopy
import weakref

from graphql.language import Location, Node, Source, Token, TokenKind
from graphql.pyutils import inspect


class SampleTestNode(Node):
    __slots__ = "alpha", "beta"

    alpha: int
    beta: int


def describe_token_class():
    def initializes():
        prev = Token(TokenKind.EQUALS, 10, 11, 1, 2)
        token = Token(
            kind=TokenKind.NAME,
            start=11,
            end=12,
            line=1,
            column=3,
            prev=prev,
            value="n",
        )
        assert prev.kind == TokenKind.EQUALS
        assert prev.start == 10
        assert prev.end == 11
        assert prev.line == 1
        assert prev.column == 2
        assert token.kind == TokenKind.NAME
        assert token.start == 11
        assert token.end == 12
        assert token.line == 1
        assert token.column == 3
        assert token.prev is prev
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
        assert not token2 != token1
        token3 = Token(TokenKind.NAME, 1, 2, 1, 2, value="text")
        assert token3 != token1
        token4 = Token(TokenKind.NAME, 1, 4, 1, 2, value="test")
        assert token4 != token1
        token5 = Token(TokenKind.NAME, 1, 2, 1, 4, value="test")
        assert token5 != token1

    def can_compare_with_string():
        token = Token(TokenKind.NAME, 1, 2, 1, 2, value="test")
        assert token == "Name 'test'"
        assert token != "Name 'foo'"

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
        assert not loc != (1, 3)
        assert not loc != [1, 3]
        assert loc != (1, 2)
        assert loc != [2, 3]

    def does_not_equal_incompatible_object():
        loc = Location(token1, token2, source)
        assert not loc == (1, 2, 3)
        assert loc != (1, 2, 3)
        assert not loc == {1: 2}
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
        node = SampleTestNode(alpha=1, beta=2, loc=0)
        assert node.alpha == 1
        assert node.beta == 2
        assert node.loc == 0
        node = SampleTestNode(alpha=1, loc=None)
        assert node.loc is None
        assert node.alpha == 1
        assert node.beta is None
        node = SampleTestNode(alpha=1, beta=2, gamma=3)
        assert node.alpha == 1
        assert node.beta == 2
        assert not hasattr(node, "gamma")

    def has_representation_with_loc():
        node = SampleTestNode(alpha=1, beta=2)
        assert repr(node) == "SampleTestNode"
        node = SampleTestNode(alpha=1, beta=2, loc=3)
        assert repr(node) == "SampleTestNode at 3"

    def can_check_equality():
        node = SampleTestNode(alpha=1, beta=2)
        node2 = SampleTestNode(alpha=1, beta=2)
        assert node2 == node
        assert not node2 != node
        node2 = SampleTestNode(alpha=1, beta=1)
        assert node2 != node
        node3 = Node(alpha=1, beta=2)
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

    def can_create_weak_reference():
        node = SampleTestNode(alpha=1, beta=2)
        ref = weakref.ref(node)
        assert ref() is node

    def can_create_custom_attribute():
        node = SampleTestNode(alpha=1, beta=2)
        node.gamma = 3  # type: ignore
        assert node.gamma == 3  # type: ignore

    def can_create_shallow_copy():
        node = SampleTestNode(alpha=1, beta=2)
        node2 = copy(node)
        assert node2 is not node
        assert node2 == node

    def shallow_copy_is_really_shallow():
        node = SampleTestNode(alpha=1, beta=2)
        node2 = SampleTestNode(alpha=node, beta=node)
        node3 = copy(node2)
        assert node3 is not node2
        assert node3 == node2
        assert node3.alpha is node2.alpha
        assert node3.beta is node2.beta

    def can_create_deep_copy():
        alpha = SampleTestNode(alpha=1, beta=2)
        beta = SampleTestNode(alpha=3, beta=4)
        node = SampleTestNode(alpha=alpha, beta=beta)
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
        class Foo(Node):
            pass

        assert Foo.kind == "foo"

    def provides_keys_as_class_attribute():
        assert SampleTestNode.keys == ["loc", "alpha", "beta"]
