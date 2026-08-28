"""Login and register pages.

See ARCHITECTURE.md's FE-3a entry for why the colour name must be
hyphenated at the use site, and FE-3b's entry for the submit handlers
below: why the API call uses in-process ASGI transport (frontend/api.py),
why data= is used for login but json= for register, why status code is
checked before body (the raw response body must never reach ui.notify —
REQ-USER-1's 422 detail echoes the submitted password back), and why
client-side validation on the register fields doesn't gate the button on
its own (submit() re-checks with explicit .validate() calls).
"""

from nicegui import app, ui

from . import api


def create() -> None:
    """Register the /login and /register pages."""

    @ui.page("/login")
    def login() -> None:
        username = ui.input("Username")
        password = ui.input("Password", password=True)

        async def submit() -> None:
            async with api.client() as http:
                response = await http.post(
                    "/auth/login",
                    data={"username": username.value, "password": password.value},
                )
            if response.status_code == 200:
                app.storage.user["token"] = response.json()["access_token"]
                app.storage.user["username"] = username.value
                ui.navigate.to("/")
            elif response.status_code == 401:
                ui.notify("Incorrect username or password")
            else:
                ui.notify("Could not complete the request.")

        ui.button("Log in", color="high-energy-pleasant", on_click=submit)
        ui.link("Register", "/register")

    @ui.page("/register")
    def register() -> None:
        username = ui.input(
            "Username",
            validation={"Username must be 3-50 characters": lambda v: 3 <= len(v or "") <= 50},
        )
        password = ui.input(
            "Password",
            password=True,
            validation={"Password must be at least 8 characters": lambda v: len(v or "") >= 8},
        )

        async def submit() -> None:
            username_ok = username.validate()
            password_ok = password.validate()
            if not (username_ok and password_ok):
                return
            async with api.client() as http:
                response = await http.post(
                    "/users",
                    json={"username": username.value, "password": password.value},
                )
            if response.status_code == 201:
                ui.navigate.to("/login")
            elif response.status_code == 400:
                ui.notify("Username already registered")
            else:
                ui.notify("Could not complete the request.")

        ui.button("Register", color="high-energy-pleasant", on_click=submit)
        ui.link("Log in", "/login")
