"""HTTP transport for frontend/ calling its own co-hosted REST API.

See ARCHITECTURE.md's FE-3b entry for why this is in-process ASGI
transport (not a real network round-trip) and why the FastAPI app is
imported lazily inside client(), not at module scope (app.py imports
frontend before app.py's own `app` object exists, so a top-level
`import app` here would be a circular import).
"""

import httpx

BASE_URL = "http://moodometer.internal"  # ASGITransport ignores the host;
# httpx just requires an absolute URL


def client() -> httpx.AsyncClient:
    """An httpx client that dispatches straight into the FastAPI app."""
    import app as backend

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend.app, raise_app_exceptions=False),
        base_url=BASE_URL,
    )


def auth_headers(token: str) -> dict[str, str]:
    """The Authorization header every authenticated frontend call sends."""
    return {"Authorization": f"Bearer {token}"}
