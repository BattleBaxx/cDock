import time

from docker.types import ContainerSpec

from cDock.container_view import ContainerView


class ContainerInterface:

    def __init__(self, container: ContainerSpec):
        self.__container = container
        self.stats = {}
        self.time_initialized = time.time()
        self.last_checked_at = 0
        self.stats_generator = {}

    def get_container_view(self) -> ContainerView:
        raise NotImplementedError
