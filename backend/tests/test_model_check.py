from __future__ import annotations

from app.model_check import inspect_seedvr2_environment


def test_model_readiness_reports_missing_cli_and_models(settings):
    status = inspect_seedvr2_environment(settings)

    assert status["ok"] is False
    assert status["cli"]["exists"] is False
    assert {model["name"] for model in status["models"]} == {"3B", "7B"}
