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
        assert print_string("\u21BB") == '"\u21BB"'

    def does_not_escape_supplementary_character():
        assert print_string("\U0001f600") == '"\U0001f600"'

    def escapes_all_control_chars():
        assert print_string(
            "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F"
            "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1A\x1B\x1C\x1D\x1E\x1F"
            "\x20\x21\x22\x23\x24\x25\x26\x27\x28\x29\x2A\x2B\x2C\x2D\x2E\x2F"
            "\x30\x31\x32\x33\x34\x35\x36\x37\x38\x39\x3A\x3B\x3C\x3D\x3E\x3F"
            "\x40\x41\x42\x43\x44\x45\x46\x47\x48\x49\x4A\x4B\x4C\x4D\x4E\x4F"
            "\x50\x51\x52\x53\x54\x55\x56\x57\x58\x59\x5A\x5B\x5C\x5D\x5E\x5F"
            "\x60\x61\x62\x63\x64\x65\x66\x67\x68\x69\x6A\x6B\x6C\x6D\x6E\x6F"
            "\x70\x71\x72\x73\x74\x75\x76\x77\x78\x79\x7A\x7B\x7C\x7D\x7E\x7F"
            "\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8A\x8B\x8C\x8D\x8E\x8F"
            "\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9A\x9B\x9C\x9D\x9E\x9F"
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
