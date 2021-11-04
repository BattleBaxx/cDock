from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MemoryStats(BaseModel):
    usage: Optional[int]
    limit: Optional[int]
    cache: Optional[int]
    max_usage: Optional[int]


class NetIOStats(BaseModel):
    read_time: Optional[datetime]
    total_rx: Optional[int]
    total_tx: Optional[int]
    rx: Optional[int]
    tx: Optional[int]


class DiskIOStats(BaseModel):
    read_time: Optional[datetime]
    total_ior: Optional[int]
    total_iow: Optional[int]
    ior: Optional[int]
    iow: Optional[int]


class ContainerView(BaseModel):
    status: str  # Enum?
    name: str
    id: str
    cpu_percent: str
    memory_stats: MemoryStats
    net_io_stats: NetIOStats
    disk_io_stats: DiskIOStats
    image: str
    created_at: datetime
    started_at: Optional[datetime]
    published_ports: List[str] = []
    command: Optional[str]
