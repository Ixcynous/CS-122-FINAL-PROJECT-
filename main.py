"""
main.py — MVC Entry Point
===========================
Run this file to start the application:

    python main.py

MVC structure
─────────────
  main.py          ← you are here (entry point)
  view.py          ← View   : Flet UI, delegates rendering to claude_cs.py
  controller.py    ← Controller : business logic & navigation decisions
  model.py         ← Model  : SQLite data access & pure helper functions
  claude_cs.py     ← Original source (UNTOUCHED) — used as the render engine

The original claude_cs.py is not modified in any way.
"""

import flet as ft
from model import init_db
from view import AppView


def main(page: ft.Page):
    init_db()           # Model bootstrap
    view = AppView(page)
    view.run()


if __name__ == "__main__":
    ft.app(target=main)
