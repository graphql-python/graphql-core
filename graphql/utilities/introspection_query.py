from textwrap import dedent

__all__ = ["get_introspection_query"]


def get_introspection_query(descriptions=True) -> str:
    """Get a query for introspection, optionally without descriptions."""
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
              {'description' if descriptions else ''}
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
          {'description' if descriptions else ''}
          fields(includeDeprecated: true) {{
            name
            {'description' if descriptions else ''}
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
            {'description' if descriptions else ''}
            isDeprecated
            deprecationReason
          }}
          possibleTypes {{
            ...TypeRef
          }}
        }}

        fragment InputValue on __InputValue {{
          name
          {'description' if descriptions else ''}
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
