import logging
from typing import Dict, Optional

from docker import DockerClient

from cDock.config import Config
from cDock.container_stat_streamer import ContainerStatStreamer


class DockerDaemonClient:
    def __init__(self, config: Config):
        self.__config = config
        self.__client: DockerClient = None
        self.__containers: Dict[str, ContainerStatStreamer] = {}

    def connect(self):
        try:
            # TODO: lookup usage for certs
            self.__client = DockerClient(base_url=self.__config.docker_socket_url)
        except Exception as e:
            logging.error(f"DockerDaemonClient - Failed establish connection to docker daemon ({e})")

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
            if container.id not in self.__containers:

                self.__containers[container.id] = ContainerStatStreamer(container)

        absent_container_ids = set(self.__containers.keys()) - set([c.id for c in containers])
        for container_id in absent_container_ids:
            if container_id in self.__containers:
                self.__containers.pop(container_id).stop_stream()

        return stats

    def start(self, container_id: str):
        if container_id not in self.__containers:
            raise Exception('unknown container')
        self.__containers[container_id].get_container().start()

    def restart(self, container_id: str):
        if container_id not in self.__containers:
            raise Exception('unknown container')
        self.__containers[container_id].get_container().restart()

    def stop(self, container_id: str):
        if container_id not in self.__containers:
            raise Exception('unknown container')
        self.__containers[container_id].get_container().stop()

    def kill(self, container_id: str):
        if container_id not in self.__containers:
            raise Exception('unknown container')
        self.__containers[container_id].get_container().kill()
