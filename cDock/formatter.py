from typing import Union

from rich.text import Text

from cDock.config import Config
from cDock.models import *

header_map = {
    "name": "Name",
    "id": "Id",
    "status": "Status",
    "image": "Tag",
    "cpu": "CPU%",
    "mem_usage": "MEM",
    "mem_limit": "MAX",
    "rx/s": "Rx/s",
    "tx/s": "Tx/s",
    "ior/s": "IOR/s",
    "iow/s": "IOW/s",
    "created": "Created",
    "started": "Started",
    "ports": "Ports",
    "command": "Command",
}

SHA_512_ID_PICK_SIZE = 12


class RichFormatter:
    def __init__(self, config: Config):
        self.config = config

    def get_header_row(self):
        return [header_map[k] for k in self.config.priority_attributes.split(",") if k in header_map]

    def get_container_row(self, view: ContainerView):
        values = {
            "name": view.name,
            "id": view.id[:SHA_512_ID_PICK_SIZE],
            "status": view.status,
            "image": view.image,
            "cpu": format(view.cpu_stats.usage, ".2f") if view.cpu_stats else '-',
            "mem_usage": self._auto_unit(view.memory_stats.usage) if view.memory_stats else '-',
            "mem_limit": self._auto_unit(view.memory_stats.limit) if view.memory_stats else '-',
            "rx/s": self._auto_unit(view.net_io_stats.rx) if view.net_io_stats else '-',
            "tx/s": self._auto_unit(view.net_io_stats.tx) if view.net_io_stats else '-',
            "ior/s": self._auto_unit(view.disk_io_stats.ior) if view.disk_io_stats else '-',
            "iow/s": self._auto_unit(view.disk_io_stats.iow) if view.disk_io_stats else '-',
            "created": "Created",
            "started": "Started",
            "ports": ", ".join(view.published_ports),
            "command": view.command[0] if len(view.command) > 0 else '',
        }
        return [Text(values[attr], overflow="ellipsis") for attr in self.config.priority_attributes.split(',')]

    def _format_cpu_usage(self, stats: CPUStats) -> str:
        return format(stats.usage, ".2f") if stats else '_'

    @staticmethod
    def _auto_unit(number: Union[int, float]) -> str:
        if number is None:
            return '-'
        units = [
            (1208925819614629174706176, 'Y'),
            (1180591620717411303424, 'Z'),
            (1152921504606846976, 'E'),
            (1125899906842624, 'P'),
            (1099511627776, 'T'),
            (1073741824, 'G'),
            (1048576, 'M'),
            (1024, 'K'),
        ]

        for unit, suffix in units:
            value = float(number) / unit
            if value > 1:
                precision = 0
                if value < 10:
                    precision = 2
                elif value < 100:
                    precision = 1
                if suffix == 'K':
                    precision = 0
                return '{:.{decimal}f}{suffix}'.format(value, decimal=precision, suffix=suffix)

        return '{!s}'.format(number)

    def _get_container_status_style(self, status):
        status_styles = {
            "created": self.config.container_created_style,
            "restarting": self.config.container_created_style,
            "running": self.config.container_created_style,
            "paused": self.config.container_created_style,
            "exited": self.config.container_created_style,
            "dead": self.config.container_created_style,
        }
        return status_styles.get(status, '')
