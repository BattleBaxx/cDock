from docker.models.containers import Container

from cDock.docker_client.info_streamer import InfoStreamer


class LogsStreamer(InfoStreamer):

    def __init__(self, container: Container):
        super().__init__(container, sleep_interval=0)
        self.logs: bytes = b''
        self.last_update_timestamp = self.time_initialized

    def get_stream_generator(self):
        return self.container.logs(stream=True)

    def stream_handler(self, streamed_value):
        self.logs += streamed_value

    def get_streamed_logs(self) -> str:
        logs = self.logs
        self.logs = b''
        return logs.decode('utf-8')
