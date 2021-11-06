from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel


class CPUStats(BaseModel):
    usage: float
    cores: int


class MemoryStats(BaseModel):
    usage: int
    limit: int
    cache: Optional[int]
    max_usage: Optional[int]


class NetIOStats(BaseModel):
    total_rx: int
    total_tx: int
    read_time: datetime
    rx: Optional[int]
    tx: Optional[int]
    duration: Optional[timedelta]


class DiskIOStats(BaseModel):
    total_ior: int
    total_iow: int
    read_time: datetime
    ior: Optional[int]
    iow: Optional[int]
    duration: Optional[timedelta]


class ContainerView(BaseModel):
    status: str  # Enum?
    name: str
    id: str
    image: str
    cpu_stats: Optional[CPUStats]
    memory_stats: Optional[MemoryStats]
    net_io_stats: Optional[NetIOStats]
    disk_io_stats: Optional[DiskIOStats]
    created_at: datetime
    started_at: Optional[datetime]
    published_ports: List[str] = []
    command: List[str] = []
