from textwrap import dedent
from typing import Optional

__all__ = ["get_introspection_query"]


def get_introspection_query(
    descriptions: bool = True,
    specified_by_url: bool = False,
    directive_is_repeatable: bool = False,
    schema_description: bool = False,
    input_value_deprecation: bool = False,
) -> str:
    """Get a query for introspection.

    Optionally, you can exclude descriptions, include specification URLs,
    include repeatability of directives, and specify whether to include
    the schema description as well.
    """
    maybe_description = "description" if descriptions else ""
    maybe_specified_by_url = "specifiedByUrl" if specified_by_url else ""
    maybe_directive_is_repeatable = "isRepeatable" if directive_is_repeatable else ""
    maybe_schema_description = maybe_description if schema_description else ""

    def input_deprecation(string: str) -> Optional[str]:
        return string if input_value_deprecation else ""

    return dedent(
        f"""
        query IntrospectionQuery {{
          __schema {{
            {maybe_schema_description}
            queryType {{ name }}
            mutationType {{ name }}
            subscriptionType {{ name }}
            types {{
              ...FullType
            }}
            directives {{
              name
              {maybe_description}
              {maybe_directive_is_repeatable}
              locations
              args{input_deprecation("(includeDeprecated: true)")} {{
                ...InputValue
              }}
            }}
          }}
        }}

        fragment FullType on __Type {{
          kind
          name
          {maybe_description}
          {maybe_specified_by_url}
          fields(includeDeprecated: true) {{
            name
            {maybe_description}
            args{input_deprecation("(includeDeprecated: true)")} {{
              ...InputValue
            }}
            type {{
              ...TypeRef
            }}
            isDeprecated
            deprecationReason
          }}
          inputFields{input_deprecation("(includeDeprecated: true)")} {{
            ...InputValue
          }}
          interfaces {{
            ...TypeRef
          }}
          enumValues(includeDeprecated: true) {{
            name
            {maybe_description}
            isDeprecated
            deprecationReason
          }}
          possibleTypes {{
            ...TypeRef
          }}
        }}

        fragment InputValue on __InputValue {{
          name
          {maybe_description}
          type {{ ...TypeRef }}
          defaultValue
          {input_deprecation("isDeprecated")}
          {input_deprecation("deprecationReason")}
        }}

        fragment TypeRef on __Type {{
          kind
          name
          ofType {{
            kind
            name
            ofType {{
              kind
              name
              ofType {{
                kind
                name
                ofType {{
                  kind
                  name
                  ofType {{
                    kind
                    name
                    ofType {{
                      kind
                      name
                      ofType {{
                        kind
                        name
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
    )
