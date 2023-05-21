from functools import partial

from graphql.validation import DeferStreamDirectiveLabel

from .harness import assert_validation_errors


assert_errors = partial(assert_validation_errors, DeferStreamDirectiveLabel)

assert_valid = partial(assert_errors, errors=[])


def describe_defer_stream_label():
    def defer_fragments_with_no_label():
        assert_valid(
            """
            {
              dog {
                ...dogFragmentA @defer
                ...dogFragmentB @defer
              }
            }
            fragment dogFragmentA on Dog {
              name
            }
            fragment dogFragmentB on Dog {
              nickname
            }
            """
        )

    def defer_fragments_one_with_label_one_without():
        assert_valid(
            """
            {
              dog {
                ...dogFragmentA @defer(label: "fragA")
                ...dogFragmentB @defer
              }
            }
            fragment dogFragmentA on Dog {
              name
            }
            fragment dogFragmentB on Dog {
              nickname
            }
            """
        )

    def defer_fragment_with_variable_label():
        assert_errors(
            """
            query($label: String) {
              dog {
                ...dogFragmentA @defer(label: $label)
                ...dogFragmentB @defer(label: "fragA")
              }
            }
            fragment dogFragmentA on Dog {
              name
            }
            fragment dogFragmentB on Dog {
              nickname
            }
            """,
            [
                {
                    "message": "Defer directive label argument"
                    " must be a static string.",
                    "locations": [(4, 33)],
                },
            ],
        )

    def defer_fragments_with_different_labels():
        assert_valid(
            """
            {
              dog {
                ...dogFragmentA @defer(label: "fragB")
                ...dogFragmentB @defer(label: "fragA")
              }
            }
            fragment dogFragmentA on Dog {
              name
            }
            fragment dogFragmentB on Dog {
              nickname
            }
            """
        )

    def defer_fragments_with_same_labels():
        assert_errors(
            """
            {
              dog {
                ...dogFragmentA @defer(label: "fragA")
                ...dogFragmentB @defer(label: "fragA")
              }
            }
            fragment dogFragmentA on Dog {
              name
            }
            fragment dogFragmentB on Dog {
              nickname
            }
            """,
            [
                {
                    "message": "Defer/Stream directive label argument must be unique.",
                    "locations": [(4, 33), (5, 33)],
                },
            ],
        )

    def defer_and_stream_with_no_label():
        assert_valid(
            """
            {
              dog {
                ...dogFragment @defer
              }
              pets @stream(initialCount: 0) @stream {
                name
              }
            }
            fragment dogFragment on Dog {
              name
            }
            """
        )

    def stream_with_variable_label():
        assert_errors(
            """
            query ($label: String!) {
              dog {
                ...dogFragment @defer
              }
              pets @stream(initialCount: 0) @stream(label: $label) {
                name
              }
            }
            fragment dogFragment on Dog {
              name
            }
            """,
            [
                {
                    "message": "Stream directive label argument"
                    " must be a static string.",
                    "locations": [(6, 45)],
                },
            ],
        )

    def defer_and_stream_with_the_same_labels():
        assert_errors(
            """
            {
              dog {
                ...dogFragment @defer(label: "MyLabel")
              }
              pets @stream(initialCount: 0) @stream(label: "MyLabel") {
                name
              }
            }
            fragment dogFragment on Dog {
              name
            }
            """,
            [
                {
                    "message": "Defer/Stream directive label argument must be unique.",
                    "locations": [(4, 32), (6, 45)],
                },
            ],
        )

    def no_defer_or_stream_directive_with_variable_and_duplicate_label():
        assert_valid(
            """
            query($label: String) {
                dog @skip(label: $label)
                dog @skip(label: $label)
            }
            """
        )
