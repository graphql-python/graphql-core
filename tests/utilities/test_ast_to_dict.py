from graphql.language import parse, FieldNode, NameNode, OperationType, SelectionSetNode
from graphql.utilities import ast_to_dict


def describe_ast_to_disc():
    def converts_name_node_to_dict():
        node = NameNode(value="test")
        res = ast_to_dict(node)
        assert res == {"kind": "name", "value": "test"}
        assert list(res)[0] == "kind"
        assert ast_to_dict(node, locations=True) == res
        assert node.to_dict() == res
        assert node.to_dict(locations=True) == res

    def converts_two_name_nodes_to_list():
        nodes = [NameNode(value="foo"), NameNode(value="bar")]
        res = ast_to_dict(nodes)
        assert ast_to_dict(nodes, locations=True) == res
        assert res == [
            {"kind": "name", "value": "foo"},
            {"kind": "name", "value": "bar"},
        ]

    def converts_operation_type_to_its_value():
        assert ast_to_dict(OperationType.QUERY) == "query"

    def keeps_all_other_leaf_nodes():
        assert ast_to_dict(None) is None  # type: ignore
        assert ast_to_dict(42) == 42  # type: ignore
        assert ast_to_dict("foo") == "foo"  # type: ignore
        ast = {"foo": "bar"}
        assert ast_to_dict(ast) is ast  # type: ignore

    def converts_recursive_ast_to_recursive_dict():
        field = FieldNode(name="foo", arguments=(), selection_set=())
        ast = SelectionSetNode(selections=(field,))
        field.selection_set = ast
        res = ast_to_dict(ast)
        assert res == {
            "kind": "selection_set",
            "selections": [
                {
                    "kind": "field",
                    "name": "foo",
                    "alias": None,
                    "arguments": [],
                    "directives": None,
                    "selection_set": res,
                }
            ],
        }

    def converts_simple_schema_to_dict():
        ast = parse(
            """
            type Query {
              me: User
            }

            type User {
              id: ID
              name: String
            }
            """
        )
        res = ast_to_dict(ast)
        assert ast.to_dict() == res
        assert res == {
            "definitions": [
                {
                    "description": None,
                    "directives": [],
                    "fields": [
                        {
                            "arguments": [],
                            "description": None,
                            "directives": [],
                            "kind": "field_definition",
                            "name": {"kind": "name", "value": "me"},
                            "type": {
                                "kind": "named_type",
                                "name": {"kind": "name", "value": "User"},
                            },
                        }
                    ],
                    "interfaces": [],
                    "kind": "object_type_definition",
                    "name": {"kind": "name", "value": "Query"},
                },
                {
                    "description": None,
                    "directives": [],
                    "fields": [
                        {
                            "arguments": [],
                            "description": None,
                            "directives": [],
                            "kind": "field_definition",
                            "name": {"kind": "name", "value": "id"},
                            "type": {
                                "kind": "named_type",
                                "name": {"kind": "name", "value": "ID"},
                            },
                        },
                        {
                            "arguments": [],
                            "description": None,
                            "directives": [],
                            "kind": "field_definition",
                            "name": {"kind": "name", "value": "name"},
                            "type": {
                                "kind": "named_type",
                                "name": {"kind": "name", "value": "String"},
                            },
                        },
                    ],
                    "interfaces": [],
                    "kind": "object_type_definition",
                    "name": {"kind": "name", "value": "User"},
                },
            ],
            "kind": "document",
        }
        assert list(res)[0] == "kind"

    def converts_simple_schema_to_dict_with_locations():
        ast = parse(
            """
            type Query {
              me: User
            }

            type User {
              id: ID
              name: String
            }
            """
        )
        res = ast_to_dict(ast, locations=True)
        assert ast.to_dict(locations=True) == res
        assert res == {
            "definitions": [
                {
                    "description": None,
                    "directives": [],
                    "fields": [
                        {
                            "arguments": [],
                            "description": None,
                            "directives": [],
                            "kind": "field_definition",
                            "loc": {"end": 48, "start": 40},
                            "name": {
                                "kind": "name",
                                "loc": {"end": 42, "start": 40},
                                "value": "me",
                            },
                            "type": {
                                "kind": "named_type",
                                "loc": {"end": 48, "start": 44},
                                "name": {
                                    "kind": "name",
                                    "loc": {"end": 48, "start": 44},
                                    "value": "User",
                                },
                            },
                        }
                    ],
                    "interfaces": [],
                    "kind": "object_type_definition",
                    "loc": {"end": 62, "start": 13},
                    "name": {
                        "kind": "name",
                        "loc": {"end": 23, "start": 18},
                        "value": "Query",
                    },
                },
                {
                    "description": None,
                    "directives": [],
                    "fields": [
                        {
                            "arguments": [],
                            "description": None,
                            "directives": [],
                            "kind": "field_definition",
                            "loc": {"end": 108, "start": 102},
                            "name": {
                                "kind": "name",
                                "loc": {"end": 104, "start": 102},
                                "value": "id",
                            },
                            "type": {
                                "kind": "named_type",
                                "loc": {"end": 108, "start": 106},
                                "name": {
                                    "kind": "name",
                                    "loc": {"end": 108, "start": 106},
                                    "value": "ID",
                                },
                            },
                        },
                        {
                            "arguments": [],
                            "description": None,
                            "directives": [],
                            "kind": "field_definition",
                            "loc": {"end": 135, "start": 123},
                            "name": {
                                "kind": "name",
                                "loc": {"end": 127, "start": 123},
                                "value": "name",
                            },
                            "type": {
                                "kind": "named_type",
                                "loc": {"end": 135, "start": 129},
                                "name": {
                                    "kind": "name",
                                    "loc": {"end": 135, "start": 129},
                                    "value": "String",
                                },
                            },
                        },
                    ],
                    "interfaces": [],
                    "kind": "object_type_definition",
                    "loc": {"end": 149, "start": 76},
                    "name": {
                        "kind": "name",
                        "loc": {"end": 85, "start": 81},
                        "value": "User",
                    },
                },
            ],
            "kind": "document",
            "loc": {"end": 162, "start": 0},
        }
        keys = list(res)
        assert keys[0] == "kind"
        assert keys[-1] == "loc"
        assert list(res["loc"]) == ["start", "end"]

    def converts_simple_query_to_dict():
        ast = parse(
            """
            query HeroForEpisode($ep: Episode!) {
              hero(episode: $ep) {
                name
                ... on Droid {
                  primaryFunction
                }
                ... on Human {
                  height
                }
              }
            }
            """
        )
        res = ast_to_dict(ast)
        assert ast.to_dict() == res
        assert res == {
            "definitions": [
                {
                    "directives": [],
                    "kind": "operation_definition",
                    "name": {"kind": "name", "value": "HeroForEpisode"},
                    "operation": "query",
                    "selection_set": {
                        "kind": "selection_set",
                        "selections": [
                            {
                                "alias": None,
                                "arguments": [
                                    {
                                        "kind": "argument",
                                        "name": {"kind": "name", "value": "episode"},
                                        "value": {
                                            "kind": "variable",
                                            "name": {"kind": "name", "value": "ep"},
                                        },
                                    }
                                ],
                                "directives": [],
                                "kind": "field",
                                "name": {"kind": "name", "value": "hero"},
                                "selection_set": {
                                    "kind": "selection_set",
                                    "selections": [
                                        {
                                            "alias": None,
                                            "arguments": [],
                                            "directives": [],
                                            "kind": "field",
                                            "name": {"kind": "name", "value": "name"},
                                            "selection_set": None,
                                        },
                                        {
                                            "directives": [],
                                            "kind": "inline_fragment",
                                            "selection_set": {
                                                "kind": "selection_set",
                                                "selections": [
                                                    {
                                                        "alias": None,
                                                        "arguments": [],
                                                        "directives": [],
                                                        "kind": "field",
                                                        "name": {
                                                            "kind": "name",
                                                            "value": "primaryFunction",
                                                        },
                                                        "selection_set": None,
                                                    }
                                                ],
                                            },
                                            "type_condition": {
                                                "kind": "named_type",
                                                "name": {
                                                    "kind": "name",
                                                    "value": "Droid",
                                                },
                                            },
                                        },
                                        {
                                            "directives": [],
                                            "kind": "inline_fragment",
                                            "selection_set": {
                                                "kind": "selection_set",
                                                "selections": [
                                                    {
                                                        "alias": None,
                                                        "arguments": [],
                                                        "directives": [],
                                                        "kind": "field",
                                                        "name": {
                                                            "kind": "name",
                                                            "value": "height",
                                                        },
                                                        "selection_set": None,
                                                    }
                                                ],
                                            },
                                            "type_condition": {
                                                "kind": "named_type",
                                                "name": {
                                                    "kind": "name",
                                                    "value": "Human",
                                                },
                                            },
                                        },
                                    ],
                                },
                            }
                        ],
                    },
                    "variable_definitions": [
                        {
                            "default_value": None,
                            "directives": [],
                            "kind": "variable_definition",
                            "type": {
                                "kind": "non_null_type",
                                "type": {
                                    "kind": "named_type",
                                    "name": {"kind": "name", "value": "Episode"},
                                },
                            },
                            "variable": {
                                "kind": "variable",
                                "name": {"kind": "name", "value": "ep"},
                            },
                        }
                    ],
                }
            ],
            "kind": "document",
        }
        assert list(res)[0] == "kind"

    def converts_simple_query_to_dict_with_locations():
        ast = parse(
            """
            query HeroForEpisode($ep: Episode!) {
              hero(episode: $ep) {
                name
                ... on Droid {
                  primaryFunction
                }
                ... on Human {
                  height
                }
              }
            }
            """
        )
        res = ast_to_dict(ast, locations=True)
        assert ast.to_dict(locations=True) == res
        assert res == {
            "definitions": [
                {
                    "directives": [],
                    "kind": "operation_definition",
                    "loc": {"end": 293, "start": 13},
                    "name": {
                        "kind": "name",
                        "loc": {"end": 33, "start": 19},
                        "value": "HeroForEpisode",
                    },
                    "operation": "query",
                    "selection_set": {
                        "kind": "selection_set",
                        "loc": {"end": 293, "start": 49},
                        "selections": [
                            {
                                "alias": None,
                                "arguments": [
                                    {
                                        "kind": "argument",
                                        "loc": {"end": 82, "start": 70},
                                        "name": {
                                            "kind": "name",
                                            "loc": {"end": 77, "start": 70},
                                            "value": "episode",
                                        },
                                        "value": {
                                            "kind": "variable",
                                            "loc": {"end": 82, "start": 79},
                                            "name": {
                                                "kind": "name",
                                                "loc": {"end": 82, "start": 80},
                                                "value": "ep",
                                            },
                                        },
                                    }
                                ],
                                "directives": [],
                                "kind": "field",
                                "loc": {"end": 279, "start": 65},
                                "name": {
                                    "kind": "name",
                                    "loc": {"end": 69, "start": 65},
                                    "value": "hero",
                                },
                                "selection_set": {
                                    "kind": "selection_set",
                                    "loc": {"end": 279, "start": 84},
                                    "selections": [
                                        {
                                            "alias": None,
                                            "arguments": [],
                                            "directives": [],
                                            "kind": "field",
                                            "loc": {"end": 106, "start": 102},
                                            "name": {
                                                "kind": "name",
                                                "loc": {"end": 106, "start": 102},
                                                "value": "name",
                                            },
                                            "selection_set": None,
                                        },
                                        {
                                            "directives": [],
                                            "kind": "inline_fragment",
                                            "loc": {"end": 189, "start": 123},
                                            "selection_set": {
                                                "kind": "selection_set",
                                                "loc": {"end": 189, "start": 136},
                                                "selections": [
                                                    {
                                                        "alias": None,
                                                        "arguments": [],
                                                        "directives": [],
                                                        "kind": "field",
                                                        "loc": {
                                                            "end": 171,
                                                            "start": 156,
                                                        },
                                                        "name": {
                                                            "kind": "name",
                                                            "loc": {
                                                                "end": 171,
                                                                "start": 156,
                                                            },
                                                            "value": "primaryFunction",
                                                        },
                                                        "selection_set": None,
                                                    }
                                                ],
                                            },
                                            "type_condition": {
                                                "kind": "named_type",
                                                "loc": {"end": 135, "start": 130},
                                                "name": {
                                                    "kind": "name",
                                                    "loc": {"end": 135, "start": 130},
                                                    "value": "Droid",
                                                },
                                            },
                                        },
                                        {
                                            "directives": [],
                                            "kind": "inline_fragment",
                                            "loc": {"end": 263, "start": 206},
                                            "selection_set": {
                                                "kind": "selection_set",
                                                "loc": {"end": 263, "start": 219},
                                                "selections": [
                                                    {
                                                        "alias": None,
                                                        "arguments": [],
                                                        "directives": [],
                                                        "kind": "field",
                                                        "loc": {
                                                            "end": 245,
                                                            "start": 239,
                                                        },
                                                        "name": {
                                                            "kind": "name",
                                                            "loc": {
                                                                "end": 245,
                                                                "start": 239,
                                                            },
                                                            "value": "height",
                                                        },
                                                        "selection_set": None,
                                                    }
                                                ],
                                            },
                                            "type_condition": {
                                                "kind": "named_type",
                                                "loc": {"end": 218, "start": 213},
                                                "name": {
                                                    "kind": "name",
                                                    "loc": {"end": 218, "start": 213},
                                                    "value": "Human",
                                                },
                                            },
                                        },
                                    ],
                                },
                            }
                        ],
                    },
                    "variable_definitions": [
                        {
                            "default_value": None,
                            "directives": [],
                            "kind": "variable_definition",
                            "loc": {"end": 47, "start": 34},
                            "type": {
                                "kind": "non_null_type",
                                "loc": {"end": 47, "start": 39},
                                "type": {
                                    "kind": "named_type",
                                    "loc": {"end": 46, "start": 39},
                                    "name": {
                                        "kind": "name",
                                        "loc": {"end": 46, "start": 39},
                                        "value": "Episode",
                                    },
                                },
                            },
                            "variable": {
                                "kind": "variable",
                                "loc": {"end": 37, "start": 34},
                                "name": {
                                    "kind": "name",
                                    "loc": {"end": 37, "start": 35},
                                    "value": "ep",
                                },
                            },
                        }
                    ],
                }
            ],
            "kind": "document",
            "loc": {"end": 306, "start": 0},
        }
        keys = list(res)
        assert keys[0] == "kind"
        assert keys[-1] == "loc"
        assert list(res["loc"]) == ["start", "end"]
