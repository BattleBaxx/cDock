import logging
from threading import Thread
from typing import Dict, Optional

from docker import DockerClient
from docker.models.containers import Container

from cDock.config import Config
from cDock.docker_client.container_logs_streamer import ContainerLogsStreamer
from cDock.docker_client.container_stat_streamer import ContainerStatStreamer
from cDock.docker_client.models import ContainerView


class DockerDaemonClient:
    """
    This class is a wrapper around DockerClient and provider features to stream stats of containers and retrieve them
    in a simpler format.
    """

    STREAMING_STATUS = ['running', 'paused']

    def __init__(self, config: Config):
        self.__config = config
        self.__client: DockerClient = None
        self.__containers: Dict[str, Container] = {}
        self.__container_stats_streams: Dict[str, ContainerStatStreamer] = {}

        # For cleaning up executing container actions
        self.__container_action_map: Dict[str, Thread] = {}

    def __get_key(self, container: Container) -> str:
        return container.name

    def __action_executor(self, key: str, action, args, kwargs):
        try:
            action(*args, **kwargs)
        except Exception as e:
            logging.info(f"DockerDaemonClient - Exception during action for {key} : ({e})")
        finally:
            self.__container_action_map.pop(key)

    def __container_action(self, container_key: str, action_name: str, *args, **kwargs):
        if container_key not in self.__containers:
            raise Exception('Unknown container!')
        if not hasattr(self.__containers[container_key], action_name):
            raise Exception('Unknown action_executor!')

        key = f"{container_key}/{action_name}"
        if key in self.__container_action_map:
            raise Exception('Another action_executor in progress!')

        action = getattr(self.__containers[container_key], action_name)
        self.__container_action_map[key] = Thread(target=self.__action_executor, args=(key, action, args, kwargs))
        self.__container_action_map[key].daemon = True
        self.__container_action_map[key].start()

    def __upsert_container(self, container: Container) -> None:
        """
        Adds the container to the internal maps. If already present, old entry is replaced. If the container's status is
        in STREAMING_STATUS, a ContainerStatStreamer is created for the container, else any previously created
        ContainerStatStreamer is stopped and removed.

        :param container:
        """
        container_key = self.__get_key(container)
        if container_key not in self.__containers:
            logging.info(f"DockerDaemonClient - Adding container {container_key}")
        else:
            logging.debug(f"DockerDaemonClient - Updating container {container_key}")
        self.__containers[container_key] = container

        if container_key not in self.__container_stats_streams and container.status in self.STREAMING_STATUS:
            logging.debug(f"DockerDaemonClient - Starting streamer for {container_key}")
            self.__container_stats_streams[container_key] = ContainerStatStreamer(container)
            self.__container_stats_streams[container_key].start_stream()

        elif container_key in self.__container_stats_streams and container.status not in self.STREAMING_STATUS:
            logging.debug(f"DockerDaemonClient - Stopping streamer for {container_key}")
            self.__container_stats_streams.pop(container_key).stop_stream()

    def __remove_container(self, container_key: str) -> None:
        """
        Removes the corresponding container from the internal maps. If the container has a ContainerStatStreamer, it is
        stopped and removed.

        :param container_key: The container that needs to be removed
        """
        if container_key in self.__containers:
            logging.info(f"DockerDaemonClient - Removing container {container_key}")
            self.__containers[container_key] = container_key

        if container_key in self.__container_stats_streams:
            logging.debug(f"DockerDaemonClient - Stopping streamer for {container_key}")
            self.__container_stats_streams.pop(container_key).stop_stream()

    def __get_active_container_stats(self, container: Container) -> Dict:
        """
        Returns a dict with the active stats of the container with the information from the corresponding
        ContainerStatStreamer. Returns a empty dict if no ContainerStatStreamer exists for the container.

        :param container: The Container to get active stats for.
        :return: A dict with active stats if a ContainerStatStreamer exists for the container
        """
        stats = {}
        container_key = self.__get_key(container)

        try:
            stats['started_at'] = container.attrs['State']['StartedAt']
            stats['command'] = []
            if container.attrs['Config'].get('Entrypoint', None):
                stats['command'].extend(container.attrs['Config'].get('Entrypoint', []))
            if container.attrs['Config'].get('Cmd', None):
                stats['command'].extend(container.attrs['Config'].get('Cmd', []))

            stats['cpu_stats'] = self.__container_stats_streams[container_key].get_cpu_stats()
            stats['memory_stats'] = self.__container_stats_streams[container_key].get_memory_stats()
            stats['net_io_stats'] = self.__container_stats_streams[container_key].get_network_io()
            stats['disk_io_stats'] = self.__container_stats_streams[container_key].get_disk_io()
            stats['ports'] = container.attrs['Config'].get('ExposedPorts', [])
        except Exception as e:
            logging.error(f"DockerDaemonClient - Failed getting active stats for {container_key} ({e})")
            logging.error(container)

        return stats

    def __generate_container_view(self, container: Container) -> ContainerView:
        """
        Generates a ContainerView object for the given container. ContainerView includes active stats if the container
        status is in STREAMING_STATUS

        :param container: The Container to generate ContainerView for.
        :return: A ContainerView
        """
        view = {
            'name': container.name,
            'id': container.id,
            'status': container.attrs['State']['Status'],
            'image': str(container.image.tags),
            'created_at': container.attrs['Created'],
        }
        if view['status'] in self.STREAMING_STATUS:
            view |= self.__get_active_container_stats(container)

        return ContainerView(**view)

    def connect(self) -> bool:
        """
        Instantiates the DockerClient with the given config options. Starts the background event loop thread if its
        not running.

        :return: A bool indicating if the DockerClient connection succeeded or not
        :raises: Exception - If the client was already initialized successfully.
        """
        if self.__client:
            raise Exception("DockerDaemonClient - Already connection to a daemon")

        try:
            # TODO: lookup usage for certs
            self.__client = DockerClient(base_url=self.__config.docker_socket_url)
        except Exception as e:
            self.__client = None
            logging.error(f"DockerDaemonClient - Failed establish connection to docker daemon ({e})")
            return False

        return True

    def disconnect(self):
        self.__client.close()
        for key in self.__containers.keys():
            self.__remove_container(key)

    def get_version_and_container_views(self) -> Optional[Dict]:
        """
        Returns a dict with `version` and  `container_views` as keys (latter is not included if a error occurs)
        Raises an exception if the client is not initialized (`connect` methods performs the connection)

        :return: A dict containing version and a list of ContainerView
        :raises Exception - If DockerClient is not initialized
        """
        if not self.__client:
            raise Exception("Client not Initialized!")

        stats = {}
        try:
            stats['version'] = self.__client.version()
            containers = self.__client.containers.list(all=self.__config.client_list_all_containers) or []
        except Exception as e:  # We might have lost connection
            logging.error(f"DockerDaemonClient - Failed to get daemon version or containers list ({e})")
            return stats

        for container in containers:
            self.__upsert_container(container)

        missing_container_names = set(self.__container_stats_streams.keys()) - set([c.name for c in containers])
        for container_name in missing_container_names:
            self.__remove_container(container_name)

        # Generating ContainerView for all containers
        stats['container_views'] = [self.__generate_container_view(container) for container in containers]

        return stats

    def start(self, container_key: str):
        self.__container_action(container_key, 'start')

    def restart(self, container_key: str):
        self.__container_action(container_key, 'restart')

    def pause(self, container_key: str):
        self.__container_action(container_key, 'pause')

    def resume(self, container_key: str):
        self.__container_action(container_key, 'resume')

    def stop(self, container_key: str):
        self.__container_action(container_key, 'stop')

    def kill(self, container_key: str):
        self.__container_action(container_key, 'kill')

    def logs(self, container_key: str):
        if container_key not in self.__containers:
            raise Exception('Unknown container!')
        return ContainerLogsStreamer(self.__containers[container_key])
