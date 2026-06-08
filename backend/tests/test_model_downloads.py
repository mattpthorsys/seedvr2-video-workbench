from __future__ import annotations

from app.main import app
from app.model_downloads import download_status, model_download_options, start_model_download


def test_model_download_routes_are_registered():
    routes = {(route.path, tuple(sorted(route.methods))) for route in app.routes if hasattr(route, "methods")}

    assert ("/api/models/downloads", ("GET",)) in routes
    assert ("/api/models/downloads", ("POST",)) in routes


def test_model_download_status_reports_idle_downloadables(settings):
    options = model_download_options()
    status = download_status(settings)

    assert {option["model"] for option in options} == {"3B", "7B"}
    assert {download["model"] for download in status} == {"3B", "7B"}
    assert {download["status"] for download in status} == {"idle"}
    assert all(download["repo_id"].startswith("ByteDance-Seed/SeedVR2-") for download in status)


def test_start_model_download_rejects_unknown_model(settings):
    try:
        start_model_download(settings, "13B")
    except ValueError as exc:
        assert "Unknown downloadable model" in str(exc)
    else:
        raise AssertionError("Expected unknown model to be rejected")
