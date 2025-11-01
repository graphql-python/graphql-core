from functools import partial

from graphql.utilities import get_introspection_query
from graphql.validation import MaxIntrospectionDepthRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, MaxIntrospectionDepthRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_max_introspection_nodes_rule():
    def default_introspection_query():
        assert_valid(get_introspection_query())

    def all_ptions_introspection_query():
        assert_valid(
            get_introspection_query(
                descriptions=True,
                specified_by_url=True,
                directive_is_repeatable=True,
                schema_description=True,
                input_value_deprecation=True,
            )
        )

    def three_flat_fields_introspection_query():
        assert_valid(
            """
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
        )

    def three_fields_deep_introspection_query_from_schema():
        assert_errors(
            """
            {
              __schema {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_interfaces_deep_introspection_query_from_schema():
        assert_errors(
            """
            {
              __schema {
                types {
                  interfaces {
                    interfaces {
                      interfaces {
                        name
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_possible_types_deep_introspection_query_from_schema():
        assert_errors(
            """
            {
              __schema {
                types {
                  possibleTypes {
                    possibleTypes {
                      possibleTypes {
                        name
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_input_fields_deep_introspection_query_from_schema():
        assert_errors(
            """
            {
              __schema {
                types {
                  inputFields {
                    type {
                      inputFields {
                        type {
                          inputFields {
                            type {
                              name
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_fields_deep_introspection_query_from_multiple_schema():
        assert_errors(
            """
            {
              one: __schema {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
              two: __schema {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
              three: __schema {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(18, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(33, 15)],
                },
            ],
        )

    def three_fields_deep_introspection_query_from_type():
        assert_errors(
            """
            {
              __type(name: "Query") {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_fields_deep_introspection_query_from_multiple_type():
        assert_errors(
            """
            {
              one: __type(name: "Query") {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
              two: __type(name: "Query") {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
              three: __type(name: "Query") {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          fields {
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
""",
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(18, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(33, 15)],
                },
            ],
        )

    def one_fields_deep_with_three_fields_introspection_query():
        assert_valid(
            """
            {
              __schema {
                types {
                  fields {
                    type {
                      oneFields: fields {
                        name
                      }
                      twoFields: fields {
                        name
                      }
                      threeFields: fields {
                        name
                      }
                    }
                  }
                }
              }
            }
            """
        )

    def three_fields_deep_from_varying_parents_introspection_query():
        assert_errors(
            """
            {
              __schema {
                types {
                  fields {
                    type {
                      fields {
                        type {
                          ofType {
                            fields {
                              name
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_fields_deep_introspection_query_with_inline_fragments():
        assert_errors(
            """
            query test {
              __schema {
                types {
                  ... on __Type {
                    fields {
                      type {
                        ... on __Type {
                          ofType {
                            fields {
                              type {
                                ... on __Type {
                                  fields {
                                    name
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_fields_deep_introspection_query_with_fragments():
        assert_errors(
            """
            query test {
              __schema {
                types {
                  ...One
                }
              }
            }

            fragment One on __Type {
              fields {
                type {
                  ...Two
                }
              }
            }

            fragment Two on __Type {
              fields {
                type {
                  ...Three
                }
              }
            }

            fragment Three on __Type {
              fields {
                name
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def three_fields_deep_inline_fragment_on_query():
        assert_errors(
            """
            {
              ... {
                __schema { types { fields { type { fields { type { fields { name } } } } } } }
              }
            }
            """,  # noqa: E501
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(4, 17)],
                },
            ],
        )

    def opts_out_if_fragment_is_missing():
        assert_valid(
            """
            query test {
              __schema {
                types {
                  ...Missing
                }
              }
            }
            """
        )

    def does_not_infinitely_recurse_on_fragment_cycle():
        assert_valid(
            """
            query test {
              __schema {
                types {
                  ...Cycle
                }
              }
            }
            fragment Cycle on __Type {
              ...Cycle
            }
            """
        )
