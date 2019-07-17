import re
from typing import NamedTuple
from warnings import warn

__all__ = ["version", "version_info", "version_js", "version_info_js"]


version = "1.1.1"

version_js = "14.4.0"


warn(
    "GraphQL-core-next has been discontinued."
    " It is now released as GraphQL-core v3 and newer.",
    DeprecationWarning,
)


_re_version = re.compile(r"(\d+)\.(\d+)\.(\d+)(\D*)(\d*)")


class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int

    @classmethod
    def from_str(cls, v: str) -> "VersionInfo":
        groups = _re_version.match(v).groups()  # type: ignore
        major, minor, micro = map(int, groups[:3])
        level = (groups[3] or "")[:1]
        if level == "a":
            level = "alpha"
        elif level == "b":
            level = "beta"
        elif level in ("c", "r"):
            level = "candidate"
        else:
            level = "final"
        serial = groups[4]
        serial = int(serial) if serial else 0
        return cls(major, minor, micro, level, serial)

    def __str__(self):
        v = f"{self.major}.{self.minor}.{self.micro}"
        level = self.releaselevel
        if level and level != "final":
            v = f"{v}{level[:1]}{self.serial}"
        return v


version_info = VersionInfo.from_str(version)

version_info_js = VersionInfo.from_str(version_js)
