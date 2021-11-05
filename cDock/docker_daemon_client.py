import logging
from typing import Dict, Optional

from docker import DockerClient

from cDock.config import Config
from cDock.container_stat_streamer import ContainerStatStreamer
from cDock.models import ContainerView


class DockerDaemonClient:
    def __init__(self, config: Config):
        self.__config = config
        self.__client: DockerClient = None
        self.__container_stats_streams: Dict[str, ContainerStatStreamer] = {}

    def connect(self):
        try:
            # TODO: lookup usage for certs
            self.__client = DockerClient(base_url=self.__config.docker_socket_url)
        except Exception as e:
            logging.error(f"DockerDaemonClient - Failed establish connection to docker daemon ({e})")

    def __remove_container(self, container_id: str):
        if container_id in self.__container_stats_streams:
            self.__container_stats_streams.pop(container_id).stop_stream()

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
            if container.id not in self.__container_stats_streams:
                self.__container_stats_streams[container.id] = ContainerStatStreamer(container)

        absent_container_ids = set(self.__container_stats_streams.keys()) - set([c.id for c in containers])
        for container_id in absent_container_ids:
            self.__remove_container(container_id)

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
                view['started_at'] = container.attrs['State']['StartedAt']
                view['cpu_stats'] = self.__container_stats_streams[container.id].get_cpu_stats()
                view['memory_stats'] = self.__container_stats_streams[container.id].get_memory_stats()
                view['net_io_stats'] = self.__container_stats_streams[container.id].get_network_io()
                view['disk_io_stats'] = self.__container_stats_streams[container.id].get_disk_io()
                view['ports'] = container.attrs['Config'].get('ExposedPorts', [])
                if container.attrs['Config'].get('Entrypoint', None):
                    view['command'].extend(container.attrs['Config'].get('Entrypoint', []))
                if container.attrs['Config'].get('Cmd', None):
                    view['command'].extend(container.attrs['Config'].get('Cmd', []))

            stats['containers'].append(ContainerView(**view))

        return stats

    def start(self, container_id: str):
        if container_id not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_id].get_container().start()

    def restart(self, container_id: str):
        if container_id not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_id].get_container().restart()

    def stop(self, container_id: str):
        if container_id not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_id].get_container().stop()

    def kill(self, container_id: str):
        if container_id not in self.__container_stats_streams:
            raise Exception('unknown container')
        self.__container_stats_streams[container_id].get_container().kill()
