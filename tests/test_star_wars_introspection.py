from graphql import graphql_sync

from .star_wars_schema import star_wars_schema


def describe_star_wars_introspection_tests():
    def describe_basic_introspection():
        def allows_querying_the_schema_for_types():
            query = """
                query IntrospectionTypeQuery {
                  __schema {
                    types {
                      name
                    }
                  }
                }
                """
            expected = {
                "__schema": {
                    "types": [
                        {"name": "Query"},
                        {"name": "Episode"},
                        {"name": "Character"},
                        {"name": "String"},
                        {"name": "Human"},
                        {"name": "Droid"},
                        {"name": "__Schema"},
                        {"name": "__Type"},
                        {"name": "__TypeKind"},
                        {"name": "Boolean"},
                        {"name": "__Field"},
                        {"name": "__InputValue"},
                        {"name": "__EnumValue"},
                        {"name": "__Directive"},
                        {"name": "__DirectiveLocation"},
                    ]
                }
            }

            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_query_type():
            query = """
                query IntrospectionQueryTypeQuery {
                  __schema {
                    queryType {
                      name
                    }
                  }
                }
                """
            expected = {"__schema": {"queryType": {"name": "Query"}}}
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_a_specific_type():
            query = """
                query IntrospectionDroidTypeQuery {
                  __type(name: "Droid") {
                    name
                  }
                }
                """
            expected = {"__type": {"name": "Droid"}}
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_an_object_kind():
            query = """
                query IntrospectionDroidKindQuery {
                  __type(name: "Droid") {
                    name
                    kind
                  }
                }
                """
            expected = {"__type": {"name": "Droid", "kind": "OBJECT"}}
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_an_interface_kind():
            query = """
                query IntrospectionCharacterKindQuery {
                  __type(name: "Character") {
                    name
                    kind
                  }
                }
                """
            expected = {"__type": {"name": "Character", "kind": "INTERFACE"}}
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_object_fields():
            query = """
                query IntrospectionDroidFieldsQuery {
                  __type(name: "Droid") {
                    name
                    fields {
                      name
                      type {
                        name
                        kind
                      }
                    }
                  }
                }
                """
            expected = {
                "__type": {
                    "name": "Droid",
                    "fields": [
                        {"name": "id", "type": {"name": None, "kind": "NON_NULL"}},
                        {"name": "name", "type": {"name": "String", "kind": "SCALAR"}},
                        {"name": "friends", "type": {"name": None, "kind": "LIST"}},
                        {"name": "appearsIn", "type": {"name": None, "kind": "LIST"}},
                        {
                            "name": "secretBackstory",
                            "type": {"name": "String", "kind": "SCALAR"},
                        },
                        {
                            "name": "primaryFunction",
                            "type": {"name": "String", "kind": "SCALAR"},
                        },
                    ],
                }
            }
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_nested_object_fields():
            query = """
                query IntrospectionDroidNestedFieldsQuery {
                  __type(name: "Droid") {
                    name
                    fields {
                      name
                      type {
                        name
                        kind
                        ofType {
                          name
                          kind
                        }
                      }
                    }
                  }
                }
                """
            expected = {
                "__type": {
                    "name": "Droid",
                    "fields": [
                        {
                            "name": "id",
                            "type": {
                                "name": None,
                                "kind": "NON_NULL",
                                "ofType": {"name": "String", "kind": "SCALAR"},
                            },
                        },
                        {
                            "name": "name",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                        },
                        {
                            "name": "friends",
                            "type": {
                                "name": None,
                                "kind": "LIST",
                                "ofType": {"name": "Character", "kind": "INTERFACE"},
                            },
                        },
                        {
                            "name": "appearsIn",
                            "type": {
                                "name": None,
                                "kind": "LIST",
                                "ofType": {"name": "Episode", "kind": "ENUM"},
                            },
                        },
                        {
                            "name": "secretBackstory",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                        },
                        {
                            "name": "primaryFunction",
                            "type": {
                                "name": "String",
                                "kind": "SCALAR",
                                "ofType": None,
                            },
                        },
                    ],
                }
            }
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_field_args():
            query = """
                query IntrospectionQueryTypeQuery {
                  __schema {
                    queryType {
                      fields {
                        name
                        args {
                          name
                          description
                          type {
                            name
                            kind
                            ofType {
                              name
                              kind
                            }
                          }
                          defaultValue
                        }
                      }
                    }
                  }
                }
                """
            expected = {
                "__schema": {
                    "queryType": {
                        "fields": [
                            {
                                "name": "hero",
                                "args": [
                                    {
                                        "defaultValue": None,
                                        "description": "If omitted, returns the hero of"
                                        " the whole saga. If provided, returns the hero"
                                        " of that particular episode.",
                                        "name": "episode",
                                        "type": {
                                            "kind": "ENUM",
                                            "name": "Episode",
                                            "ofType": None,
                                        },
                                    }
                                ],
                            },
                            {
                                "name": "human",
                                "args": [
                                    {
                                        "name": "id",
                                        "description": "id of the human",
                                        "type": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {
                                                "kind": "SCALAR",
                                                "name": "String",
                                            },
                                        },
                                        "defaultValue": None,
                                    }
                                ],
                            },
                            {
                                "name": "droid",
                                "args": [
                                    {
                                        "name": "id",
                                        "description": "id of the droid",
                                        "type": {
                                            "kind": "NON_NULL",
                                            "name": None,
                                            "ofType": {
                                                "kind": "SCALAR",
                                                "name": "String",
                                            },
                                        },
                                        "defaultValue": None,
                                    }
                                ],
                            },
                        ]
                    }
                }
            }
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)

        def allows_querying_the_schema_for_documentation():
            query = """
                query IntrospectionDroidDescriptionQuery {
                  __type(name: "Droid") {
                    name
                    description
                  }
                }
                """
            expected = {
                "__type": {
                    "name": "Droid",
                    "description": "A mechanical creature in the Star Wars universe.",
                }
            }
            result = graphql_sync(star_wars_schema, query)
            assert result == (expected, None)
