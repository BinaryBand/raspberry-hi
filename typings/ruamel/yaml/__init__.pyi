from os import PathLike
from typing import IO, Any

class YAML:
    preserve_quotes: bool
    width: int

    def __init__(
        self,
        *,
        typ: str | list[str] | None = None,
        pure: bool = False,
        output: Any = None,
        plug_ins: Any = None,
    ) -> None: ...
    def load(
        self, stream: str | bytes | PathLike[str] | PathLike[bytes] | IO[str] | IO[bytes]
    ) -> Any: ...
    def dump(
        self,
        data: Any,
        stream: str | PathLike[str] | IO[str] | None = None,
        *,
        transform: Any = None,
    ) -> Any: ...
