"""HTTP API for the Laya ticket router.

Milestone 1 deliberately contains only the service shell. Model loading and
classification are added in later milestones, while the readiness contract is
already kept explicit for deployment orchestration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from flask import Flask, jsonify


@dataclass
class ModelStatus:
    """Runtime status shared by health and readiness endpoints."""

    name: str
    version: str
    loaded: bool = False


def _as_bool(value: Any, default: bool = False) -> bool:
    """Parse a boolean configuration value from environment or tests."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create and configure the Flask application.

    ``test_config`` is intentionally supported so endpoint tests can exercise
    both the not-ready and ready states without loading the model.
    """

    app = Flask(__name__)
    app.config.from_mapping(
        MODEL_NAME=os.getenv("MODEL_NAME", "laya-multilingual"),
        MODEL_VERSION=os.getenv("MODEL_VERSION", "bootstrap"),
        MODEL_LOADED=_as_bool(os.getenv("MODEL_LOADED")),
    )

    if test_config:
        app.config.update(test_config)

    model_status = ModelStatus(
        name=app.config["MODEL_NAME"],
        version=app.config["MODEL_VERSION"],
        loaded=_as_bool(app.config.get("MODEL_LOADED")),
    )
    app.extensions["model_status"] = model_status

    @app.get("/health")
    def health() -> tuple[Any, int]:
        """Report whether the HTTP process is alive."""

        return jsonify(
            status="ok",
            model_loaded=model_status.loaded,
            model=model_status.name,
        ), 200

    @app.get("/ready")
    def ready() -> tuple[Any, int]:
        """Report whether the service can serve model-backed requests."""

        if not model_status.loaded:
            return jsonify(
                status="not_ready",
                model_loaded=False,
                model=model_status.name,
            ), 503

        return jsonify(
            status="ready",
            model_loaded=True,
            model=model_status.name,
        ), 200

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
