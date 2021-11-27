import fcntl
import os
import sys
import termios
import time
from threading import Thread
from typing import List

from cDock.config import Config
from cDock.docker_client import DockerDaemonClient
from cDock.models import ContainerView
from cDock.outputs.screen import cDockRichScreen


class cDockStandalone:
    DEFAULT_REFRESH_TIME = 0.5

    def __init__(self):
        self.config = Config.load_env_from_file()
        self.screen = cDockRichScreen(self.config)
        self.client = DockerDaemonClient(self.config)

        self.row_index = 0
        self._changed = True
        self.last_stats_update_timestamp = 0

        self.container_views: List[ContainerView] = []

        self.is_running = True
        self.key_press_listener_thread = Thread(target=self.key_strokes_listener, args=())

    def run(self):
        self.client.connect()
        self.client.get_version_and_container_views()

        self.screen.init_screen()
        self.key_press_listener_thread.start()

        while self.is_running:
            try:
                if self._changed or self.is_after_refresh_window():
                    if self.is_after_refresh_window():
                        self.update_stats()

                    self.screen.render()
            except KeyboardInterrupt:
                self.shutdown()
            except Exception as e:
                self.shutdown()
                raise e

    def is_after_refresh_window(self):
        return time.time() - self.last_stats_update_timestamp > self.DEFAULT_REFRESH_TIME

    def update_stats(self):
        stats = self.client.get_version_and_container_views()
        row_key = self.get_row_key()
        self.container_views = stats['container_views']

        # Update row index to keep the same container selected
        self.row_index = 0
        for i, view in enumerate(self.container_views):
            if view.id == row_key:
                self.row_index = i
                break

        self.screen.update_container_table(self.container_views, self.row_index)
        self.last_stats_update_timestamp = time.time()

    def get_row_key(self):
        return self.container_views[self.row_index].id if self.container_views else ''

    def key_strokes_listener(self):
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

        try:
            while self.is_running:
                try:
                    char = sys.stdin.read(1)
                    if not char:
                        continue
                    self.handle_key_stroke(char)
                except IOError:
                    pass

        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

    def handle_key_stroke(self, key_pressed: str):
        if key_pressed == "w":
            self._update_row_index(self.row_index - 1)
        elif key_pressed == "s":
            self._update_row_index(self.row_index + 1)
        elif key_pressed == "q":
            self.shutdown()
        elif key_pressed == '1':
            self.container_action('start')
        elif key_pressed == '2':
            self.container_action('stop')
        elif key_pressed == '3':
            self.container_action('restart')
        elif key_pressed == '4':
            self.container_action('kill')
        elif key_pressed == '5':
            self.container_action('pause')
        elif key_pressed == '6':
            self.container_action('resume')

    def _update_row_index(self, index: int = None):
        if index is None:
            index = self.row_index
        self.row_index = index % max(len(self.container_views), 1)
        self._changed = True

    def container_action(self, action_name: str):
        key = self.get_row_key()
        if not key or action_name not in ['start', 'stop', 'restart', 'kill', 'pause', 'resume']:
            return
        try:
            action = getattr(self.client, action_name)
            action(key)
        except Exception as e:
            print(e)

    def shutdown(self):
        if self.is_running:
            self.is_running = False
            self.screen.stop()
            self.client.disconnect()
