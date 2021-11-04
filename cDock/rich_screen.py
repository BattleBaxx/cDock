import fcntl
import os
import random
import string
import sys
import termios
import threading
import time

from ascii_graph import Pyasciigraph
from ascii_graph.colordata import vcolor
from ascii_graph.colors import *
from rich import box
from console import console
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
# from rich.style import Style
from rich.text import Text

from config import Config

# console = Console()
char = None

class RichScreen:
    def __init__(self):
        self.input_chars = []
        self.config = Config.load_env_from_file("../tests/test.env")
        self.row = 0
        self.column = 0
        self.console_screen = None
        details_dict = {
            "id": random.randint(0, 600),
            "image": ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)),
            "stack": ''.join(random.choices(string.ascii_uppercase + string.digits, k=5)),
            "created": str(time.time()),
            "updated": str(time.time())
        }
        self.container_details = []
        for _ in range(10):
            self.container_details.append(details_dict)
    def render(self):
        x = threading.Thread(target=self.input_handler, args=())
        x.start()
        container_details = []
        layout = Layout()
        layout.split_column(Layout(name='details'), Layout(name="containers"))
        layout["details"].split_row(Layout(name='details_1'), Layout(name="details_2"))
        layout["containers"].split_row(Layout(name='container_list'), Layout(name="single_container"))
        layout["containers"].size = None
        layout["containers"].ratio = 5
        layout["container_list"].ratio = 1

        with console.screen():
            with Live(self.generate_table(self.container_details), refresh_per_second=4) as live:
                while True:
                    self.update_container_details()
                    time.sleep(0.001)
                    while len(self.input_chars) > 0:
                        self.input_chars.pop(0)
                    layout['details_1'].update("End Point: primary\nURL: /var/run/docker.sock")
                    layout['details_2'].update("Test")
                    layout['single_container'].update(self.generate_single_table())
                    layout["container_list"].update(self.generate_table(self.container_details))
                    # console.print(layout)
                    live.update(layout)

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

    def generate_table(self, container_details):
        table = Table(box=box.SIMPLE , width=console.size[0]/2, header_style=self.config.header_color)
        table.add_column("ID")
        table.add_column("Stack")
        table.add_column("Image")
        table.add_column("Created")
        table.add_column("Updated")
        for index, details_dict in enumerate(container_details):
            style = 'white'
            if index == self.row:
                style = "cyan"
            count = 0
            renderables_list = []
            for key, value in details_dict.items():
                text = Text()
                if count == self.column and index == self.row:
                    text.append(str(value), style="green bold")
                else:
                    text.append(str(value))
                renderables_list.append(text)
                count += 1
            table.add_row(*renderables_list, style=style)
        return table

    def generate_single_table(self):
        table = Table(box=box.SIMPLE)
        table.add_column("")
        test = [('long_label', 423), ('sl', 1234), ('line3', 531),
                ('line4', 200), ('line5', 834)]
        pattern = [Gre, Cya, Pur]
        thresholds = {
            51: Gre, 100: Blu, 350: Yel, 500: Red,
        }
        data = vcolor(test, pattern)
        graph = Pyasciigraph()
        for line in graph.graph('test print', data):
            table.add_row("", line)
        return table

    def input_handler(self) -> list:
        global style
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
                        elif char == 's' and self.row != len(self.container_details)-1:
                            self.row += 1
                        elif char == 'a' and self.column != 0:
                            self.column -= 1
                        elif char == 'd' and self.column != len(self.container_details[0].keys())-1:
                            self.column += 1
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
