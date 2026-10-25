import gc
import weakref

import pytest

from graphql.error import GraphQLError
from graphql.language import parse
from graphql.utilities import build_schema
from graphql.validation import FieldsOnCorrectTypeRule, ValidationRule, validate
from graphql.validation.validate import ValidationAbortedError

from .harness import test_schema


def describe_validate_supports_full_validation():
    def validates_queries():
        doc = parse(
            """
            query {
              human {
                pets {
                  ... on Cat {
                    meowsVolume
                  }
                  ... on Dog {
                    barkVolume
                  }
                }
              }
            }
            """
        )

        errors = validate(test_schema, doc)
        assert errors == []

    def detects_unknown_fields():
        doc = parse(
            """
            {
              unknown
            }
            """
        )

        errors = validate(test_schema, doc)
        assert errors == [
            {"message": "Cannot query field 'unknown' on type 'QueryRoot'."}
        ]

    def validates_using_a_custom_rule():
        schema = build_schema(
            """
            directive @custom(arg: String) on FIELD

            type Query {
              foo: String
            }
            """
        )

        doc = parse(
            """
            query {
              name @custom
            }
            """
        )

        class CustomRule(ValidationRule):
            def enter_directive(self, node, *_args):
                directive_def = self.context.get_directive()
                error = GraphQLError("Reporting directive: " + str(directive_def), node)
                self.context.report_error(error)

        errors = validate(schema, doc, [CustomRule])
        assert errors == [
            {"message": "Reporting directive: @custom", "locations": [(3, 20)]}
        ]


def describe_validate_limit_maximum_number_of_validation_errors():
    query = """
        {
          firstUnknownField
          secondUnknownField
          thirdUnknownField
        }
        """
    doc = parse(query, no_location=True)

    def _validate_document(max_errors=None):
        return validate(test_schema, doc, max_errors=max_errors)

    def _invalid_field_error(field_name: str):
        return {
            "message": f"Cannot query field '{field_name}' on type 'QueryRoot'.",
        }

    def when_max_errors_is_equal_to_number_of_errors():
        errors = _validate_document(max_errors=3)
        assert errors == [
            _invalid_field_error("firstUnknownField"),
            _invalid_field_error("secondUnknownField"),
            _invalid_field_error("thirdUnknownField"),
        ]

    def when_max_errors_is_less_than_number_of_errors():
        errors = _validate_document(max_errors=2)
        assert errors == [
            _invalid_field_error("firstUnknownField"),
            _invalid_field_error("secondUnknownField"),
            {
                "message": "Too many validation errors, error limit reached."
                " Validation aborted."
            },
        ]

    def limits_to_100_when_max_errors_is_not_passed():
        errors = validate(
            test_schema,
            parse(
                "{" + " ".join(f"unknownField{n}" for n in range(120)) + "}",
                no_location=True,
            ),
        )
        assert len(errors) == 101
        assert errors[0] == _invalid_field_error("unknownField0")
        assert errors[-2] == _invalid_field_error("unknownField99")
        assert errors[-1] == {
            "message": "Too many validation errors, error limit reached."
            " Validation aborted."
        }

    class ReportWhileHandlingErrorRule(ValidationRule):
        def enter_field(self, node, *_args):
            try:
                raise RuntimeError("Handled error from custom rule!")
            except RuntimeError:
                self.report_error(GraphQLError("Error from custom rule!", node))

    def _validate_and_track(rules, count=3):
        # Run aborted validations with fresh documents, keep the aborted errors,
        # and track the documents and contexts with weak references. The other
        # errors are dropped, since errors created while handling an exception
        # keep its traceback on purpose.
        aborted_errors, refs = [], []

        class TrackContextRule(ValidationRule):
            def __init__(self, context):
                super().__init__(context)
                refs.append(weakref.ref(context))

        for _ in range(count):
            document = parse(query, no_location=True)
            refs.append(weakref.ref(document))
            errors = validate(
                test_schema, document, [TrackContextRule, *rules], max_errors=1
            )
            assert len(errors) == 2
            aborted_errors.append(errors[-1])
            del document, errors
        gc.collect()
        return aborted_errors, refs

    def creates_a_new_error_for_every_aborted_validation():
        first_error = _validate_document(max_errors=1)[-1]
        second_error = _validate_document(max_errors=1)[-1]
        assert type(first_error) is ValidationAbortedError
        assert type(second_error) is ValidationAbortedError
        assert first_error == second_error
        assert first_error is not second_error

    def returns_the_aborted_error_without_traceback_and_context():
        error = _validate_document(max_errors=1)[-1]
        assert isinstance(error, ValidationAbortedError)
        assert error.__traceback__ is None
        assert error.__context__ is None
        assert error.__cause__ is None

    def returns_the_aborted_error_without_context_of_a_handled_error():
        errors = validate(
            test_schema, doc, [ReportWhileHandlingErrorRule], max_errors=1
        )
        assert len(errors) == 2
        error = errors[-1]
        assert isinstance(error, ValidationAbortedError)
        assert error.__traceback__ is None
        assert error.__context__ is None
        assert error.__cause__ is None

    def does_not_keep_aborted_validations_alive():
        aborted_errors, refs = _validate_and_track([FieldsOnCorrectTypeRule])
        assert all(isinstance(e, ValidationAbortedError) for e in aborted_errors)
        assert len(refs) == 6
        assert all(ref() is None for ref in refs)

    def does_not_keep_validations_alive_that_were_aborted_while_handling_errors():
        aborted_errors, refs = _validate_and_track([ReportWhileHandlingErrorRule])
        assert all(isinstance(e, ValidationAbortedError) for e in aborted_errors)
        assert len(refs) == 6
        assert all(ref() is None for ref in refs)

    def aborted_error_accepts_the_arguments_of_graphql_error():
        node = doc.definitions[0]
        error = ValidationAbortedError(
            "Validation aborted.", node, extensions={"code": "ABORTED"}
        )
        assert error.message == "Validation aborted."
        assert error.nodes == [node]
        assert error.extensions == {"code": "ABORTED"}

    def pass_through_exceptions_from_rules():
        class CustomRule(ValidationRule):
            def enter_field(self, *_args):
                raise RuntimeError("Error from custom rule!")

        with pytest.raises(RuntimeError, match=r"^Error from custom rule!$"):
            validate(test_schema, doc, [CustomRule], max_errors=1)


def describe_operation_and_variable_definition_descriptions():
    def validates_operation_with_description_and_variable_descriptions():
        schema = build_schema("type Query { field(a: Int, b: String): String }")
        query = '''
            "Operation description"
            query myQuery(
              "Variable a description"
              $a: Int,
              """Variable b\nmultiline description"""
              $b: String
            ) {
              field(a: $a, b: $b)
            }
            '''
        ast = parse(query)
        errors = validate(schema, ast)
        assert errors == []
