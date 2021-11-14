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

        # For streaming container stats in a background thread
        self.__streaming_event_loop = asyncio.new_event_loop()
        self.__streaming_event_loop_thread = Thread(target=self.__run_streaming_event_loop)
        self.__streaming_event_loop_thread.daemon = True

        # For cleaning up executing container actions
        self.__container_action_map: Dict[str, Thread] = {}
        asyncio.run_coroutine_threadsafe(self.__clean_container_action_threads(), self.__streaming_event_loop)

    def __run_streaming_event_loop(self) -> None:
        """
        A utility method used to run the event loop for stats streaming in a background thread.
        """
        asyncio.set_event_loop(self.__streaming_event_loop)
        self.__streaming_event_loop.run_forever()

    def __start_streaming_event_loop_thread(self) -> None:
        """
        Starts the background event loop thread if its not started yet. Returns if its already started
        """
        if not self.__streaming_event_loop_thread.is_alive():
            self.__streaming_event_loop_thread.start()

    async def __clean_container_action_threads(self):
        """
        Async task that cleans up container action_executor threads when they get completed
        """
        while True:
            for key, thread in self.__container_action_map.items():
                if not thread.is_alive():
                    self.__container_action_map.pop(key)
            await asyncio.sleep(0.3)

    def __container_action(self, container_name: str, action: str, *args, **kwargs):
        if container_name not in self.__containers:
            raise Exception('Unknown container!')
        if not hasattr(self.__containers[container_name], action):
            raise Exception('Unknown action_executor!')

        key = f"{container_name}/{action}"
        if key in self.__container_action_map:
            raise Exception('Another action_executor in progress!')

        action_executor = getattr(self.__containers[container_name], action)
        thread = Thread(target=action_executor, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        self.__container_action_map[key] = thread

    def __upsert_container(self, container: Container) -> None:
        """
        Adds the container to the internal maps. If already present, old entry is replaced. If the container's status is
        in STREAMING_STATUS, a ContainerStatStreamer is created for the container, else any previously created
        ContainerStatStreamer is stopped and removed.

        :param container:
        """
        if container.name not in self.__containers:
            logging.info(f"DockerDaemonClient - Adding container {container.name}")
        else:
            logging.debug(f"DockerDaemonClient - Updating container {container.name}")
        self.__containers[container.name] = container

        if container.name not in self.__container_stats_streams and container.status in self.STREAMING_STATUS:
            logging.debug(f"DockerDaemonClient - Starting streamer for {container.name}")
            streamer = ContainerStatStreamer(container, self.__streaming_event_loop)
            self.__container_stats_streams[container.name] = streamer

        elif container.name in self.__container_stats_streams and container.status not in self.STREAMING_STATUS:
            logging.debug(f"DockerDaemonClient - Stopping streamer for {container.name}")
            self.__container_stats_streams.pop(container.name).stop_stream()

    def __remove_container(self, container_name: str) -> None:
        """
        Removes the corresponding container from the internal maps. If the container has a ContainerStatStreamer, it is
        stopped and removed.

        :param container_name: The container that needs to be removed
        """
        if container_name in self.__containers:
            logging.info(f"DockerDaemonClient - Removing container {container_name}")
            self.__containers[container_name] = container_name

        if container_name in self.__container_stats_streams:
            logging.debug(f"DockerDaemonClient - Stopping streamer for {container_name}")
            self.__container_stats_streams.pop(container_name).stop_stream()

    def __get_active_container_stats(self, container: Container) -> Dict:
        """
        Returns a dict with the active stats of the container with the information from the corresponding
        ContainerStatStreamer. Returns a empty dict if no ContainerStatStreamer exists for the container.

        :param container: The Container to get active stats for.
        :return: A dict with active stats if a ContainerStatStreamer exists for the container
        """
        stats = {}

        try:
            stats['started_at'] = container.attrs['State']['StartedAt']
            stats['command'] = []
            if container.attrs['Config'].get('Entrypoint', None):
                stats['command'].extend(container.attrs['Config'].get('Entrypoint', []))
            if container.attrs['Config'].get('Cmd', None):
                stats['command'].extend(container.attrs['Config'].get('Cmd', []))

            stats['cpu_stats'] = self.__container_stats_streams[container.name].get_cpu_stats()
            stats['memory_stats'] = self.__container_stats_streams[container.name].get_memory_stats()
            stats['net_io_stats'] = self.__container_stats_streams[container.name].get_network_io()
            stats['disk_io_stats'] = self.__container_stats_streams[container.name].get_disk_io()
            stats['ports'] = container.attrs['Config'].get('ExposedPorts', [])
        except Exception as e:
            logging.error(f"DockerDaemonClient - Failed getting active stats for {container.name} ({e})")
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

        self.__start_streaming_event_loop_thread()
        return True

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

    def start(self, container_name: str):
        self.__container_action(container_name, 'start')

    def restart(self, container_name: str):
        self.__container_action(container_name, 'restart')

    def pause(self, container_name: str):
        self.__container_action(container_name, 'pause')

    def resume(self, container_name: str):
        self.__container_action(container_name, 'resume')

    def stop(self, container_name: str):
        self.__container_action(container_name, 'stop')

    def kill(self, container_name: str):
        self.__container_action(container_name, 'kill')
