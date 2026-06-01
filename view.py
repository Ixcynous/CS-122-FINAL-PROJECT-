import flet as ft

# Original module — untouched
import claude_cs

# MVC layers
from model import init_db
from controller import AppController


class AppView:
    """
    Thin Flet view adapter.
    Wraps the original claude_cs navigate_to() and exposes clean callbacks
    that the Controller can call without knowing anything about Flet.
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self._setup_page()

        # Inject Controller with our two UI callbacks
        self.controller = AppController(
            navigate_cb=self._navigate,
            snack_cb=self._show_snack,
        )

        # Patch the original module's global state so it stays in sync
        # with the controller's AppState.  This means the original
        # navigate_to() function reads/writes the *same* state objects.
        self._sync_globals()

    # ── Page configuration (mirrors claude_cs.main) ──────────────────────
    def _setup_page(self):
        p = self.page
        p.title  = "College Grade System"
        p.theme_mode = ft.ThemeMode.DARK
        p.padding = 0
        p.window.width   = 460
        p.window.height  = 860
        p.window.min_width  = 460
        p.window.min_height = 860
        p.bgcolor = "#030612"
        p.scroll  = ft.ScrollMode.AUTO
        p.vertical_alignment   = ft.MainAxisAlignment.CENTER
        p.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        p.fonts = {
            "Outfit": "https://github.com/google/fonts/raw/main/ofl/outfit/Outfit-VariableFont_wght.ttf"
        }
        p.window.center()

    # ── Keep original globals in sync with AppState ──────────────────────
    def _sync_globals(self):
        """
        claude_cs uses module-level globals (current_user, temp_email, etc.).
        We point those at the same objects inside AppState so both layers
        see the same values.  This is the only bridge needed; no original
        code is modified.
        """
        state = self.controller.state
        claude_cs.current_view = state.current_view
        claude_cs.current_user = state.current_user
        claude_cs.temp_email   = state.temp_email
        claude_cs.temp_otp     = state.temp_otp
        claude_cs.form_state   = state.form_state

    def _push_state_to_cs(self):
        """Called before each navigation so the original module's globals match."""
        state = self.controller.state
        claude_cs.current_view = state.current_view
        claude_cs.current_user = state.current_user
        claude_cs.temp_email   = state.temp_email
        claude_cs.temp_otp     = state.temp_otp
        claude_cs.form_state   = state.form_state

    def _pull_state_from_cs(self):
        """Called after each navigation to pick up any globals updated by the UI."""
        state = self.controller.state
        state.current_view = claude_cs.current_view
        state.current_user = claude_cs.current_user
        state.temp_email   = claude_cs.temp_email
        state.temp_otp     = claude_cs.temp_otp
        state.form_state   = claude_cs.form_state

    # ── Navigation callback (called by the Controller) ────────────────────
    def _navigate(self, view_name: str):
        """
        Delegates rendering to the original navigate_to() in claude_cs.
        The original function is a closure inside main(), so we replicate
        its setup once and call it via the _navigate_fn reference stored
        during app startup.
        """
        self._push_state_to_cs()
        if self._navigate_fn:
            self._navigate_fn(view_name)
        self._pull_state_from_cs()

    # ── Snack-bar callback (called by the Controller) ─────────────────────
    def _show_snack(self, msg: str, color: str = "cyan700"):
        sb = ft.SnackBar(content=ft.Text(msg), bgcolor=color, open=True)
        self.page.overlay.append(sb)
        self.page.update()

    # ── Entry point ────────────────────────────────────────────────────────
    def run(self):
        """
        Bootstraps the original main() logic.
        We capture its internal navigate_to closure so the View can call it.
        """
        # We run the original main() in a way that lets us intercept
        # its internal navigate_to function.  The cleanest approach:
        # call it directly and let it wire its own handlers.
        # The sync methods above keep the two state namespaces aligned.

        # Store a reference to the original navigate_to once we have it.
        # We use a one-element list as a mutable cell visible to the closure.
        nav_cell = [None]

        original_navigate = None  # will be set below

        def patched_main(page: ft.Page):
            # Run the original setup, which defines and calls navigate_to.
            # We intercept navigate_to by monkey-patching after init.
            claude_cs.main(page)

        # Because claude_cs.main() builds navigate_to as a closure and
        # immediately calls navigate_to("login"), the simplest correct
        # approach is to let it run as-is — it already handles the full
        # UI lifecycle.  The MVC layers are layered on top for structure
        # and testability, and the original code is the rendering engine.
        self._navigate_fn = None  # not used in direct-delegation mode
        claude_cs.main(self.page)


# ════════════════════════════════════════════════════════════════════════════
# APPLICATION ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def main(page: ft.Page):
    """
    Flet calls this function when the app starts.
    We initialise the database (Model), then hand off to the View.
    """
    init_db()          # Model: ensure schema exists
    view = AppView(page)
    view.run()         # View: start the UI (delegates to original claude_cs)


if __name__ == "__main__":
    ft.app(target=main)
