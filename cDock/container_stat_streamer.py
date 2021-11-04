import asyncio
import logging
from datetime import datetime
from threading import Thread
from typing import Dict

from docker.models.containers import Container

from cDock.models import DiskIOStats, NetIOStats, MemoryStats

SHA_256_HASH_PICK = 12


def read_iso_timestamp(timestamp_str: str) -> datetime:
    """
    A utility method to convert Docker APIs timestamp into datetime objects
    :param timestamp_str: ISO 8061 string timestamp
    :return: corresponding datetime instance
    """
    # index = timestamp_str.rfind('Z')
    # if index != -1:
    #     timestamp_str = timestamp_str[:index]
    #
    # index = timestamp_str.rfind('.')
    # if index != -1:
    #     timestamp_str = timestamp_str[:index + 4]

    # Hard coding to 19 chars for lesser computation
    timestamp_str = timestamp_str[:19]

    return datetime.fromisoformat(timestamp_str)


class ContainerStatStreamer:

    def __init__(self, container: Container):
        self.__stats: Dict = {}
        self.__container: Container = container
        self.__time_initialized = datetime.now()
        self.__stats_generator = self.__container.stats(decode=True)

        # To calculate with details from Docker API
        self.__old_net_io = None
        self.__old_disk_io = None

        self.__stream_task = asyncio.ensure_future(self.__stream_stats())

    def stop_stream(self):
        self.__stream_task.cancel()

    def get_container(self) -> Container:
        return self.__container

    def update_container(self, container: Container) -> None:
        self.__container = container

    def __initialize_stats_streamer(self):
        """
        Initialize the stats generator on a thread to evade sync block from the docker's stream_helper
        """
        thread = Thread(target=lambda: next(self.__stats_generator))
        thread.start()
        thread.join()

    async def __stream_stats(self):
        if self.__stats:
            # Return if stats is already initialized (that is, another async task is already running)
            return

        self.__initialize_stats_streamer()

        try:
            for stats in self.__stats_generator:
                self.__stats = stats
                self.__container.reload()
                try:
                    print(self.__container.name)
                except Exception as e:
                    print(self.__container.name, "EXP:", type(e), e)
                finally:
                    await asyncio.sleep(0.9)
        except Exception as e:
            print("excep", e)

    def get_cpu_usage(self) -> float:
        """
        Returns a container's CPU usage
        :return: a float value indicating the CPU usage of the container
        """
        usage = 0.0
        cpu = {}
        precpu = {}
        stats = self.__stats.copy()  # Using a copy to avoid values overwritten while reading

        try:
            cpu['system'] = stats['cpu_stats']['system_cpu_usage']
            cpu['total'] = stats['cpu_stats']['cpu_usage']['total_usage']
            precpu['system'] = stats['precpu_stats']['system_cpu_usage']
            precpu['total'] = stats['precpu_stats']['cpu_usage']['total_usage']

            cpu['count'] = stats['cpu_stats'].get('online_cpus')
            if cpu['count'] is None:
                cpu['count'] = len(stats['cpu_stats']['cpu_usage']['percpu_usage'] or [])
        except KeyError as e:
            logging.debug(f"StatsStreamer - Failed to get CPU usage for `{self.__container.id}` ({e})")
            logging.debug(stats)
        else:
            # CPU usage % = cpu_delta / system_cpu_delta * number_of_cpus * 100
            cpu_delta = cpu['total'] - precpu['total']
            system_cpu_delta = cpu['system'] - precpu['system']
            usage = cpu_delta / system_cpu_delta * cpu['count'] * 100

        return usage

    def get_memory_usage(self) -> MemoryStats:
        """
        Returns a container's memory details
        :return: a dict with the respective details
        """
        details = {}

        try:
            memory_stats = self.__stats['memory_stats']

            # Fixed details
            details['usage'] = memory_stats['usage']
            details['limit'] = memory_stats['limit']

            # Optional details
            if 'stats' in memory_stats:
                details['cache'] = memory_stats['stats'].get('cache')
                details['max_usage'] = memory_stats['stats'].get('max_usage')

        except KeyError as e:
            logging.debug(f"StatsStreamer - Failed to get Memory stats for `{self.__container.id}` ({e})")
            logging.debug(self.__stats)

        return MemoryStats(**details)

    def get_network_io(self) -> NetIOStats:
        """
        Returns a container's network transfer details
        :return: a dict with the respective details
        """
        net_io = {}
        stats = self.__stats.copy()  # Using a copy to avoid values overwritten while reading

        try:
            net_io['read_time'] = read_iso_timestamp(stats['read'])
            net_io['total_rx'] = stats['networks']['eth0']['rx_bytes']
            net_io['total_tx'] = stats['networks']['eth0']['tx_bytes']
        except KeyError as e:
            logging.debug(f"StatsStreamer - Failed to get Network IO for `{self.__container.id}` ({e})")
            logging.debug(stats)
        else:
            if self.__old_net_io is not None:
                net_io['rx'] = net_io['total_rx'] - self.__old_net_io['total_rx']
                net_io['tx'] = net_io['total_tx'] - self.__old_net_io['total_tx']
                net_io['duration'] = net_io['read_time'] - self.__old_net_io['read_time']

            # Storing net_io details for Rx/s, Tx/s and duration calculation in subsequent call
            self.__old_net_io = net_io

        # Return the details
        return NetIOStats(**net_io)

    def get_disk_io(self) -> DiskIOStats:
        """
        Returns a container's disk IO transfer details
        :return: a dict with the respective details
        """
        disk_io = {}
        stats = self.__stats.copy()  # Using a copy to avoid values overwritten while reading

        try:
            io_service_bytes_recursive = stats["blkio_stats"]['io_service_bytes_recursive']
            disk_io['read_time'] = read_iso_timestamp(stats['read'])
            disk_io['total_ior'] = [i for i in io_service_bytes_recursive if i['op'].upper() == 'READ'][0]['value']
            disk_io['total_iow'] = [i for i in io_service_bytes_recursive if i['op'].upper() == 'WRITE'][0]['value']
        except KeyError as e:
            logging.debug(f"StatsStreamer - Failed to get Disk IO for `{self.__container.id}` ({e})")
            logging.debug(stats)
        else:
            if self.__old_disk_io is not None:
                disk_io['ior'] = disk_io['total_ior'] - self.__old_disk_io['total_ior']
                disk_io['iow'] = disk_io['total_iow'] - self.__old_disk_io['total_iow']
                disk_io['duration'] = disk_io['read_time'] - self.__old_disk_io['read_time']

            # Storing disk_io details for ior, iow and duration in subsequent call
            self.__old_disk_io = disk_io

        return DiskIOStats(**disk_io)
