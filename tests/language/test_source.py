from graphql.language import Source


def describe_source():
    def can_be_stringified():
        source = Source("")
        assert str(source) == "<Source name='GraphQL request'>"

        source = Source("", "Custom source name")
        assert str(source) == "<Source name='Custom source name'>"
