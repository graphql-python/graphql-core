from graphql import build_schema, parse, validate

from ..fixtures import big_schema_sdl  # noqa: F401


def test_validate_invalid_query(benchmark, big_schema_sdl):  # noqa: F811
    schema = build_schema(big_schema_sdl, assume_valid=True)
    query_ast = parse(
        """
        {
          unknownField
          ... on unknownType {
            anotherUnknownField
            ...unknownFragment
          }
        }

        fragment TestFragment on anotherUnknownType {
          yetAnotherUnknownField
        }
        """
    )
    result = benchmark(lambda: validate(schema, query_ast))
    assert result == [
        {
            "message": "Cannot query field 'unknownField' on type 'Query'.",
            "locations": [(3, 11)],
        },
        {"message": "Unknown type 'unknownType'.", "locations": [(4, 18)]},
        {"message": "Unknown fragment 'unknownFragment'.", "locations": [(6, 16)]},
        {"message": "Unknown type 'anotherUnknownType'.", "locations": [(10, 34)]},
        {"message": "Fragment 'TestFragment' is never used.", "locations": [(10, 9)]},
    ]
