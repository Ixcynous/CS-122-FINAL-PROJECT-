
import flet as ft
from model import init_db
from view import AppView


def main(page: ft.Page):
    init_db()           # Model bootstrap
    view = AppView(page)
    view.run()


if __name__ == "__main__":
    ft.app(target=main)
