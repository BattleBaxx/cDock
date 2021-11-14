import asyncio
import concurrent
import logging
from abc import ABC, abstractmethod
from concurrent.futures import Future
from datetime import datetime
from typing import Optional, Union

from docker.models.containers import Container


class ContainerInfoStreamer(ABC):

    def __init__(self, container: Container, loop: asyncio.AbstractEventLoop, sleep_interval: Union[int, float] = 0.9):
        self.container: Container = container
        self.time_initialized: datetime = datetime.now()
        self.sleep_interval: Union[int, float] = sleep_interval

        # To stream container stats and stop when not required
        self.__streaming_event_loop: asyncio.AbstractEventLoop = loop
        self.__stream_task: Optional[Future] = None

    @abstractmethod
    def stream_handler(self, streamed_value):
        """
        The handler for the streamed value from the stream_generator. Must be overridden.
        """
        ...

    @abstractmethod
    def get_stream_generator(self):
        """
        Return the blocking generator used for streaming. Must be overridden.
        """
        ...

    def __stream_action(self):
        """
        Action to be executed every `sleep_interval` seconds
        """
        self.stream_handler(next(self.__stream_generator))

    async def __stream_action_loop(self):
        # Return if not task not setup or another async task is already running
        if not self.__stream_task or self.__stream_task.running():
            return

        try:
            self.__stream_generator = self.get_stream_generator()

            with concurrent.futures.ThreadPoolExecutor() as pool:
                await self.__streaming_event_loop.run_in_executor(pool, self.__stream_action)

            while True:
                await asyncio.sleep(self.sleep_interval)
                self.__stream_action()
        except Exception as e:
            logging.error(f"{self.__class__.__name__} - Exiting. Exception while streaming: ({e})")

    def start_stream(self):
        """
        Generates the async streamer task and starts it, if its not already running
        """
        if self.__stream_task and self.__stream_task.running():
            raise Exception("Already streaming!")
        self.__stream_task = asyncio.run_coroutine_threadsafe(self.__stream_action_loop(), self.__streaming_event_loop)

    def stop_stream(self):
        """
        Stops the async streamer task
        """
        if not isinstance(self.__stream_task, Future):
            raise Exception("Streaming was never started!")
        if not self.__stream_task.cancelled():
            self.__stream_task.cancel()

    def get_container(self) -> Container:
        """
        Returns the internal container object
        :return: The Container used for the current
        """
        return self.container

    def update_container(self, container: Container) -> None:
        self.container = container
