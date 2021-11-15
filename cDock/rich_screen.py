import fcntl
import logging
import os
import random
import string
import sys
import termios
import threading
import time
from datetime import datetime

from ascii_graph import Pyasciigraph
from rich import box
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
# from rich.style import Style
from rich.text import Text

from cDock.config import Config
from cDock.console import console
from cDock.docker_daemon_client import DockerDaemonClient
from cDock.models import ContainerView

# console = Console()
# char = None
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


def get_formatted_memory(value):
    suffixs = ["", "KB", "MB", "GB", "TB"]
    denominator = 1024
    i = 0
    while i <= 4:
        if value / 1024 > 1:
            denominator *= 1024
            value /= 1024
        else:
            break
        i += 1
    return str(format(value, '.2f')) + " " + suffixs[i]


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

    return f"{duration_list[non_zero_index]} {units[non_zero_index]}, {duration_list[non_zero_index + 1]} {units[non_zero_index + 1]} ago."


class RichScreen:
    def __init__(self):
        self.input_chars = []
        self.config = Config.load_env_from_file("")
        self.row = 0
        self.column = 0
        self.refresh_layout = True
        self.layout = None
        self.single_container_view = True

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.FileHandler('bug.txt', mode="w"))

        config = Config.load_env_from_file(None)
        try:
            self.client = DockerDaemonClient(config)
            self.client.connect()
        except KeyboardInterrupt:
            pass

    def render(self):
        # self.logger.info("In render")
        x = threading.Thread(target=self.input_handler, args=())
        x.start()
        with console.screen():
            with Live("", refresh_per_second=4) as live:
                while True:
                    # self.logger.info("In while loop")
                    self.update_container_details()
                    self.update_layout()
                    time.sleep(1)
                    while len(self.input_chars) > 0:
                        self.input_chars.pop(0)
                    live.update(self.layout)

    def update_layout(self):
        # self.logger.info("In Update layout")
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

    def update_container_details(self):
        self.container_details = []
        for _ in range(10):
            details_dict = {
                "id": random.randint(0, 600),
                "image": ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)),
                "stack": ''.join(random.choices(string.ascii_uppercase + string.digits, k=5)),
                "created": str(time.time()),
                "updated": str(time.time())
            }
            self.container_details.append(details_dict)

    def generate_table(self, stats):
        # self.logger.info("In generate table")
        if not self.single_container_view:
            size = console.size[0]
            rendering_attributes = ui_to_container_view.keys()
        else:
            rendering_attributes = self.config.priority_attributes.split(",")
            size = console.size[0] // 2
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
        # self.logger.info("In generate row")
        if not self.single_container_view:
            rendering_attributes = ui_to_container_view.keys()
        else:
            rendering_attributes = self.config.priority_attributes.split(",")
        count = 0
        renderables_list = []
        for attr in rendering_attributes:
            text = Text()
            style = ""
            if count == self.column and index == self.row:
                style = self.config.selected_col_style
            attr = ui_to_container_view[attr].split(".")
            if len(attr) == 1:
                value = getattr(view, attr[0])
                if attr[0] == "started_at" or attr[0] == "created_at":
                    value = get_formatted_datetime(datetime.now() - value.replace(tzinfo=None))
            else:
                if getattr(view, attr[0]) is None:
                    value = "_"
                else:
                    if attr[0] == "cpu_stats":
                        value = format(getattr(getattr(view, attr[0]), attr[1]), '.2f')
                    elif attr[0] == "memory_stats":
                        value = get_formatted_memory(getattr(getattr(view, attr[0]), attr[1]))
                    else:
                        value = getattr(getattr(view, attr[0]), attr[1])
            text.append(str(value), style=style)
            renderables_list.append(text)
            count += 1
        return renderables_list

    # def generate_single_table(self):
    #     table = Table(box=box.SIMPLE)
    #     table.add_column("")
    #     test = [('long_label', 423), ('sl', 1234), ('line3', 531),
    #             ('line4', 200), ('line5', 834)]
    #     pattern = [Gre, Cya, Pur]
    #     thresholds = {
    #         51: Gre, 100: Blu, 350: Yel, 500: Red,
    #     }
    #     data = vcolor(test, pattern)
    #     graph = Pyasciigraph()
    #     for line in graph.graph('test print', data):
    #         table.add_row("", line)
    #     return table

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
                        logging.info(char)
                        if char == 'w' and self.row != 0:
                            self.row -= 1
                        elif char == 's' and self.row != len(self.container_details) - 1:
                            self.row += 1
                        elif char == 'a' and self.column != 0:
                            self.column -= 1
                        elif char == 'd' and self.column != len(self.container_details[0].keys()) - 1:
                            self.column += 1
                        elif char == 'l':
                            self.refresh_layout = True
                            self.single_container_view = not self.single_container_view
                except IOError:
                    pass

        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

    def render_test(self):
        test = [('long_label', 423), ('sl', 1234), ('line3', 531),
                ('line4', 200), ('line5', 834)]

        graph = Pyasciigraph()
        text = ''
        for line in graph.graph('test print', test):
            # print(line)
            text += line + '\n'
        print(text)
        # layout = Layout()
        # layout.split_column(Layout(name = 'details'), Layout(name="containers"))
        # layout["details"].split_row(Layout(name = 'details_1'), Layout(name="details_2"))
        # layout["containers"].split_row(Layout(name='container_list'), Layout(name="single_container"))
        # layout["containers"].ratio = 5
        # layout["container_list"].ratio = 3
        # layout["container_list"].update("Sometext")
        # console.print(layout)


if __name__ == "__main__":
    print("Stuff")
    obj = RichScreen()
    obj.render()
    print("Stuff")
    # inspect(console)

# supercali = "supercalifragilisticexpialidocious"
# console.print(supercali, overflow="ellipsis", style="bold blue")
# with console.screen(style="bold white on red") as screen:
#     for count in range(5, 0, -1):
#         text = Align.center(
#             Text.from_markup(f"[blink]Don't Panic![/blink]\n{count}", justify="center"),
#             vertical="middle",
#         )
#         screen.update(Panel(text))
#         time.sleep(1)
# with console.screen():
#     console.rule("[bold red]Testing RICH")
#     console.print("Hello World!", style="uu frame red on white")
#     pprint(locals())
#     console.print(locals())
#     time.sleep(5)
# console.input("What is [i]your[/i] [bold red]name[/]? :smiley: ")
# console.print([1, 2, 3])
# console.print("[blue underline]Looks like a link")
# console.print(locals())
# console.print("FOO", style="white on blue")
# console.out("Locals", locals())
# with console.status("Working..."):
#     print("Doing stuff")
#     time.sleep(10)
