"""Login and register pages.

See ARCHITECTURE.md's FE-3a entry for why the colour name must be
hyphenated at the use site, and FE-3b's entry for the submit handlers
below: why the API call uses in-process ASGI transport (frontend/api.py),
why data= is used for login but json= for register, why status code is
checked before body (the raw response body must never reach ui.notify --
REQ-USER-1's 422 detail echoes the submitted password back), and why
client-side validation on the register fields doesn't gate the button on
its own (submit() re-checks with explicit .validate() calls).

2026-09 redesign: these are the only two routes that render without
shell.page_shell -- a full-bleed split with a brand slab enumerating all
eight mood zones (colour + caption, each band's height roughly matching
its area on the pad) down one side and the form on the other. Every
field/button label, colour and validation rule tested by
tests/test_frontend.py is unchanged; only presentation and the
error-message *placement* (inline alert instead of ui.notify) move.
"""

from nicegui import app, ui

from . import api

# zone id, flex-grow weight (roughly proportional to its pad-area), caption ink
_BRAND_BANDS: tuple[tuple[str, int, str], ...] = (
    ("reckless_energy", 13, "#ffffff"),
    ("energetic_optimism", 17, "#1c1a17"),
    ("peak_excitement", 4, "#1c1a17"),
    ("resigned_acceptance", 11, "#1c1a17"),
    ("sinking_despair", 16, "#1c1a17"),
    ("deep_despair", 4, "#1c1a17"),
    ("relaxed_contentment", 10, "#1c1a17"),
    ("neutral", 4, "#1c1a17"),
)


def _brand_slab() -> None:
    from . import ZONE_CAPTIONS, ZONE_COLOURS

    with (
        ui.column()
        .classes("gap-0")
        .style("width:32%;min-width:280px;min-height:100vh;border-right:2px solid #1c1a17")
    ):
        ui.label("MOODOMETER").classes("text-2xl font-black p-4 pb-0")
        for zone, weight, ink in _BRAND_BANDS:
            with (
                ui.row()
                .classes("items-center px-4")
                .style(
                    f"flex:{weight} 1 0;width:100%;background:{ZONE_COLOURS[zone]};"
                    f"border-bottom:2px solid #1c1a17"
                )
            ):
                ui.label(ZONE_CAPTIONS[zone]).style(f"color:{ink}").classes("font-black")


def create() -> None:
    """Register the /login and /register pages."""

    @ui.page("/login")
    def login() -> None:
        from . import inject_house_style

        inject_house_style()
        with ui.row().classes("w-full items-stretch no-wrap").style("margin:0"):
            _brand_slab()
            with ui.column().classes("items-center justify-center flex-grow p-8"):
                with ui.column().classes("gap-4").style("width:380px"):
                    ui.label("Log in").classes("text-3xl font-black")
                    error = ui.label("Incorrect username or password.").classes(
                        "mo-warn p-2 text-sm"
                    )
                    error.set_visibility(False)
                    username = ui.input("Username").classes("w-full")
                    password = ui.input("Password", password=True).classes("w-full")

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
                            error.set_visibility(True)
                        else:
                            ui.notify("Could not complete the request.")

                    ui.button("Log in", color="high-energy-pleasant", on_click=submit).classes(
                        "w-full"
                    )
                    with ui.row().classes("gap-1 mo-muted"):
                        ui.label("No account?")
                        ui.link("Register", "/register")

    @ui.page("/register")
    def register() -> None:
        from . import inject_house_style

        inject_house_style()
        with ui.row().classes("w-full items-stretch no-wrap").style("margin:0"):
            _brand_slab()
            with ui.column().classes("items-center justify-center flex-grow p-8"):
                with ui.column().classes("gap-4").style("width:380px"):
                    ui.label("Create an account").classes("text-3xl font-black")
                    taken_error = ui.label("That username is taken.").classes("mo-warn p-2 text-sm")
                    taken_error.set_visibility(False)
                    username = ui.input(
                        "Username",
                        validation={
                            "Username must be 3-50 characters": lambda v: 3 <= len(v or "") <= 50
                        },
                    ).classes("w-full")
                    password = ui.input(
                        "Password",
                        password=True,
                        validation={
                            "Password must be at least 8 characters": lambda v: len(v or "") >= 8
                        },
                    ).classes("w-full")

                    async def submit() -> None:
                        username_ok = username.validate()
                        password_ok = password.validate()
                        if not (username_ok and password_ok):
                            return
                        taken_error.set_visibility(False)
                        async with api.client() as http:
                            response = await http.post(
                                "/users",
                                json={"username": username.value, "password": password.value},
                            )
                        if response.status_code == 201:
                            ui.navigate.to("/login")
                        elif response.status_code == 400:
                            taken_error.set_visibility(True)
                        else:
                            ui.notify("Could not complete the request.")

                    ui.button("Register", color="high-energy-pleasant", on_click=submit).classes(
                        "w-full"
                    )
                    with ui.row().classes("gap-1 mo-muted"):
                        ui.label("Already have an account?")
                        ui.link("Log in", "/login")
