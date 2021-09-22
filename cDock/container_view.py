from typing import List
from pydantic import BaseModel


class ContainerView(BaseModel):
    status: str  # Enum?
    name: str
    id: str
    memory_usage: str
    io_transfer: str
    cpu_load: str
    image: str
    created_at: int
    started_at: int
    published_ports: List[str]
    command: str
