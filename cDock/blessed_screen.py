import blessed
import time

try:
    import cursor
except:
    cursor = None


class BlessedScreen:
    def __init__(self):
        self.term = blessed.Terminal()
        print(self.term.civics)
        if cursor:
            cursor.hide()
        self.get_screen()

    def get_screen(self):
        with self.term.fullscreen(), self.term.cbreak():
            val = ''
            while val.lower() != 'q':
                val = self.term.inkey(timeout=1)
                # print(self.term.black_on_skyblue)
                # print(f"{self.term.home}{self.term.skyblue_on_black}{self.term.clear}")
                # print("Something")
                print(self.term.green_reverse("All systems go"))
                # time.sleep(5)


if __name__ == "__main__":
    obj = BlessedScreen()
