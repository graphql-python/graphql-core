from typing import Any

from graphql import graphql_sync

from .star_wars_schema import star_wars_schema


def query_star_wars(source: str) -> Any:
    result = graphql_sync(star_wars_schema, source)
    assert result.errors is None
    return result.data


def describe_star_wars_introspection_tests():
    def describe_basic_introspection():
        def allows_querying_the_schema_for_types():
            data = query_star_wars(
                """
                {
                  __schema {
                    types {
                      name
                    }
                  }
                }
                """
            )
            # Include all types used by StarWars schema, introspection types and
            # standard directives. For example, `Boolean` is used in `@skip`,
            # `@include` and also inside introspection types.
            assert data == {
                "__schema": {
                    "types": [
                        {"name": "Human"},
                        {"name": "Character"},
                        {"name": "String"},
                        {"name": "Episode"},
                        {"name": "Droid"},
                        {"name": "Query"},
                        {"name": "Boolean"},
                        {"name": "__Schema"},
                        {"name": "__Type"},
                        {"name": "__TypeKind"},
                        {"name": "__Field"},
                        {"name": "__InputValue"},
                        {"name": "__EnumValue"},
                        {"name": "__Directive"},
                        {"name": "__DirectiveLocation"},
                    ]
                }
            }

        def allows_querying_the_schema_for_query_type():
            data = query_star_wars(
                """
                {
                  __schema {
                    queryType {
                      name
                    }
                  }
                }
                """
            )

            assert data == {"__schema": {"queryType": {"name": "Query"}}}

        def allows_querying_the_schema_for_a_specific_type():
            data = query_star_wars(
                """
                {
                  __type(name: "Droid") {
                    name
                  }
                }
                """
            )
            assert data == {"__type": {"name": "Droid"}}

        def allows_querying_the_schema_for_an_object_kind():
            data = query_star_wars(
                """
                {
                  __type(name: "Droid") {
                    name
                    kind
                  }
                }
                """
            )
            assert data == {"__type": {"name": "Droid", "kind": "OBJECT"}}

        def allows_querying_the_schema_for_an_interface_kind():
            data = query_star_wars(
                """
                {
                  __type(name: "Character") {
                    name
                    kind
                  }
                }
                """
            )
            assert data == {"__type": {"name": "Character", "kind": "INTERFACE"}}

        def allows_querying_the_schema_for_object_fields():
            data = query_star_wars(
                """
                {
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
            )
            assert data == {
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

        def allows_querying_the_schema_for_nested_object_fields():
            data = query_star_wars(
                """
                {
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
            )
            assert data == {
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

        def allows_querying_the_schema_for_field_args():
            data = query_star_wars(
                """
                {
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
            )

            assert data == {
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

        def allows_querying_the_schema_for_documentation():
            data = query_star_wars(
                """
                {
                  __type(name: "Droid") {
                    name
                    description
                  }
                }
                """
            )

            assert data == {
                "__type": {
                    "name": "Droid",
                    "description": "A mechanical creature in the Star Wars universe.",
                }
            }
