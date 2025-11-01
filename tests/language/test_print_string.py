from graphql.language.print_string import print_string


def describe_print_string():
    def prints_a_simple_string():
        assert print_string("hello world") == '"hello world"'

    def escapes_quotes():
        assert print_string('"hello world"') == '"\\"hello world\\""'

    def escapes_backslashes():
        assert print_string("escape: \\") == '"escape: \\\\"'

    def escapes_well_known_control_chars():
        assert print_string("\b\f\n\r\t") == '"\\b\\f\\n\\r\\t"'

    def escapes_zero_byte():
        assert print_string("\x00") == '"\\u0000"'

    def does_not_escape_space():
        assert print_string(" ") == '" "'

    def does_not_escape_non_ascii_character():
        assert print_string("\u21bb") == '"\u21bb"'

    def does_not_escape_supplementary_character():
        assert print_string("\U0001f600") == '"\U0001f600"'

    def escapes_all_control_chars():
        assert print_string(
            "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
            "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
            "\x20\x21\x22\x23\x24\x25\x26\x27\x28\x29\x2a\x2b\x2c\x2d\x2e\x2f"
            "\x30\x31\x32\x33\x34\x35\x36\x37\x38\x39\x3a\x3b\x3c\x3d\x3e\x3f"
            "\x40\x41\x42\x43\x44\x45\x46\x47\x48\x49\x4a\x4b\x4c\x4d\x4e\x4f"
            "\x50\x51\x52\x53\x54\x55\x56\x57\x58\x59\x5a\x5b\x5c\x5d\x5e\x5f"
            "\x60\x61\x62\x63\x64\x65\x66\x67\x68\x69\x6a\x6b\x6c\x6d\x6e\x6f"
            "\x70\x71\x72\x73\x74\x75\x76\x77\x78\x79\x7a\x7b\x7c\x7d\x7e\x7f"
            "\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f"
            "\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f"
        ) == (
            '"\\u0000\\u0001\\u0002\\u0003\\u0004\\u0005\\u0006\\u0007'
            "\\b\\t\\n\\u000B\\f\\r\\u000E\\u000F"
            "\\u0010\\u0011\\u0012\\u0013\\u0014\\u0015\\u0016\\u0017"
            "\\u0018\\u0019\\u001A\\u001B\\u001C\\u001D\\u001E\\u001F"
            " !\\\"#$%&'()*+,-./0123456789:;<=>?"
            "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\\\]^_"
            "`abcdefghijklmnopqrstuvwxyz{|}~\\u007F"
            "\\u0080\\u0081\\u0082\\u0083\\u0084\\u0085\\u0086\\u0087"
            "\\u0088\\u0089\\u008A\\u008B\\u008C\\u008D\\u008E\\u008F"
            "\\u0090\\u0091\\u0092\\u0093\\u0094\\u0095\\u0096\\u0097"
            '\\u0098\\u0099\\u009A\\u009B\\u009C\\u009D\\u009E\\u009F"'
        )
