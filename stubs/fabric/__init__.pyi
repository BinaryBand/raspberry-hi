from typing import Any, Optional, Union

class Result:
    ok: bool
    stdout: str
    stderr: str
    return_code: int

    def __init__(
        self,
        command: str,
        stdout: str = "",
        stderr: str = "",
        exited: int = 0,
    ) -> None: ...

class Connection:
    host: str
    user: Optional[str]
    port: Optional[int]
    connect_kwargs: dict[str, Any]

    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        connect_kwargs: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None: ...
    def run(
        self,
        command: str,
        *,
        hide: Union[bool, str] = False,
        warn: bool = False,
        echo: bool = False,
        in_stream: Optional[Any] = None,
        **kwargs: Any,
    ) -> Result: ...
    def sudo(
        self,
        command: str,
        *,
        user: Optional[str] = None,
        hide: Union[bool, str] = False,
        warn: bool = False,
        **kwargs: Any,
    ) -> Result: ...
    def close(self) -> None: ...
