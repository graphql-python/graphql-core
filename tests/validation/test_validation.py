import pytest

from graphql.error import GraphQLError
from graphql.language import parse
from graphql.utilities import TypeInfo, build_schema
from graphql.validation import ValidationRule, validate

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

    def deprecated_validates_using_a_custom_type_info():
        # This TypeInfo will never return a valid field.
        type_info = TypeInfo(test_schema, None, lambda *_args: None)

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

        errors = validate(test_schema, doc, None, None, type_info)

        assert [error.message for error in errors] == [
            "Cannot query field 'human' on type 'QueryRoot'. Did you mean 'human'?",
            "Cannot query field 'meowsVolume' on type 'Cat'."
            " Did you mean 'meowsVolume'?",
            "Cannot query field 'barkVolume' on type 'Dog'. Did you mean 'barkVolume'?",
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

    def pass_through_exceptions_from_rules():
        class CustomRule(ValidationRule):
            def enter_field(self, *_args):
                raise RuntimeError("Error from custom rule!")

        with pytest.raises(RuntimeError, match=r"^Error from custom rule!$"):
            validate(test_schema, doc, [CustomRule], max_errors=1)
