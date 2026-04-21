from typing import Sequence

from ansible.parsing.dataloader import DataLoader

class Host:
    name: str

class InventoryManager:
    def __init__(self, loader: DataLoader, sources: Sequence[str]) -> None: ...
    def get_hosts(self) -> list[Host]: ...
