from . import dedent


def describe_dedent():
    def removes_indentation_in_typical_usage():
        assert (
            dedent(
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
            == "type Query {\n  me: User\n}\n\n"
            "type User {\n  id: ID\n  name: String\n}"
        )

    def removes_only_the_first_level_of_indentation():
        assert (
            dedent(
                """
                first
                  second
                    third
                      fourth
                """
            )
            == "first\n  second\n    third\n      fourth"
        )

    def does_not_escape_special_characters():
        assert (
            dedent(
                """
                type Root {
                  field(arg: String = "wi\th de\fault"): String
                }
                """
            )
            == "type Root {\n"
            '  field(arg: String = "wi\th de\fault"): String\n}'
        )

    def also_removes_indentation_using_tabs():
        assert (
            dedent(
                """
                \t\t    type Query {
                \t\t      me: User
                \t\t    }
                """
            )
            == "type Query {\n  me: User\n}"
        )

    def removes_leading_and_trailing_newlines():
        assert (
            dedent(
                """


                 type Query {
                   me: User
                 }


                 """
            )
            == "type Query {\n  me: User\n}"
        )

    def removes_all_trailing_spaces_and_tabs():
        assert (
            dedent(
                """
                type Query {
                  me: User
                }
                    \t\t  \t """
            )
            == "type Query {\n  me: User\n}"
        )

    def works_on_text_without_leading_newline():
        assert (
            dedent(
                """                type Query {
                  me: User
                }
                """
            )
            == "type Query {\n  me: User\n}"
        )
