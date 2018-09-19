from graphql.language import parse
from graphql.utilities import get_operation_ast


def describe_get_operation_ast():
    def gets_an_operation_from_a_simple_document():
        doc = parse("{ field }")
        assert get_operation_ast(doc) == doc.definitions[0]

    def gets_an_operation_from_a_document_with_named_op_mutation():
        doc = parse("mutation Test { field }")
        assert get_operation_ast(doc) == doc.definitions[0]

    def gets_an_operation_from_a_document_with_named_op_subscription():
        doc = parse("subscription Test { field }")
        assert get_operation_ast(doc) == doc.definitions[0]

    def does_not_get_missing_operation():
        doc = parse("type Foo { field: String }")
        assert get_operation_ast(doc) is None

    def does_not_get_ambiguous_unnamed_operation():
        doc = parse(
            """
            { field }
            mutation Test { field }
            subscription TestSub { field }
            """
        )
        assert get_operation_ast(doc) is None

    def does_not_get_ambiguous_named_operation():
        doc = parse(
            """
            query TestQ { field }
            mutation TestM { field }
            subscription TestS { field }
            """
        )
        assert get_operation_ast(doc) is None

    def does_not_get_misnamed_operation():
        doc = parse(
            """
            query TestQ { field }
            mutation TestM { field }
            subscription TestS { field }
            """
        )
        assert get_operation_ast(doc, "Unknown") is None

    def gets_named_operation():
        doc = parse(
            """
            query TestQ { field }
            mutation TestM { field }
            subscription TestS { field }
            """
        )
        assert get_operation_ast(doc, "TestQ") == doc.definitions[0]
        assert get_operation_ast(doc, "TestM") == doc.definitions[1]
        assert get_operation_ast(doc, "TestS") == doc.definitions[2]
