import gc
import sys
import weakref
from functools import cache

import pytest

from graphql.error import GraphQLError
from graphql.language import parse
from graphql.language.parser import MAX_NESTING_DEPTH
from graphql.utilities import build_schema
from graphql.validation import (
    FieldsOnCorrectTypeRule,
    NoFragmentCyclesRule,
    OverlappingFieldsCanBeMergedRule,
    ValidationRule,
    validate,
)
from graphql.validation import validation_context as validation_context_module
from graphql.validation.validate import ValidationAbortedError

from .harness import test_schema


def describe_validate_supports_full_validation():
    def handles_a_rule_abort_without_discarding_previous_errors():
        class AbortingRule(ValidationRule):
            def enter_document(self, *_args):
                self.report_error(GraphQLError("Earlier error."))
                msg = "Validation aborted."
                raise ValidationAbortedError(msg)

        errors = validate(test_schema, parse("{ human { name } }"), [AbortingRule])
        assert [error.message for error in errors] == [
            "Earlier error.",
            "Validation aborted.",
        ]

    def validates_queries():
        doc = parse(
            """
            query {
              human {
                pets {
                  ... on Cat {
                    meowsVolume
                  }
                  ... on Dog {
                    barkVolume
                  }
                }
              }
            }
            """
        )

        errors = validate(test_schema, doc)
        assert errors == []

    def detects_unknown_fields():
        doc = parse(
            """
            {
              unknown
            }
            """
        )

        errors = validate(test_schema, doc)
        assert errors == [
            {"message": "Cannot query field 'unknown' on type 'QueryRoot'."}
        ]

    def validates_using_a_custom_rule():
        schema = build_schema(
            """
            directive @custom(arg: String) on FIELD

            type Query {
              foo: String
            }
            """
        )

        doc = parse(
            """
            query {
              name @custom
            }
            """
        )

        class CustomRule(ValidationRule):
            def enter_directive(self, node, *_args):
                directive_def = self.context.get_directive()
                error = GraphQLError("Reporting directive: " + str(directive_def), node)
                self.context.report_error(error)

        errors = validate(schema, doc, [CustomRule])
        assert errors == [
            {"message": "Reporting directive: @custom", "locations": [(3, 20)]}
        ]


def describe_validate_limit_maximum_number_of_validation_errors():
    query = """
        {
          firstUnknownField
          secondUnknownField
          thirdUnknownField
        }
        """
    doc = parse(query, no_location=True)

    def _validate_document(max_errors=None):
        return validate(test_schema, doc, max_errors=max_errors)

    def _invalid_field_error(field_name: str):
        return {
            "message": f"Cannot query field '{field_name}' on type 'QueryRoot'.",
        }

    def when_max_errors_is_equal_to_number_of_errors():
        errors = _validate_document(max_errors=3)
        assert errors == [
            _invalid_field_error("firstUnknownField"),
            _invalid_field_error("secondUnknownField"),
            _invalid_field_error("thirdUnknownField"),
        ]

    def when_max_errors_is_less_than_number_of_errors():
        errors = _validate_document(max_errors=2)
        assert errors == [
            _invalid_field_error("firstUnknownField"),
            _invalid_field_error("secondUnknownField"),
            {
                "message": "Too many validation errors, error limit reached."
                " Validation aborted."
            },
        ]

    def limits_to_100_when_max_errors_is_not_passed():
        errors = validate(
            test_schema,
            parse(
                "{" + " ".join(f"unknownField{n}" for n in range(120)) + "}",
                no_location=True,
            ),
        )
        assert len(errors) == 101
        assert errors[0] == _invalid_field_error("unknownField0")
        assert errors[-2] == _invalid_field_error("unknownField99")
        assert errors[-1] == {
            "message": "Too many validation errors, error limit reached."
            " Validation aborted."
        }

    class ReportWhileHandlingErrorRule(ValidationRule):
        def enter_field(self, node, *_args):
            try:
                raise RuntimeError("Handled error from custom rule!")
            except RuntimeError:
                self.report_error(GraphQLError("Error from custom rule!", node))

    def _validate_and_track(rules, count=3):
        # Run aborted validations with fresh documents, keep the aborted errors,
        # and track the documents and contexts with weak references. The other
        # errors are dropped, since errors created while handling an exception
        # keep its traceback on purpose.
        aborted_errors, refs = [], []

        class TrackContextRule(ValidationRule):
            def __init__(self, context):
                super().__init__(context)
                refs.append(weakref.ref(context))

        for _ in range(count):
            document = parse(query, no_location=True)
            refs.append(weakref.ref(document))
            errors = validate(
                test_schema, document, [TrackContextRule, *rules], max_errors=1
            )
            assert len(errors) == 2
            aborted_errors.append(errors[-1])
            del document, errors
        gc.collect()
        return aborted_errors, refs

    def creates_a_new_error_for_every_aborted_validation():
        first_error = _validate_document(max_errors=1)[-1]
        second_error = _validate_document(max_errors=1)[-1]
        assert type(first_error) is ValidationAbortedError
        assert type(second_error) is ValidationAbortedError
        assert first_error == second_error
        assert first_error is not second_error

    def returns_the_aborted_error_without_traceback_and_context():
        error = _validate_document(max_errors=1)[-1]
        assert isinstance(error, ValidationAbortedError)
        assert error.__traceback__ is None
        assert error.__context__ is None
        assert error.__cause__ is None

    def returns_the_aborted_error_without_context_of_a_handled_error():
        errors = validate(
            test_schema, doc, [ReportWhileHandlingErrorRule], max_errors=1
        )
        assert len(errors) == 2
        error = errors[-1]
        assert isinstance(error, ValidationAbortedError)
        assert error.__traceback__ is None
        assert error.__context__ is None
        assert error.__cause__ is None

    def does_not_keep_aborted_validations_alive():
        aborted_errors, refs = _validate_and_track([FieldsOnCorrectTypeRule])
        assert all(isinstance(e, ValidationAbortedError) for e in aborted_errors)
        assert len(refs) == 6
        assert all(ref() is None for ref in refs)

    def does_not_keep_validations_alive_that_were_aborted_while_handling_errors():
        aborted_errors, refs = _validate_and_track([ReportWhileHandlingErrorRule])
        assert all(isinstance(e, ValidationAbortedError) for e in aborted_errors)
        assert len(refs) == 6
        assert all(ref() is None for ref in refs)

    def aborted_error_accepts_the_arguments_of_graphql_error():
        node = doc.definitions[0]
        error = ValidationAbortedError(
            "Validation aborted.", node, extensions={"code": "ABORTED"}
        )
        assert error.message == "Validation aborted."
        assert error.nodes == [node]
        assert error.extensions == {"code": "ABORTED"}

    def pass_through_exceptions_from_rules():
        class CustomRule(ValidationRule):
            def enter_field(self, *_args):
                raise RuntimeError("Error from custom rule!")

        with pytest.raises(RuntimeError, match=r"^Error from custom rule!$"):
            validate(test_schema, doc, [CustomRule], max_errors=1)


def describe_validate_limits_fragment_work():
    schema = build_schema("type Query { name(arg: String): String }")

    def _document(num_operations: int, num_fragments: int):
        # operations with distinct entry fragments sharing one chain of fragments
        operations = (
            f"query Q{i}($v: String) {{ ...A{i} }}" for i in range(num_operations)
        )
        entries = (f"fragment A{i} on Query {{ ...F0 }}" for i in range(num_operations))
        chain = (
            f"fragment F{i} on Query {{ ...F{i + 1} }}"
            for i in range(num_fragments - 1)
        )
        last = f"fragment F{num_fragments - 1} on Query {{ name(arg: $v) }}"
        return parse("\n".join([*operations, *entries, *chain, last]))

    def validates_shared_fragments_within_the_budget():
        assert validate(schema, _document(10, 10)) == []

    def aborts_validation_when_the_fragment_work_is_exhausted(monkeypatch):
        monkeypatch.setattr(validation_context_module, "MAX_FRAGMENT_WORK", 100)
        errors = validate(schema, _document(10, 10))
        assert len(errors) == 1
        error = errors[0]
        assert type(error) is ValidationAbortedError
        assert error.message == "Validation aborted."
        assert error.locations is None
        assert error.__traceback__ is None
        assert error.__context__ is None

    def reads_the_budget_when_the_validation_starts(monkeypatch):
        document = _document(10, 10)
        monkeypatch.setattr(validation_context_module, "MAX_FRAGMENT_WORK", 100)
        assert len(validate(schema, document)) == 1
        monkeypatch.setattr(validation_context_module, "MAX_FRAGMENT_WORK", 10_000)
        assert validate(schema, document) == []


def describe_validate_aborts_on_too_deeply_nested_fragments():
    schema = build_schema("type Query { name: String, query: Query }")

    # Far beyond the recursion limit on all interpreters.
    depth = 10_000

    selections = {
        "fragment chain": "...F{next}",
        "chain with fields": "name ...F{next}",
        "chain through fields": "query {{ ...F{next} }}",
    }

    @cache
    def _document(shape: str):
        chain = "\n".join(
            f"fragment F{i} on Query {{ {selections[shape].format(next=i + 1)} }}"
            for i in range(depth)
        )
        return parse(
            f"query First {{ missing }} query Second {{ ...F0 }}"
            f" {chain} fragment F{depth} on Query {{ name }}",
            no_location=True,
        )

    def _assert_aborted(error: GraphQLError):
        assert type(error) is ValidationAbortedError
        assert error.message == "Validation aborted."
        assert error.locations is None
        assert error.__traceback__ is None
        assert error.__context__ is None
        assert error.__cause__ is None

    @pytest.mark.parametrize("shape", selections)
    @pytest.mark.usefixtures("without_nesting_limit")
    def keeps_previous_errors_with_the_default_rules(shape: str):
        errors = validate(schema, _document(shape))
        assert len(errors) > 1
        assert errors[0].message == "Cannot query field 'missing' on type 'Query'."
        _assert_aborted(errors[-1])

    @pytest.mark.parametrize(
        ("shape", "rule"),
        [
            ("fragment chain", NoFragmentCyclesRule),
            ("chain with fields", NoFragmentCyclesRule),
            ("chain with fields", OverlappingFieldsCanBeMergedRule),
            ("chain through fields", NoFragmentCyclesRule),
        ],
    )
    @pytest.mark.usefixtures("without_nesting_limit")
    def aborts_with_the_failing_rule_alone(shape: str, rule):
        errors = validate(schema, _document(shape), [rule])
        assert len(errors) == 1
        _assert_aborted(errors[0])

    @pytest.mark.parametrize("shape", selections)
    @pytest.mark.usefixtures("without_nesting_limit")
    def keeps_previous_errors_with_the_failing_rule(shape: str):
        errors = validate(
            schema, _document(shape), [FieldsOnCorrectTypeRule, NoFragmentCyclesRule]
        )
        assert [error.message for error in errors] == [
            "Cannot query field 'missing' on type 'Query'.",
            "Validation aborted.",
        ]
        _assert_aborted(errors[-1])

    def _chain(length: int, selection: str = "...F{next}", head: str = "{ ...F0 }"):
        chain = " ".join(
            f"fragment F{i} on Query {{ {selection.format(next=i + 1)} }}"
            for i in range(length)
        )
        return parse(f"{head} {chain} fragment F{length} on Query {{ name }}")

    def accepts_chains_up_to_the_maximum_nesting_depth():
        document = _chain(MAX_NESTING_DEPTH - 2)
        assert validate(schema, document) == []
        document = _chain(
            (MAX_NESTING_DEPTH - 2) // 2, "query {{ ...F{next} }}", "{ ...F0 }"
        )
        assert validate(schema, document) == []

    def aborts_on_chains_above_the_maximum_nesting_depth():
        document = _chain(MAX_NESTING_DEPTH - 1)
        errors = validate(schema, document)
        assert len(errors) == 1
        _assert_aborted(errors[0])

    def aborts_on_chains_through_fields_above_the_maximum_nesting_depth():
        document = _chain(MAX_NESTING_DEPTH // 2, "query {{ ...F{next} }}")
        errors = validate(schema, document, [FieldsOnCorrectTypeRule])
        assert len(errors) == 1
        _assert_aborted(errors[0])

    def counts_nesting_within_the_definitions_through_inline_fragments():
        def nested(inner: str) -> str:
            return "... on Query { " * 100 + inner + " }" * 100

        document = parse(
            f"{{ ...A }} fragment A on Query {{ {nested('...B')} }}"
            f" fragment B on Query {{ {nested('...C')} }}"
            f" fragment C on Query {{ {nested('name')} }}"
        )
        errors = validate(schema, document, [FieldsOnCorrectTypeRule])
        assert len(errors) == 1
        _assert_aborted(errors[0])

    def does_not_add_up_the_nesting_of_sibling_selections():
        nested = "... on Query { " * 100 + "name" + " }" * 100
        document = parse(
            f"{{ ...A }} fragment A on Query {{ {nested} ...B }}"
            f" fragment B on Query {{ {nested} ...C }}"
            f" fragment C on Query {{ {nested} }}"
        )
        assert validate(schema, document) == []

    def checks_all_operations():
        document = _chain(
            MAX_NESTING_DEPTH - 1, head="query A { name } query B { ...F0 }"
        )
        errors = validate(schema, document, [FieldsOnCorrectTypeRule])
        assert len(errors) == 1
        _assert_aborted(errors[0])

    def checks_fragments_that_no_operation_uses():
        document = _chain(MAX_NESTING_DEPTH, head="{ name }")
        errors = validate(schema, document, [FieldsOnCorrectTypeRule])
        assert len(errors) == 1
        _assert_aborted(errors[0])

    def aborts_on_a_long_fragment_cycle():
        length = MAX_NESTING_DEPTH + 1
        spreads = " ".join(
            f"fragment F{i} on Query {{ ...F{(i + 1) % length} }}"
            for i in range(length)
        )
        errors = validate(
            schema, parse(f"{{ ...F0 }} {spreads}"), [FieldsOnCorrectTypeRule]
        )
        assert len(errors) == 1
        _assert_aborted(errors[0])

    def reports_short_fragment_cycles_and_unknown_fragments_as_before():
        document = parse(
            "{ ...A ...A ...Unknown }"
            " fragment A on Query { ...B ...B ...C }"
            " fragment B on Query { ...A }"
            " fragment C on Query { name }"
        )
        messages = [error.message for error in validate(schema, document)]
        assert "Unknown fragment 'Unknown'." in messages
        assert "Cannot spread fragment 'A' within itself via 'B'." in messages

    def does_not_abort_when_the_chain_fits():
        document = parse(
            "{ ...F0 }"
            + " ".join(f"fragment F{i} on Query {{ ...F{i + 1} }}" for i in range(100))
            + " fragment F100 on Query { name }"
        )
        assert validate(schema, document) == []

    def aborts_on_a_fragment_spreading_itself_with_an_argument():
        document = parse(
            "{ name ...A(x: 1) } fragment A($x: Int) on Query { name ...A(x: $x) }",
            experimental_fragment_arguments=True,
        )
        for rules in (None, [OverlappingFieldsCanBeMergedRule]):
            errors = validate(schema, document, rules)
            assert len(errors) == 1
            _assert_aborted(errors[0])

    def keeps_previous_errors_on_a_fragment_spreading_itself_with_an_argument():
        document = parse(
            "query First { missing } query Second { name ...A(x: 1) }"
            " fragment A($x: Int) on Query { name ...A(x: $x) }",
            experimental_fragment_arguments=True,
        )
        errors = validate(
            schema,
            document,
            [FieldsOnCorrectTypeRule, OverlappingFieldsCanBeMergedRule],
        )
        assert [error.message for error in errors] == [
            "Cannot query field 'missing' on type 'Query'.",
            "Validation aborted.",
        ]
        _assert_aborted(errors[-1])

    def does_not_keep_the_frames_of_the_recursion_alive():
        refs: list[weakref.ref] = []

        class Tracked:
            pass

        class RecursingRule(ValidationRule):
            def enter_document(self, *_args):
                def recurse():
                    tracked = Tracked()
                    refs.append(weakref.ref(tracked))
                    recurse()

                recurse()

        errors = validate(schema, parse("{ name }"), [RecursingRule])
        gc.collect()
        assert len(refs) > 10
        assert all(ref() is None for ref in refs)
        assert len(errors) == 1
        _assert_aborted(errors[0])

    @pytest.mark.skipif(
        sys.implementation.name == "pypy",
        reason="The JIT of PyPy can keep these objects alive.",
    )
    @pytest.mark.usefixtures("without_nesting_limit")
    def does_not_keep_the_document_alive():
        document = parse(
            "{ ...F0 } "
            + " ".join(
                f"fragment F{i} on Query {{ ...F{i + 1} }}" for i in range(depth)
            )
            + f" fragment F{depth} on Query {{ name }}",
            no_location=True,
        )
        ref = weakref.ref(document)
        errors = validate(schema, document, [NoFragmentCyclesRule])
        del document
        gc.collect()
        assert ref() is None
        _assert_aborted(errors[0])


def describe_operation_and_variable_definition_descriptions():
    def validates_operation_with_description_and_variable_descriptions():
        schema = build_schema("type Query { field(a: Int, b: String): String }")
        query = '''
            "Operation description"
            query myQuery(
              "Variable a description"
              $a: Int,
              """Variable b\nmultiline description"""
              $b: String
            ) {
              field(a: $a, b: $b)
            }
            '''
        ast = parse(query)
        errors = validate(schema, ast)
        assert errors == []
