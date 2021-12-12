from graphql import graphql_sync
from graphql.utilities import get_introspection_query, build_schema


def describe_introspection():
    def executes_an_introspection_query():
        schema = build_schema(
            """
            type SomeObject {
              someField: String
            }

            schema {
              query: SomeObject
            }
            """
        )

        source = get_introspection_query(
            descriptions=False, specified_by_url=True, directive_is_repeatable=True
        )

        result = graphql_sync(schema=schema, source=source)
        assert result.errors is None
        assert result.data == {
            "__schema": {
                "queryType": {"name": "SomeObject"},
                "mutationType": None,
                "subscriptionType": None,
                "types": [
                    {
                        "kind": "OBJECT",
                        "name": "SomeObject",
                        "specifiedByUrl": None,
                        "fields": [
                            {
                                "name": "someField",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            }
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "String",
                        "specifiedByUrl": None,
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "Boolean",
                        "specifiedByUrl": None,
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__Schema",
                        "specifiedByUrl": None,
                        "fields": [
                            {
                                "name": "description",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "types",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "LIST",
                                        "name": None,
                                        "ofType": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {
                                                "kind": "OBJECT",
                                                "name": "__Type",
                                                "ofType": None,
                                            },
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "queryType",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "OBJECT",
                                        "name": "__Type",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "mutationType",
                                "args": [],
                                "type": {
                                    "kind": "OBJECT",
                                    "name": "__Type",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "subscriptionType",
                                "args": [],
                                "type": {
                                    "kind": "OBJECT",
                                    "name": "__Type",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "directives",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "LIST",
                                        "name": None,
                                        "ofType": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {
                                                "kind": "OBJECT",
                                                "name": "__Directive",
                                                "ofType": None,
                                            },
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__Type",
                        "specifiedByUrl": None,
                        "fields": [
                            {
                                "name": "kind",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "ENUM",
                                        "name": "__TypeKind",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "name",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "description",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "specifiedByUrl",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "fields",
                                "args": [
                                    {
                                        "name": "includeDeprecated",
                                        "type": {
                                            "kind": "SCALAR",
                                            "name": "Boolean",
                                            "ofType": None,
                                        },
                                        "defaultValue": "false",
                                    }
                                ],
                                "type": {
                                    "kind": "LIST",
                                    "name": None,
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "name": None,
                                        "ofType": {
                                            "kind": "OBJECT",
                                            "name": "__Field",
                                            "ofType": None,
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "interfaces",
                                "args": [],
                                "type": {
                                    "kind": "LIST",
                                    "name": None,
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "name": None,
                                        "ofType": {
                                            "kind": "OBJECT",
                                            "name": "__Type",
                                            "ofType": None,
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "possibleTypes",
                                "args": [],
                                "type": {
                                    "kind": "LIST",
                                    "name": None,
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "name": None,
                                        "ofType": {
                                            "kind": "OBJECT",
                                            "name": "__Type",
                                            "ofType": None,
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "enumValues",
                                "args": [
                                    {
                                        "name": "includeDeprecated",
                                        "type": {
                                            "kind": "SCALAR",
                                            "name": "Boolean",
                                            "ofType": None,
                                        },
                                        "defaultValue": "false",
                                    }
                                ],
                                "type": {
                                    "kind": "LIST",
                                    "name": None,
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "name": None,
                                        "ofType": {
                                            "kind": "OBJECT",
                                            "name": "__EnumValue",
                                            "ofType": None,
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "inputFields",
                                "args": [
                                    {
                                        "name": "includeDeprecated",
                                        "type": {
                                            "kind": "SCALAR",
                                            "name": "Boolean",
                                            "ofType": None,
                                        },
                                        "defaultValue": "false",
                                    }
                                ],
                                "type": {
                                    "kind": "LIST",
                                    "name": None,
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "name": None,
                                        "ofType": {
                                            "kind": "OBJECT",
                                            "name": "__InputValue",
                                            "ofType": None,
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "ofType",
                                "args": [],
                                "type": {
                                    "kind": "OBJECT",
                                    "name": "__Type",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "ENUM",
                        "name": "__TypeKind",
                        "specifiedByUrl": None,
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": [
                            {
                                "name": "SCALAR",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "OBJECT",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "INTERFACE",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "UNION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "ENUM",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "INPUT_OBJECT",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "LIST",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "NON_NULL",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__Field",
                        "specifiedByUrl": None,
                        "fields": [
                            {
                                "name": "name",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "String",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "description",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "args",
                                "args": [
                                    {
                                        "name": "includeDeprecated",
                                        "type": {
                                            "kind": "SCALAR",
                                            "name": "Boolean",
                                            "ofType": None,
                                        },
                                        "defaultValue": "false",
                                    }
                                ],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "LIST",
                                        "name": None,
                                        "ofType": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {
                                                "kind": "OBJECT",
                                                "name": "__InputValue",
                                                "ofType": None,
                                            },
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "type",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "OBJECT",
                                        "name": "__Type",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "isDeprecated",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "Boolean",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "deprecationReason",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__InputValue",
                        "specifiedByUrl": None,
                        "fields": [
                            {
                                "name": "name",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "String",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "description",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "type",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "OBJECT",
                                        "name": "__Type",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "defaultValue",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "isDeprecated",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "Boolean",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "deprecationReason",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__EnumValue",
                        "specifiedByUrl": None,
                        "fields": [
                            {
                                "name": "name",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "String",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "description",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "isDeprecated",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "Boolean",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "deprecationReason",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__Directive",
                        "specifiedByUrl": None,
                        "fields": [
                            {
                                "name": "name",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "String",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "description",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "isRepeatable",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "Boolean",
                                        "ofType": None,
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "locations",
                                "args": [],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "LIST",
                                        "name": None,
                                        "ofType": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {
                                                "kind": "ENUM",
                                                "name": "__DirectiveLocation",
                                                "ofType": None,
                                            },
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "args",
                                "args": [
                                    {
                                        "name": "includeDeprecated",
                                        "type": {
                                            "kind": "SCALAR",
                                            "name": "Boolean",
                                            "ofType": None,
                                        },
                                        "defaultValue": "false",
                                    }
                                ],
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "LIST",
                                        "name": None,
                                        "ofType": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {
                                                "kind": "OBJECT",
                                                "name": "__InputValue",
                                                "ofType": None,
                                            },
                                        },
                                    },
                                },
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "ENUM",
                        "name": "__DirectiveLocation",
                        "specifiedByUrl": None,
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": [
                            {
                                "name": "QUERY",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "MUTATION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "SUBSCRIPTION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "FIELD",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "FRAGMENT_DEFINITION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "FRAGMENT_SPREAD",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "INLINE_FRAGMENT",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "VARIABLE_DEFINITION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "SCHEMA",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "SCALAR",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "OBJECT",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "FIELD_DEFINITION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "ARGUMENT_DEFINITION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "INTERFACE",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "UNION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "ENUM",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "ENUM_VALUE",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "INPUT_OBJECT",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                            {
                                "name": "INPUT_FIELD_DEFINITION",
                                "isDeprecated": False,
                                "deprecationReason": None,
                            },
                        ],
                        "possibleTypes": None,
                    },
                ],
                "directives": [
                    {
                        "name": "include",
                        "isRepeatable": False,
                        "locations": ["FIELD", "FRAGMENT_SPREAD", "INLINE_FRAGMENT"],
                        "args": [
                            {
                                "defaultValue": None,
                                "name": "if",
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "Boolean",
                                        "ofType": None,
                                    },
                                },
                            }
                        ],
                    },
                    {
                        "name": "skip",
                        "isRepeatable": False,
                        "locations": ["FIELD", "FRAGMENT_SPREAD", "INLINE_FRAGMENT"],
                        "args": [
                            {
                                "defaultValue": None,
                                "name": "if",
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "Boolean",
                                        "ofType": None,
                                    },
                                },
                            }
                        ],
                    },
                    {
                        "name": "deprecated",
                        "isRepeatable": False,
                        "locations": [
                            "FIELD_DEFINITION",
                            "ARGUMENT_DEFINITION",
                            "INPUT_FIELD_DEFINITION",
                            "ENUM_VALUE",
                        ],
                        "args": [
                            {
                                "defaultValue": '"No longer supported"',
                                "name": "reason",
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                            }
                        ],
                    },
                    {
                        "name": "specifiedBy",
                        "isRepeatable": False,
                        "locations": ["SCALAR"],
                        "args": [
                            {
                                "defaultValue": None,
                                "name": "url",
                                "type": {
                                    "kind": "NON_NULL",
                                    "name": None,
                                    "ofType": {
                                        "kind": "SCALAR",
                                        "name": "String",
                                        "ofType": None,
                                    },
                                },
                            }
                        ],
                    },
                ],
            }
        }

    def introspects_on_input_object():
        schema = build_schema(
            """
            input SomeInputObject {
              a: String = "tes\\t de\\fault"
              b: [String]
              c: String = null
            }

            type Query {
              someField(someArg: SomeInputObject): String
            }
            """
        )

        source = """
            {
              __type(name: "SomeInputObject") {
                kind
                name
                inputFields {
                  name
                  type { ...TypeRef }
                  defaultValue
                }
              }
            }

            fragment TypeRef on __Type {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                  ofType {
                    kind
                    name
                  }
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "__type": {
                    "kind": "INPUT_OBJECT",
                    "name": "SomeInputObject",
                    "inputFields": [
                        {
                            "name": "a",
                            "type": {
                                "kind": "SCALAR",
                                "name": "String",
                                "ofType": None,
                            },
                            "defaultValue": '"tes\\t de\\fault"',
                        },
                        {
                            "name": "b",
                            "type": {
                                "kind": "LIST",
                                "name": None,
                                "ofType": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                            },
                            "defaultValue": None,
                        },
                        {
                            "name": "c",
                            "type": {
                                "kind": "SCALAR",
                                "name": "String",
                                "ofType": None,
                            },
                            "defaultValue": "null",
                        },
                    ],
                }
            },
            None,
        )

    def supports_the_type_root_field():
        schema = build_schema(
            """
            type Query {
              someField: String
            }
            """
        )

        source = """
            {
              __type(name: "Query") {
                name
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {"__type": {"name": "Query"}},
            None,
        )

    def identifies_deprecated_fields():
        schema = build_schema(
            """
            type Query {
              nonDeprecated: String
              deprecated: String @deprecated(reason: "Removed in 1.0")
              deprecatedWithEmptyReason: String @deprecated(reason: "")
            }
            """
        )

        source = """
            {
              __type(name: "Query") {
                fields(includeDeprecated: true) {
                  name
                  isDeprecated,
                  deprecationReason
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "__type": {
                    "fields": [
                        {
                            "name": "nonDeprecated",
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "deprecated",
                            "isDeprecated": True,
                            "deprecationReason": "Removed in 1.0",
                        },
                        {
                            "name": "deprecatedWithEmptyReason",
                            "isDeprecated": True,
                            "deprecationReason": "",
                        },
                    ],
                }
            },
            None,
        )

    def respects_the_include_deprecated_parameter_for_fields():
        schema = build_schema(
            """
            type Query {
              nonDeprecated: String
              deprecated: String @deprecated(reason: "Removed in 1.0")
            }
            """
        )

        source = """
            {
              __type(name: "Query") {
                trueFields: fields(includeDeprecated: true) {
                  name
                }
                falseFields: fields(includeDeprecated: false) {
                  name
                }
                omittedFields: fields {
                  name
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "__type": {
                    "trueFields": [{"name": "nonDeprecated"}, {"name": "deprecated"}],
                    "falseFields": [{"name": "nonDeprecated"}],
                    "omittedFields": [{"name": "nonDeprecated"}],
                }
            },
            None,
        )

    def identifies_deprecated_args():
        schema = build_schema(
            """
            type Query {
              someField(
                nonDeprecated: String
                deprecated: String @deprecated(reason: "Removed in 1.0")
                deprecatedWithEmptyReason: String @deprecated(reason: "")
              ): String
            }
            """
        )

        source = """
            {
              __type(name: "Query") {
                fields {
                  args(includeDeprecated: true) {
                    name
                    isDeprecated,
                    deprecationReason
                  }
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "__type": {
                    "fields": [
                        {
                            "args": [
                                {
                                    "name": "nonDeprecated",
                                    "isDeprecated": False,
                                    "deprecationReason": None,
                                },
                                {
                                    "name": "deprecated",
                                    "isDeprecated": True,
                                    "deprecationReason": "Removed in 1.0",
                                },
                                {
                                    "name": "deprecatedWithEmptyReason",
                                    "isDeprecated": True,
                                    "deprecationReason": "",
                                },
                            ],
                        },
                    ],
                }
            },
            None,
        )

    def respects_the_include_deprecated_parameter_for_args():
        schema = build_schema(
            """
            type Query {
              someField(
                nonDeprecated: String
                deprecated: String @deprecated(reason: "Removed in 1.0")
              ): String
            }
            """
        )

        source = """
            {
              __type(name: "Query") {
                fields {
                  trueArgs: args(includeDeprecated: true) {
                    name
                  }
                  falseArgs: args(includeDeprecated: false) {
                    name
                  }
                  omittedArgs: args {
                    name
                  }
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "__type": {
                    "fields": [
                        {
                            "trueArgs": [
                                {"name": "nonDeprecated"},
                                {"name": "deprecated"},
                            ],
                            "falseArgs": [{"name": "nonDeprecated"}],
                            "omittedArgs": [{"name": "nonDeprecated"}],
                        },
                    ],
                },
            },
            None,
        )

    def identifies_deprecated_enum_values():
        schema = build_schema(
            """
            enum SomeEnum {
              NON_DEPRECATED
              DEPRECATED @deprecated(reason: "Removed in 1.0")
              ALSO_NON_DEPRECATED
            }

            type Query {
              someField(someArg: SomeEnum): String
            }
            """
        )

        source = """
            {
              __type(name: "SomeEnum") {
                enumValues(includeDeprecated: true) {
                  name
                  isDeprecated,
                  deprecationReason
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "__type": {
                    "enumValues": [
                        {
                            "name": "NON_DEPRECATED",
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "DEPRECATED",
                            "isDeprecated": True,
                            "deprecationReason": "Removed in 1.0",
                        },
                        {
                            "name": "ALSO_NON_DEPRECATED",
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                }
            },
            None,
        )

    def respects_the_include_deprecated_parameter_for_enum_values():
        schema = build_schema(
            """
          enum SomeEnum {
            NON_DEPRECATED
            DEPRECATED @deprecated(reason: "Removed in 1.0")
            DEPRECATED_WITH_EMPTY_REASON @deprecated(reason: "")
            ALSO_NON_DEPRECATED
          }

          type Query {
            someField(someArg: SomeEnum): String
          }
            """
        )

        source = """
            {
              __type(name: "SomeEnum") {
                trueValues: enumValues(includeDeprecated: true) {
                  name
                }
                falseValues: enumValues(includeDeprecated: false) {
                  name
                }
                omittedValues: enumValues {
                  name
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "__type": {
                    "trueValues": [
                        {"name": "NON_DEPRECATED"},
                        {"name": "DEPRECATED"},
                        {"name": "DEPRECATED_WITH_EMPTY_REASON"},
                        {"name": "ALSO_NON_DEPRECATED"},
                    ],
                    "falseValues": [
                        {"name": "NON_DEPRECATED"},
                        {"name": "ALSO_NON_DEPRECATED"},
                    ],
                    "omittedValues": [
                        {"name": "NON_DEPRECATED"},
                        {"name": "ALSO_NON_DEPRECATED"},
                    ],
                }
            },
            None,
        )

    def fails_as_expected_on_the_type_root_field_without_an_arg():
        schema = build_schema(
            """
            type Query {
              someField: String
            }
            """
        )

        source = """
            {
              __type {
                name
              }
            }
            """
        assert graphql_sync(schema=schema, source=source) == (
            None,
            [
                {
                    "message": "Field '__type' argument 'name'"
                    " of type 'String!' is required, but it was not provided.",
                    "locations": [(3, 15)],
                }
            ],
        )

    def exposes_descriptions():
        schema = build_schema(
            '''
            """Enum description"""
            enum SomeEnum {
              """Value description"""
              VALUE
            }

            """Object description"""
            type SomeObject {
              """Field description"""
              someField(arg: SomeEnum): String
            }

            """Schema description"""
            schema {
              query: SomeObject
            }
            '''
        )

        source = """
            {
              Schema: __schema { description }
              SomeObject: __type(name: "SomeObject") {
                description,
                fields {
                  name
                  description
                }
              }
              SomeEnum: __type(name: "SomeEnum") {
                description
                enumValues {
                  name
                  description
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "Schema": {
                    "description": "Schema description",
                },
                "SomeEnum": {
                    "description": "Enum description",
                    "enumValues": [
                        {
                            "name": "VALUE",
                            "description": "Value description",
                        },
                    ],
                },
                "SomeObject": {
                    "description": "Object description",
                    "fields": [
                        {
                            "name": "someField",
                            "description": "Field description",
                        },
                    ],
                },
            },
            None,
        )

    def executes_introspection_query_without_calling_global_resolvers():
        schema = build_schema(
            """
            type Query {
              someField: String
            }
            """
        )

        source = get_introspection_query(
            specified_by_url=True, directive_is_repeatable=True, schema_description=True
        )

        def field_resolver(_obj, info):
            assert False, f"Called on {info.parent_type.name}.{info.field_name}"

        def type_resolver(_obj, info, _abstract_type):
            assert False, f"Called on {info.parent_type.name}.{info.field_name}"

        graphql_sync(
            schema=schema,
            source=source,
            field_resolver=field_resolver,
            type_resolver=type_resolver,
        )
