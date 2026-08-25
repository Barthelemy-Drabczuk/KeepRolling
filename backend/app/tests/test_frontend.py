"""Tests for the NiceGUI frontend mounted onto the FastAPI app (FE-1)."""


def test_root_page_serves_nicegui_placeholder(client) -> None:
    """GET / renders a NiceGUI page naming the app, not the old index.html."""
    response = client.get("/")

    assert response.status_code == 200
    assert "Moodometer" in response.text
