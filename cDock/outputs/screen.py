from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text

from cDock.config import Config
from cDock.outputs.formatter import RichFormatter


class cDockRichScreen:
    def __init__(self, config: Config):
        self.config = config
        self.console = Console()

        self.split_view = False
        self.container_table = Table()
        self.formatter = RichFormatter(config)

        self.live = Live(console=self.console)

    def init_screen(self):
        self.live.start(False)

    def render(self):
        self.live.update(self.prepare_layout())

    def prepare_layout(self):
        layout = Layout()
        layout.split(
            # Layout(name="header", size=2),
            Layout(name="main"),
            Layout(name="footer", size=1),
        )

        layout['main'].update(self.container_table)
        layout['footer'].update(self.prepare_footer())
        return layout

    def prepare_footer(self):
        grid = Table.grid(padding=(1, 1))

        options_dict = {
            "w": "Up     ",
            "s": "Down   ",
            "1": "Start  ",
            "2": "Down   ",
            "3": "Restart",
            "4": "Kill   ",
            "5": "Pause  ",
            "6": "Resume ",
            "q": "Quit   "
        }
        rendering_list = []
        for key in options_dict.keys():
            grid.add_column()
            text = Text()
            text.append(key)
            text.append(options_dict[key], style="black on cyan")
            rendering_list.append(text)

        grid.add_row(*rendering_list)
        return grid

    def update_container_table(self, container_views, index):
        title = f"CONTAINERS ({len(container_views)}) - cDock"
        table = Table(box=box.SIMPLE, header_style=self.config.tui_header_color, expand=True, title=title)
        for i, column in enumerate(self.formatter.get_header_row()):
            table.add_column(column)

        for i, view in enumerate(container_views):
            row = self.formatter.get_container_row(view)
            if i == index:
                table.add_row(*row, style=self.config.selected_row_style)
            else:
                table.add_row(*row)
        self.container_table = table

    def stop(self):
        self.live.stop()
