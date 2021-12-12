from string import ascii_letters as letters, digits, punctuation

from graphql.language.character_classes import (
    is_digit,
    is_letter,
    is_name_start,
    is_name_continue,
)

non_ascii = "¯＿±¹²³½£ºµÄäÖöØø×〇᧐〸αΑωΩ"


def describe_digit():
    def accepts_digits():
        assert all(is_digit(char) for char in digits)

    def rejects_letters():
        assert not any(is_digit(char) for char in letters)

    def rejects_underscore():
        assert not is_digit("_")

    def rejects_punctuation():
        assert not any(is_digit(char) for char in punctuation)

    def rejects_non_ascii():
        assert not any(is_digit(char) for char in non_ascii)

    def rejects_empty_string():
        assert not is_digit("")


def describe_letter():
    def accepts_letters():
        assert all(is_letter(char) for char in letters)

    def rejects_digits():
        assert not any(is_letter(char) for char in digits)

    def rejects_underscore():
        assert not is_letter("_")

    def rejects_punctuation():
        assert not any(is_letter(char) for char in punctuation)

    def rejects_non_ascii():
        assert not any(is_letter(char) for char in non_ascii)

    def rejects_empty_string():
        assert not is_letter("")


def describe_name_start():
    def accepts_letters():
        assert all(is_name_start(char) for char in letters)

    def accepts_underscore():
        assert is_name_start("_")

    def rejects_digits():
        assert not any(is_name_start(char) for char in digits)

    def rejects_punctuation():
        assert not any(is_name_start(char) for char in punctuation if char != "_")

    def rejects_non_ascii():
        assert not any(is_name_start(char) for char in non_ascii)

    def rejects_empty_string():
        assert not is_name_start("")


def describe_name_continue():
    def accepts_letters():
        assert all(is_name_continue(char) for char in letters)

    def accepts_digits():
        assert all(is_name_continue(char) for char in digits)

    def accepts_underscore():
        assert is_name_continue("_")

    def rejects_punctuation():
        assert not any(is_name_continue(char) for char in punctuation if char != "_")

    def rejects_non_ascii():
        assert not any(is_name_continue(char) for char in non_ascii)

    def rejects_empty_string():
        assert not is_name_continue("")
