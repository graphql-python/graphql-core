from functools import partial
from importlib import import_module

from graphql.utilities import get_introspection_query
from graphql.validation import MaxIntrospectionDepthRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, MaxIntrospectionDepthRule)

assert_valid = partial(assert_errors, errors=[])


def assert_errors_looking_up_fragments(query, errors, looked_up_fragments):
    class RuleLookingUpFragments(MaxIntrospectionDepthRule):
        def __init__(self, context):
            get_fragment = context.get_fragment

            def look_up_fragment(name):
                looked_up_fragments.append(name)
                return get_fragment(name)

            context.get_fragment = look_up_fragment
            super().__init__(context)

    assert_validation_errors(RuleLookingUpFragments, query, errors)


def describe_validate_max_introspection_nodes_rule():
    def default_introspection_query():
        assert_valid(get_introspection_query())

    def all_options_introspection_query():
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
                  ...Three
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

    def reuses_a_successful_fragment_check():
        looked_up_fragments: list[str] = []
        assert_errors_looking_up_fragments(
            """
            {
              first: __type(name: "Query") { ...Shared }
              second: __type(name: "Query") { ...Shared }
            }
            fragment Shared on __Type {
              interfaces { name }
            }
            """,
            [],
            looked_up_fragments,
        )
        assert looked_up_fragments == ["Shared"]

    def reuses_a_fragment_check_exceeding_the_depth():
        looked_up_fragments: list[str] = []
        assert_errors_looking_up_fragments(
            """
            {
              first: __type(name: "Query") { ...Shared }
              second: __type(name: "Query") { ...Shared }
            }
            fragment Shared on __Type {
              interfaces { interfaces { interfaces { name } } }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(4, 15)],
                },
            ],
            looked_up_fragments,
        )
        assert looked_up_fragments == ["Shared"]

    def checks_shared_fragments_at_different_depths():
        assert_errors(
            """
            {
              first: __type(name: "Query") { ...Fields }
              second: __type(name: "Query") { interfaces { ...Fields } }
              third: __type(name: "Query") { ...Fields }
              fourth: __type(name: "Query") { interfaces { interfaces { ...Fields } } }
              fifth: __type(name: "Query") { interfaces { interfaces { ...Fields } } }
            }
            fragment Fields on __Type {
              fields {
                name
              }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(6, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(7, 15)],
                },
            ],
        )

    def does_not_exceed_the_recursion_limit_on_long_fragment_chains(monkeypatch):
        # The rule on its own copes with this, without the limit in validate().
        module = import_module("graphql.validation.validate")
        monkeypatch.setattr(module, "MAX_NESTING_DEPTH", 10_000)
        n = 2000
        chain = "\n".join(
            f"fragment F{i} on __Type {{ name ...F{i + 1} }}" for i in range(n)
        )
        assert_valid(
            f'{{ __type(name: "Query") {{ ...F0 }} }}\n{chain}\n'
            f"fragment F{n} on __Type {{ name }}"
        )
        assert_errors(
            f'{{ __type(name: "Query") {{ ...F0 }} }}\n{chain}\n'
            f"fragment F{n} on __Type {{ fields {{ type {{ fields {{ type {{"
            " fields { name } } } } } }",
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(1, 3)],
                },
            ],
        )

    def reuses_fragment_checks_from_fields_exceeding_the_depth():
        looked_up_fragments: list[str] = []
        assert_errors_looking_up_fragments(
            """
            {
              first: __type(name: "Query") {
                ...Shared
                fields { fields { fields { name } } }
              }
              second: __type(name: "Query") {
                ...Shared
                fields { fields { fields { name } } }
              }
            }
            fragment Shared on __Type {
              ...Leaf
            }
            fragment Leaf on __Type {
              name
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(7, 15)],
                },
            ],
            looked_up_fragments,
        )
        assert looked_up_fragments == ["Shared", "Leaf"]

    def reuses_fragment_checks_exceeding_the_depth():
        looked_up_fragments: list[str] = []
        assert_errors_looking_up_fragments(
            """
            {
              first: __type(name: "Query") { ...Outer }
              second: __type(name: "Query") { interfaces { ...Outer } }
              third: __type(name: "Query") { name }
            }
            fragment Outer on __Type {
              ...Inner
            }
            fragment Inner on __Type {
              fields { fields { fields { name } } }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(4, 15)],
                },
            ],
            looked_up_fragments,
        )
        assert looked_up_fragments == ["Outer", "Inner"]

    def reuses_fragment_checks_completed_inside_a_fragment_cycle():
        assert_errors(
            """
            {
              first: __type(name: "Query") { ...Outer }
              second: __type(name: "Query") { ...Inner }
            }
            fragment Outer on __Type {
              ...Inner
              fields { fields { fields { name } } }
            }
            fragment Inner on __Type {
              ...Outer
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
            ],
        )

    def records_fragments_being_checked_when_reusing_an_exceeded_check():
        # A GraphQL-core-only test: the walk is iterative here, so the fragments on
        # the stack must also be recorded when the limit comes from the exceeded cache.
        looked_up_fragments: list[str] = []
        assert_errors_looking_up_fragments(
            """
            {
              first: __type(name: "Query") { ...Inner }
              second: __type(name: "Query") { ...Wrapper }
              third: __type(name: "Query") { ...Wrapper }
            }
            fragment Wrapper on __Type {
              ...Inner
            }
            fragment Inner on __Type {
              fields { fields { fields { name } } }
            }
            """,
            [
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(4, 15)],
                },
                {
                    "message": "Maximum introspection depth exceeded",
                    "locations": [(5, 15)],
                },
            ],
            looked_up_fragments,
        )
        assert looked_up_fragments == ["Inner", "Wrapper"]
