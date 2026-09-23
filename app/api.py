"""HTTP API for the Laya ticket router."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from flask import Flask, jsonify, request

from .classifier import load_classifier


logger = logging.getLogger(__name__)
MAX_SUBJECT_LENGTH = 500
MAX_BODY_LENGTH = 10_000


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
        LOAD_MODEL=_as_bool(os.getenv("LOAD_MODEL"), default=True),
        MAX_CONTENT_LENGTH=65_536,
    )

    if test_config:
        app.config.update(test_config)
        if test_config.get("TESTING") and "LOAD_MODEL" not in test_config:
            app.config["LOAD_MODEL"] = False

    model_status, classifier = _initialize_model(app)
    app.extensions["model_status"] = model_status
    app.extensions["classifier"] = classifier
    _register_health_routes(app, model_status)
    _register_classify_route(app, model_status, classifier)
    app.register_error_handler(413, _request_too_large)
    return app


def _initialize_model(app: Flask) -> tuple[ModelStatus, Any | None]:
    """Load the classifier once and retain readiness state for the app."""

    model_status = ModelStatus(
        name=app.config["MODEL_NAME"],
        version=app.config["MODEL_VERSION"],
        loaded=(
            _as_bool(app.config.get("MODEL_LOADED"))
            if app.config["TESTING"]
            else False
        ),
    )
    classifier = app.config.get("CLASSIFIER")

    if classifier is not None:
        model_status.loaded = True
    elif not model_status.loaded and app.config["LOAD_MODEL"]:
        load_started = time.perf_counter()
        try:
            classifier = load_classifier()
            model_status.loaded = True
            logger.info(
                "Laya model loaded",
                extra={
                    "model": model_status.name,
                    "model_version": model_status.version,
                    "load_seconds": round(time.perf_counter() - load_started, 3),
                },
            )
        except Exception:
            logger.exception("Laya model failed to load")

    return model_status, classifier


def _register_health_routes(app: Flask, model_status: ModelStatus) -> None:
    """Register liveness and readiness endpoints."""

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


def _register_classify_route(
    app: Flask, model_status: ModelStatus, classifier: Any | None
) -> None:
    """Register the category-only classification endpoint."""

    @app.post("/v1/classify-only")
    def classify_only() -> tuple[Any, int]:
        """Classify a ticket category without selecting a route."""

        if not request.is_json:
            return _error(
                "unsupported_media_type", "Content-Type must be application/json", 415
            )
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("invalid_json", "Request body must be a JSON object", 400)

        validation_error = _validate_ticket(payload)
        if validation_error is not None:
            return _error("invalid_ticket", validation_error, 400)
        if classifier is None:
            return _error("model_not_ready", "Laya model is not loaded", 503)

        subject = payload["subject"]
        body = payload.get("body", "")
        started = time.perf_counter()
        try:
            classification = classifier.classify(subject, body)
        except Exception:
            logger.exception("Ticket classification failed")
            return _error(
                "classification_failed", "Ticket could not be classified", 500
            )

        response: dict[str, object] = {
            "classification": classification,
            "model": {
                "name": model_status.name,
                "version": model_status.version,
            },
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
        if "ticket_id" in payload:
            response["ticket_id"] = payload["ticket_id"]
        return jsonify(response), 200


def _request_too_large(exception: Exception) -> tuple[Any, int]:
    """Return a consistent JSON response for oversized requests."""

    del exception
    return _error(
        "request_too_large", "Request exceeds the 65536-byte limit", 413
    )


def _validate_ticket(payload: dict[str, Any]) -> str | None:
    """Return a validation message for a malformed ticket, if any."""

    subject = payload.get("subject")
    body = payload.get("body", "")
    ticket_id = payload.get("ticket_id")
    if not isinstance(subject, str) or not subject.strip():
        return "subject must be a non-empty string"
    if len(subject) > MAX_SUBJECT_LENGTH:
        return f"subject must be at most {MAX_SUBJECT_LENGTH} characters"
    if not isinstance(body, str):
        return "body must be a string"
    if len(body) > MAX_BODY_LENGTH:
        return f"body must be at most {MAX_BODY_LENGTH} characters"
    if ticket_id is not None and not isinstance(ticket_id, str):
        return "ticket_id must be a string"
    return None


def _error(code: str, message: str, status: int) -> tuple[Any, int]:
    """Build a consistent JSON error response."""

    return jsonify(error={"code": code, "message": message}), status


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
