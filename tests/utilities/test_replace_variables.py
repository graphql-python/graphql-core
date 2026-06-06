from typing import Any

from graphql.execution.values import get_variable_values
from graphql.language import TokenKind, parse_value
from graphql.language.parser import Parser
from graphql.type import GraphQLInt, GraphQLSchema
from graphql.utilities import replace_variables


def _parse_value(ast: str):
    return parse_value(ast, no_location=True)


def _test_variables(variable_defs: str, inputs: dict[str, Any]):
    parser = Parser(variable_defs, no_location=True)
    parser.expect_token(TokenKind.SOF)
    variable_values = get_variable_values(
        GraphQLSchema(types=[GraphQLInt]),
        parser.parse_variable_definitions(),
        inputs,
    )
    assert not isinstance(variable_values, list)
    return variable_values


def describe_replace_variables():
    def describe_operation_variables():
        def does_not_change_simple_ast():
            ast = _parse_value("null")
            assert replace_variables(ast, None) is ast

        def replaces_simple_variables():
            ast = _parse_value("$var")
            vars_ = _test_variables("($var: Int)", {"var": 123})
            assert replace_variables(ast, vars_) == _parse_value("123")

        def replaces_variables_with_default_values():
            ast = _parse_value("$var")
            vars_ = _test_variables("($var: Int = 123)", {})
            assert replace_variables(ast, vars_) == _parse_value("123")

        def replaces_nested_variables():
            ast = _parse_value("{ foo: [ $var ], bar: $var }")
            vars_ = _test_variables("($var: Int)", {"var": 123})
            assert replace_variables(ast, vars_) == _parse_value(
                "{ foo: [ 123 ], bar: 123 }"
            )

        def replaces_missing_variables_with_null():
            ast = _parse_value("$var")
            assert replace_variables(ast, None) == _parse_value("null")

        def replaces_missing_variable_declaration_with_null():
            ast = _parse_value("$var")
            vars_ = _test_variables("", {})
            assert replace_variables(ast, vars_) == _parse_value("null")

        def replaces_misspelled_variable_declaration_with_null():
            ast = _parse_value("$var1")
            vars_ = _test_variables("($var2: Int)", {"var2": 123})
            assert replace_variables(ast, vars_) == _parse_value("null")

        def replaces_missing_variables_in_lists_with_null():
            ast = _parse_value("[1, $var]")
            assert replace_variables(ast, None) == _parse_value("[1, null]")

        def omits_missing_variables_from_objects():
            ast = _parse_value("{ foo: 1, bar: $var }")
            vars_ = _test_variables("($wrongVar: Int)", {"var": 123})
            assert replace_variables(ast, vars_) == _parse_value("{ foo: 1 }")

    def describe_fragment_variables():
        def replaces_simple_fragment_variables():
            ast = _parse_value("$var")
            fragment_vars = _test_variables("($var: Int)", {"var": 123})
            assert replace_variables(ast, None, fragment_vars) == _parse_value("123")

        def replaces_simple_fragment_variables_overlapping_with_operation_variables():
            ast = _parse_value("$var")
            operation_vars = _test_variables("($var: Int)", {"var": 123})
            fragment_vars = _test_variables("($var: Int)", {"var": 456})
            assert replace_variables(
                ast, operation_vars, fragment_vars
            ) == _parse_value("456")

        def replaces_fragment_variables_with_default_values():
            ast = _parse_value("$var")
            fragment_vars = _test_variables("($var: Int = 123)", {})
            assert replace_variables(ast, None, fragment_vars) == _parse_value("123")

        def replaces_fragment_var_default_values_overlapping_with_operation_variables():
            ast = _parse_value("$var")
            operation_vars = _test_variables("($var: Int = 123)", {})
            fragment_vars = _test_variables("($var: Int = 456)", {})
            assert replace_variables(
                ast, operation_vars, fragment_vars
            ) == _parse_value("456")

        def replaces_nested_fragment_variables():
            ast = _parse_value("{ foo: [ $var ], bar: $var }")
            fragment_vars = _test_variables("($var: Int)", {"var": 123})
            assert replace_variables(ast, None, fragment_vars) == _parse_value(
                "{ foo: [ 123 ], bar: 123 }"
            )

        def replaces_nested_fragment_variables_overlapping_with_operation_variables():
            ast = _parse_value("{ foo: [ $var ], bar: $var }")
            operation_vars = _test_variables("($var: Int)", {"var": 123})
            fragment_vars = _test_variables("($var: Int)", {"var": 456})
            assert replace_variables(
                ast, operation_vars, fragment_vars
            ) == _parse_value("{ foo: [ 456 ], bar: 456 }")

        def replaces_missing_fragment_variables_with_null():
            ast = _parse_value("$var")
            assert replace_variables(ast, None, None) == _parse_value("null")

        def replaces_missing_fragment_variables_with_null_overlapping_with_operation():
            ast = _parse_value("$var")
            operation_vars = _test_variables("($var: Int)", {"var": 123})
            fragment_vars = _test_variables("($var: Int)", {})
            assert replace_variables(
                ast, operation_vars, fragment_vars
            ) == _parse_value("null")

        def replaces_missing_fragment_variables_in_lists_with_null():
            ast = _parse_value("[1, $var]")
            assert replace_variables(ast, None, None) == _parse_value("[1, null]")

        def replaces_missing_fragment_vars_in_lists_with_null_overlapping_operation():
            ast = _parse_value("[1, $var]")
            operation_vars = _test_variables("($var: Int)", {"var": 123})
            fragment_vars = _test_variables("($var: Int)", {})
            assert replace_variables(
                ast, operation_vars, fragment_vars
            ) == _parse_value("[1, null]")

        def omits_missing_fragment_variables_from_objects():
            ast = _parse_value("{ foo: 1, bar: $var }")
            assert replace_variables(ast, None, None) == _parse_value("{ foo: 1 }")

        def omits_missing_fragment_variables_from_objects_overlapping_with_operation():
            ast = _parse_value("{ foo: 1, bar: $var }")
            operation_vars = _test_variables("($var: Int)", {"var": 123})
            fragment_vars = _test_variables("($var: Int)", {})
            assert replace_variables(
                ast, operation_vars, fragment_vars
            ) == _parse_value("{ foo: 1 }")
