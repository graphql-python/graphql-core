from graphql.language import parse
from graphql.utilities import TypeInfo
from graphql.validation import validate

from .harness import test_schema


def describe_validate_supports_full_validation():
    def validates_queries():
        doc = parse(
            """
            query {
              catOrDog {
                ... on Cat {
                  furColor
                }
                ... on Dog {
                  isHousetrained
                }
              }
            }
            """
        )

        errors = validate(test_schema, doc)
        assert errors == []

    def detects_bad_scalar_parse():
        doc = parse(
            """
            query {
              invalidArg(arg: "bad value")
            }
            """
        )

        errors = validate(test_schema, doc)
        assert errors == [
            {
                "message": 'Expected type Invalid, found "bad value";'
                " Invalid scalar is always invalid: 'bad value'",
                "locations": [(3, 31)],
            }
        ]

    # NOTE: experimental
    def validates_using_a_custom_type_info():
        # This TypeInfo will never return a valid field.
        type_info = TypeInfo(test_schema, lambda *args: None)

        doc = parse(
            """
            query {
              catOrDog {
                ... on Cat {
                  furColor
                }
                ... on Dog {
                  isHousetrained
                }
              }
            }
            """
        )

        errors = validate(test_schema, doc, None, type_info)

        assert [error.message for error in errors] == [
            "Cannot query field 'catOrDog' on type 'QueryRoot'."
            " Did you mean 'catOrDog'?",
            "Cannot query field 'furColor' on type 'Cat'. Did you mean 'furColor'?",
            "Cannot query field 'isHousetrained' on type 'Dog'."
            " Did you mean 'isHousetrained'?",
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
            "locations": [],
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
