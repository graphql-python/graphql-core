from textwrap import dedent

__all__ = ["get_introspection_query"]


def get_introspection_query(descriptions=True, directive_is_repeatable=False) -> str:
    """Get a query for introspection.

    Optionally, you can exclude descriptions and include repeatability of directives.
    """
    maybe_description = "description" if descriptions else ""
    maybe_directive_is_repeatable = "isRepeatable" if directive_is_repeatable else ""
    return dedent(
        f"""
        query IntrospectionQuery {{
          __schema {{
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
              args {{
                ...InputValue
              }}
            }}
          }}
        }}

        fragment FullType on __Type {{
          kind
          name
          {maybe_description}
          fields(includeDeprecated: true) {{
            name
            {maybe_description}
            args {{
              ...InputValue
            }}
            type {{
              ...TypeRef
            }}
            isDeprecated
            deprecationReason
          }}
          inputFields {{
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
