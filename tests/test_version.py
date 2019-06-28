import re

import graphql
from graphql import version, version_info, version_js, version_info_js

_re_version = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:(a|b|c)(\d+))?$")


def describe_version():
    def test_module_version():
        assert graphql.__version__ == version
        assert graphql.version == version

    def test_module_version_info():
        assert graphql.__version_info__ == version_info
        assert graphql.version_info == version_info

    def test_module_version_js():
        assert graphql.__version_js__ == version_js
        assert graphql.version_js == version_js

    def test_module_version_info_js():
        assert graphql.__version_info_js__ == version_info_js
        assert graphql.version_info_js == version_info_js

    def test_version():
        assert isinstance(version, str)
        assert _re_version.match(version)

    def test_version_info():
        assert isinstance(version_info, tuple)
        assert str(version_info) == version
        groups = _re_version.match(version).groups()
        assert version_info.major == int(groups[0])
        assert version_info.minor == int(groups[1])
        assert version_info.micro == int(groups[2])
        if groups[3] is None:
            assert groups[4] is None
        else:
            assert version_info.releaselevel[:1] == groups[3]
            assert version_info.serial == int(groups[4])

    def test_version_js():
        assert isinstance(version_js, str)
        assert _re_version.match(version_js)

    def test_version_info_js():
        assert isinstance(version_info_js, tuple)
        assert str(version_info_js) == version_js
        groups = _re_version.match(version_js).groups()
        assert version_info_js.major == int(groups[0])
        assert version_info_js.minor == int(groups[1])
        assert version_info_js.micro == int(groups[2])
        if groups[3] is None:
            assert groups[4] is None
        else:
            assert version_info_js.releaselevel[:1] == groups[3]
            assert version_info_js.serial == int(groups[4])
