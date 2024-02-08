from graphql.pyutils import merge_kwargs

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict


class FooDict(TypedDict):
    foo: str
    bar: str
    baz: int


def describe_merge_kwargs():
    def should_merge_with_no_kwargs():
        base = FooDict(foo="foo", bar="bar", baz=0)
        assert merge_kwargs(base) == base

    def should_merge_with_kwargs():
        base = FooDict(foo="foo", bar="bar", baz=0)
        assert merge_kwargs(base, foo="moo", bar="mar", baz=1) == FooDict(
            foo="moo", bar="mar", baz=1
        )
