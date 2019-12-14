from graphql.pyutils import did_you_mean


def describe_did_you_mean():
    def does_accept_an_empty_list():
        assert did_you_mean([]) == ""

    def handles_single_suggestion():
        assert did_you_mean(["A"]) == " Did you mean 'A'?"

    def handles_two_suggestions():
        assert did_you_mean(["A", "B"]) == " Did you mean 'A' or 'B'?"

    def handles_multiple_suggestions():
        assert did_you_mean(["A", "B", "C"]) == " Did you mean 'A', 'B', or 'C'?"

    def limits_to_five_suggestions():
        assert (
            did_you_mean(["A", "B", "C", "D", "E", "F"])
            == " Did you mean 'A', 'B', 'C', 'D', or 'E'?"
        )

    def adds_sub_message():
        assert did_you_mean(["A"], "the letter") == " Did you mean the letter 'A'?"
