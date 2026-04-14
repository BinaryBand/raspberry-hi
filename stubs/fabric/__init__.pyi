from typing import Any, Optional

class Result:
    ok: bool
    stdout: str
    stderr: str
    return_code: int

class Connection:
    def __init__(
        self,
        host: str,
        user: Optional[str] = ...,
        connect_kwargs: Optional[dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...
    def run(
        self,
        command: str,
        *,
        hide: bool = ...,
        warn: bool = ...,
        **kwargs: Any,
    ) -> Result: ...
