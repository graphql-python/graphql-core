from graphql import graphql_sync
from graphql.type import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import get_introspection_query


def describe_introspection():
    def executes_an_introspection_query():
        schema = GraphQLSchema(
            GraphQLObjectType("QueryRoot", {"onlyField": GraphQLField(GraphQLString)}),
            description="Sample schema",
        )
        source = get_introspection_query(
            descriptions=False, directive_is_repeatable=True
        )

        result = graphql_sync(schema=schema, source=source)
        assert result.errors is None
        assert result.data == {
            "__schema": {
                "mutationType": None,
                "subscriptionType": None,
                "queryType": {"name": "QueryRoot"},
                "types": [
                    {
                        "kind": "OBJECT",
                        "name": "QueryRoot",
                        "fields": [
                            {
                                "name": "onlyField",
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
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "SCALAR",
                        "name": "Boolean",
                        "fields": None,
                        "inputFields": None,
                        "interfaces": None,
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__Schema",
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
                                "args": [],
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
                        ],
                        "inputFields": None,
                        "interfaces": [],
                        "enumValues": None,
                        "possibleTypes": None,
                    },
                    {
                        "kind": "OBJECT",
                        "name": "__EnumValue",
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
                        "locations": ["FIELD_DEFINITION", "ENUM_VALUE"],
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
                ],
            }
        }

    def introspects_on_input_object():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "a": GraphQLInputField(GraphQLString, default_value="tes\t de\fault"),
                "b": GraphQLInputField(GraphQLList(GraphQLString)),
                "c": GraphQLInputField(GraphQLString, default_value=None),
            },
        )

        TestType = GraphQLObjectType(
            "TestType",
            {
                "field": GraphQLField(
                    GraphQLString, args={"complex": GraphQLArgument(TestInputObject)}
                )
            },
        )

        schema = GraphQLSchema(TestType)
        source = """
            {
              __type(name: "TestInputObject") {
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
                    "name": "TestInputObject",
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
        TestType = GraphQLObjectType(
            "TestType", {"testField": GraphQLField(GraphQLString)}
        )

        schema = GraphQLSchema(TestType)
        source = """
            {
              __type(name: "TestType") {
                name
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {"__type": {"name": "TestType"}},
            None,
        )

    def identifies_deprecated_fields():
        TestType = GraphQLObjectType(
            "TestType",
            {
                "nonDeprecated": GraphQLField(GraphQLString),
                "deprecated": GraphQLField(
                    GraphQLString, deprecation_reason="Removed in 1.0"
                ),
                "deprecatedWithEmptyReason": GraphQLField(
                    GraphQLString, deprecation_reason=""
                ),
            },
        )

        schema = GraphQLSchema(TestType)
        source = """
            {
              __type(name: "TestType") {
                name
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
                    "name": "TestType",
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
        TestType = GraphQLObjectType(
            "TestType",
            {
                "nonDeprecated": GraphQLField(GraphQLString),
                "deprecated": GraphQLField(
                    GraphQLString, deprecation_reason="Removed in 1.0"
                ),
            },
        )

        schema = GraphQLSchema(TestType)
        source = """
            {
              __type(name: "TestType") {
                name
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
                    "name": "TestType",
                    "trueFields": [{"name": "nonDeprecated"}, {"name": "deprecated"}],
                    "falseFields": [{"name": "nonDeprecated"}],
                    "omittedFields": [{"name": "nonDeprecated"}],
                }
            },
            None,
        )

    def identifies_deprecated_enum_values():
        TestEnum = GraphQLEnumType(
            "TestEnum",
            {
                "NON_DEPRECATED": GraphQLEnumValue(0),
                "DEPRECATED": GraphQLEnumValue(1, deprecation_reason="Removed in 1.0"),
                "ALSO_NON_DEPRECATED": GraphQLEnumValue(2),
            },
        )

        TestType = GraphQLObjectType("TestType", {"testEnum": GraphQLField(TestEnum)})

        schema = GraphQLSchema(TestType)
        source = """
            {
              __type(name: "TestEnum") {
                name
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
                    "name": "TestEnum",
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
        TestEnum = GraphQLEnumType(
            "TestEnum",
            {
                "NON_DEPRECATED": GraphQLEnumValue(0),
                "DEPRECATED": GraphQLEnumValue(1, deprecation_reason="Removed in 1.0"),
                "DEPRECATED_WITH_EMPTY_REASON": GraphQLEnumValue(
                    2, deprecation_reason=""
                ),
                "ALSO_NON_DEPRECATED": GraphQLEnumValue(3),
            },
        )

        TestType = GraphQLObjectType("TestType", {"testEnum": GraphQLField(TestEnum)})

        schema = GraphQLSchema(TestType)
        source = """
            {
              __type(name: "TestEnum") {
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
        TestType = GraphQLObjectType(
            "TestType", {"testField": GraphQLField(GraphQLString)}
        )

        schema = GraphQLSchema(TestType)
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

    def exposes_descriptions_on_types_and_fields():
        QueryRoot = GraphQLObjectType(
            "QueryRoot", {"onlyField": GraphQLField(GraphQLString)}
        )

        schema = GraphQLSchema(QueryRoot)
        source = """
            {
              schemaType: __type(name: "__Schema") {
                name,
                description,
                fields {
                  name,
                  description
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "schemaType": {
                    "name": "__Schema",
                    "description": "A GraphQL Schema defines the capabilities of a"
                    " GraphQL server. It exposes all available types and"
                    " directives on the server, as well as the entry points"
                    " for query, mutation, and subscription operations.",
                    "fields": [
                        {"name": "description", "description": None},
                        {
                            "name": "types",
                            "description": "A list of all types supported"
                            " by this server.",
                        },
                        {
                            "name": "queryType",
                            "description": "The type that query operations"
                            " will be rooted at.",
                        },
                        {
                            "name": "mutationType",
                            "description": "If this server supports mutation, the type"
                            " that mutation operations will be rooted at.",
                        },
                        {
                            "name": "subscriptionType",
                            "description": "If this server support subscription,"
                            " the type that subscription operations will be rooted at.",
                        },
                        {
                            "name": "directives",
                            "description": "A list of all directives supported"
                            " by this server.",
                        },
                    ],
                }
            },
            None,
        )

    def exposes_descriptions_on_enums():
        QueryRoot = GraphQLObjectType(
            "QueryRoot", {"onlyField": GraphQLField(GraphQLString)}
        )

        schema = GraphQLSchema(QueryRoot)
        source = """
            {
              typeKindType: __type(name: "__TypeKind") {
                name,
                description,
                enumValues {
                  name,
                  description
                }
              }
            }
            """

        assert graphql_sync(schema=schema, source=source) == (
            {
                "typeKindType": {
                    "name": "__TypeKind",
                    "description": "An enum describing what kind of type"
                    " a given `__Type` is.",
                    "enumValues": [
                        {
                            "description": "Indicates this type is a scalar.",
                            "name": "SCALAR",
                        },
                        {
                            "description": "Indicates this type is an object."
                            + " `fields` and `interfaces` are valid fields.",
                            "name": "OBJECT",
                        },
                        {
                            "description": "Indicates this type is an interface."
                            " `fields`, `interfaces`, and `possibleTypes`"
                            " are valid fields.",
                            "name": "INTERFACE",
                        },
                        {
                            "description": "Indicates this type is a union."
                            " `possibleTypes` is a valid field.",
                            "name": "UNION",
                        },
                        {
                            "description": "Indicates this type is an enum."
                            " `enumValues` is a valid field.",
                            "name": "ENUM",
                        },
                        {
                            "description": "Indicates this type is an input object."
                            " `inputFields` is a valid field.",
                            "name": "INPUT_OBJECT",
                        },
                        {
                            "description": "Indicates this type is a list."
                            " `ofType` is a valid field.",
                            "name": "LIST",
                        },
                        {
                            "description": "Indicates this type is a non-null."
                            " `ofType` is a valid field.",
                            "name": "NON_NULL",
                        },
                    ],
                }
            },
            None,
        )

    def executes_introspection_query_without_calling_global_field_resolver():
        query_root = GraphQLObjectType(
            "QueryRoot", {"onlyField": GraphQLField(GraphQLString)}
        )

        schema = GraphQLSchema(query_root)
        source = get_introspection_query(directive_is_repeatable=True)

        def field_resolver(_obj, info):
            assert False, f"Called on {info.parent_type.name}.{info.field_name}"

        graphql_sync(schema=schema, source=source, field_resolver=field_resolver)
