"""Login and register pages.

See ARCHITECTURE.md's FE-3a entry for why the colour name must be
hyphenated at the use site, why cross-navigation uses ui.link (not a
button with on_click), and what's deliberately out of scope here
(form submission, app.storage.user, navigation — all FE-3b).
"""

from nicegui import ui


def create() -> None:
    """Register the /login and /register pages."""

    @ui.page("/login")
    def login() -> None:
        ui.input("Username")
        ui.input("Password", password=True)
        ui.button("Log in", color="high-energy-pleasant")
        ui.link("Register", "/register")

    @ui.page("/register")
    def register() -> None:
        ui.input("Username")
        ui.input("Password", password=True)
        ui.button("Register", color="high-energy-pleasant")
        ui.link("Log in", "/login")
