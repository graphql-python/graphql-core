from __future__ import annotations

from graphql.pyutils.suggestion_list import LexicalDistance


def describe_lexical_distance():
    def measures_distances_with_shared_prefix_and_suffix():
        assert LexicalDistance("abcdefgh").measure("abcdefxy", 3) == 2
        assert LexicalDistance("prefix_middle_suffix").measure("prefix_middie_suffix", 3) == 1

    def still_detects_transpositions_after_trimming():
        assert LexicalDistance("214365879").measure("123456789", 4) == 4
        assert LexicalDistance("aaaa").measure("aaab", 3) == 1
        assert LexicalDistance("aaaa").measure("aabb", 3) == 2

    def handles_empty_and_prefix_strings():
        assert LexicalDistance("").measure("", 3) == 0
        assert LexicalDistance("").measure("abc", 3) == 3
        assert LexicalDistance("abc").measure("abcdef", 3) == 3
        assert LexicalDistance("abcdef").measure("abc", 3) == 3

    def counts_case_changes_as_one_edit():
        assert LexicalDistance("verylongstring").measure("VERYLONGSTRING", 3) == 1
        assert LexicalDistance("A").measure("a", 0) == 1

    def returns_none_when_the_distance_exceeds_the_threshold():
        assert LexicalDistance("aaaa").measure("abbb", 2) is None
        assert LexicalDistance("ab").measure("ca", 1) is None
