import logging
from datetime import datetime
from typing import Dict, Optional

from docker.models.containers import Container

from cDock.docker_client.container_info_streamer import ContainerInfoStreamer
from cDock.docker_client.models import DiskIOStats, NetIOStats, MemoryStats, CPUStats

SHA_256_HASH_PICK = 12


def read_iso_timestamp(timestamp_str: str) -> datetime:
    """
    A utility method to convert Docker API's timestamp into datetime objects.
    Removes characters after `.` or `Z` in the timestamp as datetime doesnt accept it
    :param timestamp_str: ISO 8061 string timestamp
    :return: corresponding datetime instance
    """
    # Hard coding to 19 chars as that filters out excess text
    timestamp_str = timestamp_str[:19]
    return datetime.fromisoformat(timestamp_str)


class ContainerStatStreamer(ContainerInfoStreamer):

    def __init__(self, container: Container):
        super().__init__(container)
        self.stats: Dict = {}

        # To calculate with details from Docker API
        self.old_net_io = None
        self.old_disk_io = None

    def get_stream_generator(self):
        return self.container.stats(decode=True)

    def stream_handler(self, streamed_value):
        self.stats = streamed_value

    def get_cpu_stats(self) -> CPUStats:
        """
        Returns a container's CPU usage and core count
        :return: a float value indicating the CPU usage along with core count
        """
        cpu_stats = {}
        stats = self.stats  # Using a copy to avoid values overwritten while reading

        try:
            cpu = {
                'system': stats['cpu_stats']['system_cpu_usage'],
                'total': stats['cpu_stats']['cpu_usage']['total_usage']
            }
            precpu = {
                'system': stats['precpu_stats']['system_cpu_usage'],
                'total': stats['precpu_stats']['cpu_usage']['total_usage']
            }

            cpu['count'] = stats['cpu_stats'].get('online_cpus')
            if cpu['count'] is None:
                cpu['count'] = len(stats['cpu_stats']['cpu_usage']['percpu_usage'] or [])
        except KeyError as e:
            logging.debug(f"StatsStreamer - Failed to get CPU usage for `{self.container.id}` ({e})")
            logging.debug(stats)
        else:
            # CPU usage % = cpu_delta / system_cpu_delta * number_of_cpus * 100
            cpu_delta = cpu['total'] - precpu['total']
            system_cpu_delta = cpu['system'] - precpu['system']
            usage = cpu_delta / system_cpu_delta * cpu['count'] * 100

            cpu_stats = {'usage': usage, 'cores': cpu['count']}

        return CPUStats(**cpu_stats) if cpu_stats else None

    def get_memory_stats(self) -> Optional[MemoryStats]:
        """
        Returns a container's memory details
        :return: a MemoryStats object
        """
        memory_stats = {}

        try:
            container_mem_stats = self.stats['memory_stats']

            # Fixed details
            memory_stats['usage'] = container_mem_stats['usage']
            memory_stats['limit'] = container_mem_stats['limit']

            # Optional details
            if 'stats' in memory_stats:
                memory_stats['cache'] = container_mem_stats['stats'].get('cache')
                memory_stats['max_usage'] = container_mem_stats['stats'].get('max_usage')

        except KeyError as e:
            logging.debug(f"StatsStreamer - Failed to get Memory stats for `{self.container.id}` ({e})")
            logging.debug(self.stats)

        return MemoryStats(**memory_stats) if memory_stats else None

    def get_network_io(self) -> Optional[NetIOStats]:
        """
        Returns a container's network transfer details
        :return: a NetIOStats object
        """
        net_io = {}
        stats = self.stats  # Using a copy to avoid values overwritten while reading

        try:
            net_io['total_rx'] = stats['networks']['eth0']['rx_bytes']
            net_io['total_tx'] = stats['networks']['eth0']['tx_bytes']
            net_io['read_time'] = read_iso_timestamp(stats['read'])
        except KeyError as e:
            logging.debug(f"StatsStreamer - Failed to get Network IO for `{self.container.id}` ({e})")
            logging.debug(stats)
        else:
            if self.old_net_io is not None:
                net_io['rx'] = net_io['total_rx'] - self.old_net_io['total_rx']
                net_io['tx'] = net_io['total_tx'] - self.old_net_io['total_tx']
                net_io['duration'] = net_io['read_time'] - self.old_net_io['read_time']

            # Storing net_io details for Rx/s, Tx/s and duration calculation in subsequent call
            self.old_net_io = net_io

        # Return the details
        return NetIOStats(**net_io) if net_io else None

    def get_disk_io(self) -> Optional[DiskIOStats]:
        """
        Returns a container's disk IO transfer details
        :return: a DiskIOStats object
        """
        disk_io = {}
        stats = self.stats  # Using a copy to avoid values overwritten while reading

        try:
            io_service_bytes_recursive = stats["blkio_stats"]['io_service_bytes_recursive']
            disk_io['total_ior'] = [i for i in io_service_bytes_recursive if i['op'].upper() == 'READ'][0]['value']
            disk_io['total_iow'] = [i for i in io_service_bytes_recursive if i['op'].upper() == 'WRITE'][0]['value']
            disk_io['read_time'] = read_iso_timestamp(stats['read'])
        except (KeyError, TypeError) as e:
            logging.debug(f"StatsStreamer - Failed to get Disk IO for `{self.container.id}` ({e})")
            logging.debug(stats)
        else:
            if self.old_disk_io is not None:
                disk_io['ior'] = disk_io['total_ior'] - self.old_disk_io['total_ior']
                disk_io['iow'] = disk_io['total_iow'] - self.old_disk_io['total_iow']
                disk_io['duration'] = disk_io['read_time'] - self.old_disk_io['read_time']

            # Storing disk_io details for ior, iow and duration in subsequent call
            self.old_disk_io = disk_io

        return DiskIOStats(**disk_io) if disk_io else None
