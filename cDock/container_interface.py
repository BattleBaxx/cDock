import time

from docker.models.containers import Container

from cDock.container_view import ContainerView


class ContainerInterface:

    def __init__(self, container: Container):
        self.__container = container
        self.stats = None
        self.time_initialized = time.time()
        self.last_checked_at = 0
        self.stats_generator = {}

    def get_container_view(self) -> ContainerView:
        raise NotImplementedError
