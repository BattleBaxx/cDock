import fcntl
import logging
import os
import sys
import termios
import threading
import time
from datetime import datetime

# import pydevd_pycharm
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text

from cDock.config import Config
from cDock.docker_client.docker_daemon_client import DockerDaemonClient
from cDock.models import ContainerView

ui_to_container_view = {
    "name": "name",
    "id": "id",
    "status": "status",
    "image": "image",
    "cpu": "cpu_stats.usage",
    "mem_usage": "memory_stats.usage",
    "mem_limit": "memory_stats.limit",
    "rx/s": "net_io_stats.rx",
    "tx/s": "net_io_stats.tx",
    "ior/s": "disk_io_stats.ior",
    "iow/s": "disk_io_stats.iow",
    "created": "created_at",
    "started": "started_at",
    "ports": "published_ports",
    "command": "command"
}

def auto_unit(number, low_precision=False, min_symbol='K'):
    """Make a nice human-readable string out of number.
    Number of decimal places increases as quantity approaches 1.
    CASE: 613421788        RESULT:       585M low_precision:       585M
    CASE: 5307033647       RESULT:      4.94G low_precision:       4.9G
    CASE: 44968414685      RESULT:      41.9G low_precision:      41.9G
    CASE: 838471403472     RESULT:       781G low_precision:       781G
    CASE: 9683209690677    RESULT:      8.81T low_precision:       8.8T
    CASE: 1073741824       RESULT:      1024M low_precision:      1024M
    CASE: 1181116006       RESULT:      1.10G low_precision:       1.1G
    :low_precision: returns less decimal places potentially (default is False)
                    sacrificing precision for more readability.
    :min_symbol: Do not approache if number < min_symbol (default is K)
    """
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    if min_symbol in symbols:
        symbols = symbols[symbols.index(min_symbol):]
    prefix = {
        'Y': 1208925819614629174706176,
        'Z': 1180591620717411303424,
        'E': 1152921504606846976,
        'P': 1125899906842624,
        'T': 1099511627776,
        'G': 1073741824,
        'M': 1048576,
        'K': 1024
    }

    for symbol in reversed(symbols):
        value = float(number) / prefix[symbol]
        if value > 1:
            decimal_precision = 0
            if value < 10:
                decimal_precision = 2
            elif value < 100:
                decimal_precision = 1
            if low_precision:
                if symbol in 'MK':
                    decimal_precision = 0
                else:
                    decimal_precision = min(1, decimal_precision)
            elif symbol in 'K':
                decimal_precision = 0
            return '{:.{decimal}f}{symbol}'.format(
                value, decimal=decimal_precision, symbol=symbol)
    return '{!s}'.format(number)


def get_formatted_datetime(value):
    units = ["days", "hours", "minutes", "seconds"]

    duration_list = []
    total_seconds = value.total_seconds()

    duration_list.append(value.days)

    days = divmod(total_seconds, 86400)
    hours = divmod(days[1], 3600)
    minutes = divmod(hours[1], 60)
    seconds = divmod(minutes[1], 1)

    duration_list.append(int(hours[0]))
    duration_list.append(int(minutes[0]))
    duration_list.append(int(seconds[0]))

    non_zero_index = duration_list.index(next(filter(lambda x: x != 0, duration_list)))

    if non_zero_index == len(units) - 1:
        return f"{duration_list[non_zero_index]} seconds ago."

    return f"{duration_list[non_zero_index]} {units[non_zero_index]} ago."


class RichScreen:
    def __init__(self):
        self.input_chars = []
        self.config = Config.load_env_from_file("")
        self.row = 0
        self.column = 0
        self.refresh_layout = True
        self.layout = None
        self.single_container_view = False
        self.console = Console()

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.FileHandler('bug.txt', mode="w"))
        try:
            self.client = DockerDaemonClient(self.config)
            self.client.connect()
        except KeyboardInterrupt:
            pass

    def render(self):
        x = threading.Thread(target=self.input_handler, args=())
        x.start()
        with self.console.screen():
            with Live("", refresh_per_second=4) as live:
                while True:
                    self.update_layout()
                    time.sleep(1)
                    while len(self.input_chars) > 0:
                        self.input_chars.pop(0)
                    live.update(self.layout)

    def update_layout(self):
        try:
            if self.refresh_layout:
                self.refresh_layout = False
                self.layout = Layout()
                self.layout.split_column(Layout(name='details'), Layout(name="containers"))
                self.layout["details"].split_row(Layout(name='details_1'), Layout(name="details_2"))
                self.layout["containers"].ratio = 5

                if self.single_container_view:
                    self.layout["containers"].split_row(Layout(name='container_list'), Layout(name="single_container"))
                    self.layout["container_list"].ratio = 1
                    self.layout["containers"].size = None

            if self.single_container_view:
                self.layout['single_container'].update("Test")
                self.layout["container_list"].update(
                    self.generate_table(self.client.get_version_and_container_views()["container_views"]))
            else:
                pass
                self.layout["containers"].update(
                    self.generate_table(self.client.get_version_and_container_views()["container_views"]))

            self.layout['details_1'].update("End Point: primary\nURL: /var/run/docker.sock")
            self.layout['details_2'].update("Test")
        except KeyboardInterrupt:
            pass

    def generate_table(self, stats):
        if not self.single_container_view:
            size = self.console.size[0]
            rendering_attributes = ui_to_container_view.keys()
        else:
            rendering_attributes = self.config.priority_attributes.split(",")
            size = self.console.size[0] // 2
        table = Table(box=box.SIMPLE, width=size, header_style=self.config.tui_header_color)
        for attr in rendering_attributes:
            table.add_column(attr)
        for index, view in enumerate(stats):
            style = self.config.default_style
            if index == self.row:
                style = self.config.selected_row_style
            table.add_row(*self.generate_row(view, index), style=style)
        return table

    def generate_row(self, view: ContainerView, index):
        if not self.single_container_view:
            rendering_attributes = ui_to_container_view.keys()
        else:
            rendering_attributes = self.config.priority_attributes.split(",")
        count = 0
        renderables_list = []
        for attr in rendering_attributes:
            text = Text()
            style = ""
            attr = ui_to_container_view[attr].split(".")
            if len(attr) == 1:
                value = getattr(view, attr[0])
                if attr[0] == "started_at" or attr[0] == "created_at":
                    if value is None:
                        value = "-"
                    else:
                        value = get_formatted_datetime(datetime.now() - value.replace(tzinfo=None))
            else:
                if getattr(view, attr[0]) is None:
                    value = "_"
                else:
                    if attr[0] == "cpu_stats":
                        value = format(getattr(getattr(view, attr[0]), attr[1]), '.2f')
                    elif attr[0] == "memory_stats":
                        value = auto_unit(getattr(getattr(view, attr[0]), attr[1]))
                    else:
                        value = getattr(getattr(view, attr[0]), attr[1])

            if value == "created":
                style = self.config.container_created_style
            elif value == "restarting":
                style = self.config.container_restarting_style
            elif value == "running":
                style = self.config.container_running_style
            elif value == "paused":
                style = self.config.container_paused_style
            elif value == "exited":
                style = self.config.container_exited_style
            elif value == "dead":
                style = self.config.container_dead_style

            if count == self.column and index == self.row:
                style = self.config.selected_col_style
            text.append(str(value), style=style)
            renderables_list.append(text)
            count += 1
        return renderables_list

    def input_handler(self) -> list:
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

        try:
            while 1:
                try:
                    char = sys.stdin.read(1)
                    if char:
                        self.input_chars.append(char)
                        if char == 'w' and self.row != 0:
                            self.row -= 1
                        elif char == 's':
                            self.row += 1
                        elif char == 'a' and self.column != 0:
                            self.column -= 1
                        elif char == 'd':
                            self.column += 1
                        elif char == 'l':
                            self.refresh_layout = True
                            self.single_container_view = not self.single_container_view
                except IOError:
                    pass

        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)


if __name__ == "__main__":
    print("Stuff")
    obj = RichScreen()
    obj.render()
    print("Stuff")