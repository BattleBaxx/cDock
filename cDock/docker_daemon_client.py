import asyncio
import logging
from threading import Thread
from typing import Dict, Optional

from docker import DockerClient
from docker.models.containers import Container

from cDock.config import Config
from cDock.container_stat_streamer import ContainerStatStreamer
from cDock.models import ContainerView


class DockerDaemonClient:
    def __init__(self, config: Config):
        self.__config = config
        self.__client: DockerClient = None
        self.__container_stats_streams: Dict[str, ContainerStatStreamer] = {}

        # For streaming container stats in a background thread
        self.__streaming_event_loop = asyncio.new_event_loop()
        self.__streaming_event_loop_thread = Thread(target=self.__run_streaming_event_loop)
        self.__streaming_event_loop_thread.daemon = True

    def __run_streaming_event_loop(self):
        asyncio.set_event_loop(self.__streaming_event_loop)
        self.__streaming_event_loop.run_forever()

    def __start_streaming_event_loop_thread(self):
        if not self.__streaming_event_loop_thread.is_alive():
            self.__streaming_event_loop_thread.start()

    def __remove_container(self, container_name: str):
        if container_name in self.__container_stats_streams:
            logging.info(f"DockerDaemonClient - Stopping streamer for {container_name}")
            self.__container_stats_streams.pop(container_name).stop_stream()

    def connect(self):
        if self.__client:
            raise Exception("DockerDaemonClient - Already connection to a daemon")
        try:
            # TODO: lookup usage for certs
            self.__client = DockerClient(base_url=self.__config.docker_socket_url)
        except Exception as e:
            self.__client = None
            logging.error(f"DockerDaemonClient - Failed establish connection to docker daemon ({e})")
        else:
            self.__start_streaming_event_loop_thread()

    def update(self) -> Optional[Dict]:
        if not self.__client:
            raise Exception("Client not Initialized!")

        stats = {}

        try:
            stats['version'] = self.__client.version()
        except Exception as e:
            logging.error(f"DockerDaemonClient - Failed to get daemon version ({e})")
            # We might have lost connection
            return None

        try:
            containers = self.__client.containers.list(all=self.__config.client_list_all_containers) or []
        except Exception as e:
            logging.error(f"DockerDaemonClient - Failed to get containers list ({e})")
            # We might have lost connection
            return None

        for container in containers:
            if container.name not in self.__container_stats_streams:
                logging.info(f"DockerDaemonClient - Starting streamer for {container.name}")
                streamer = ContainerStatStreamer(container, self.__streaming_event_loop)
                self.__container_stats_streams[container.name] = streamer

        absent_container_name = set(self.__container_stats_streams.keys()) - set([c.name for c in containers])
        for container_name in absent_container_name:
            self.__remove_container(container_name)

        # Generating ContainerView for all containers
        stats['containers'] = []
        for container in containers:
            view = {
                'name': container.name,
                'id': container.id,
                'status': container.attrs['State']['Status'],
                'image': str(container.image.tags),
                'created_at': container.attrs['Created'],
                'command': []
            }
            if view['status'] in ['running', 'paused']:
                view |= self.__get_active_container_stats(container)
            stats['containers'].append(ContainerView(**view))

        return stats

    def __get_active_container_stats(self, container: Container):
        stats = {'command': []}
        try:
            stats['started_at'] = container.attrs['State']['StartedAt']
            stats['cpu_stats'] = self.__container_stats_streams[container.name].get_cpu_stats()
            stats['memory_stats'] = self.__container_stats_streams[container.name].get_memory_stats()
            stats['net_io_stats'] = self.__container_stats_streams[container.name].get_network_io()
            stats['disk_io_stats'] = self.__container_stats_streams[container.name].get_disk_io()
            stats['ports'] = container.attrs['Config'].get('ExposedPorts', [])
            if container.attrs['Config'].get('Entrypoint', None):
                stats['command'].extend(container.attrs['Config'].get('Entrypoint', []))
            if container.attrs['Config'].get('Cmd', None):
                stats['command'].extend(container.attrs['Config'].get('Cmd', []))
        except Exception as e:
            logging.error(f"DockerDaemonClient - Failed getting active stats for {container.name} ({e})")
            logging.error(container)
        return stats

    def start(self, container_name: str):
        if container_name not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_name].get_container().start()

    def restart(self, container_name: str):
        if container_name not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_name].get_container().restart()

    def stop(self, container_name: str):
        if container_name not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_name].get_container().stop()

    def kill(self, container_name: str):
        if container_name not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_name].get_container().kill()
