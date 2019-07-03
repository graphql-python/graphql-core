from graphql.language import parse
from graphql.utilities import TypeInfo
from graphql.validation import specified_rules, validate

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

        errors = validate(test_schema, doc, specified_rules, type_info)

        assert [error.message for error in errors] == [
            "Cannot query field 'catOrDog' on type 'QueryRoot'."
            " Did you mean 'catOrDog'?",
            "Cannot query field 'furColor' on type 'Cat'. Did you mean 'furColor'?",
            "Cannot query field 'isHousetrained' on type 'Dog'."
            " Did you mean 'isHousetrained'?",
        ]
