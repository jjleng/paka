from collections import namedtuple

ARCHIVE_TYPE_URL = "url"
ARCHIVE_TYPE_LITERAL = "literal"

Archive = namedtuple("Archive", ["type", "literal", "url", "checksum"])
