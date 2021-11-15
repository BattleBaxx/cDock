import asyncio
import concurrent
import logging
from abc import ABC, abstractmethod
from concurrent.futures import Future
from datetime import datetime
from threading import Thread
from typing import Optional, Union

from docker.models.containers import Container


def run_event_loop(event_loop: asyncio.AbstractEventLoop) -> None:
    """
    A utility method used to run the event loop for streaming in a background thread.
    """
    asyncio.set_event_loop(event_loop)
    event_loop.run_forever()


class InfoStreamer(ABC):
    __executor = concurrent.futures.ThreadPoolExecutor()
    __event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    __event_loop_thread: Thread = Thread(target=run_event_loop, args=(__event_loop,))
    __event_loop_thread.daemon = True

    def __init__(self, container: Container, sleep_interval: Union[int, float] = 0.9):
        self.container: Container = container
        self.time_initialized: datetime = datetime.now()
        self.sleep_interval: Union[int, float] = sleep_interval

        # To stream container stats and stop when not required
        self.__stream_task: Optional[Future] = None

        self.__start_event_loop_thread()

    @classmethod
    def __start_event_loop_thread(cls) -> None:
        """
        Starts the background event loop thread if its not started yet. Returns if its already started
        """
        if not cls.__event_loop_thread.is_alive():
            cls.__event_loop_thread.start()

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

    async def __shared_executor_loop(self):
        with self.__executor as executor:
            await self.__event_loop.run_in_executor(executor, self.__stream_action)

        while True:
            await asyncio.sleep(self.sleep_interval)
            self.__stream_action()

    async def __private_executor_loop(self):
        with concurrent.futures.ThreadPoolExecutor(1) as executor:
            while True:
                await self.__event_loop.run_in_executor(executor, self.__stream_action)

    async def __stream_action_invoker(self, use_private_executor: bool) -> None:
        """
        Runs the executor loop which invokes the stream action_name periodically. Returns if another stream task was not
        setup or if it is already in progress

        :param use_private_executor: Set to True to use a private executor for the stream
        """
        if not self.__stream_task or self.__stream_task.running():
            return

        try:
            self.__stream_generator = self.get_stream_generator()

            if use_private_executor:
                await self.__private_executor_loop()
            else:
                await self.__shared_executor_loop()

        except Exception as e:
            logging.error(f"{self.__class__.__name__} - Exiting. {type(e)} while streaming: ({e})")

    def start_stream(self, use_private_executor: bool = False) -> None:
        """
        Generates the async stream task and schedules it, if its not already running.

        :param use_private_executor: Set to True to stream on a separate thread
        :raise Exception: if the stream task is already in progress
        """
        if self.__stream_task and self.__stream_task.running():
            raise Exception("Already streaming!")

        self.__stream_task = asyncio.run_coroutine_threadsafe(self.__stream_action_invoker(use_private_executor),
                                                              self.__event_loop)

    def stop_stream(self) -> None:
        """
        Stops the async streamer task and closes the generator.

        :raise Exception: if streaming was never started
        """
        if not isinstance(self.__stream_task, Future):
            raise Exception("Streaming was never started!")
        if not self.__stream_task.cancelled():
            self.__stream_task.cancel()
            self.__stream_generator.close()

    def get_container(self) -> Container:
        """
        Returns the internal container object

        :return: The Container used for the current
        """
        return self.container

    def update_container(self, container: Container) -> None:
        """
        Updates the the internal container object

        :param container: Newer container object to replace with
        """
        self.container = container
