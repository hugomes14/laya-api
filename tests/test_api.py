from app.api import create_app


class StubClassifier:
    """Return a stable category result without loading model weights."""

    def classify(self, subject: str, body: str) -> dict[str, object]:
        assert subject
        assert isinstance(body, str)
        return {
            "category": "IT_SUPPORT",
            "category_confidence": 0.91,
            "category_probabilities": {"IT_SUPPORT": 0.91, "OTHER": 0.09},
        }


def test_health_reports_live_process_without_model() -> None:
    app = create_app({"TESTING": True})
    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "model_loaded": False,
        "model": "laya-multilingual",
    }


def test_ready_returns_503_until_model_is_loaded() -> None:
    app = create_app({"TESTING": True})
    response = app.test_client().get("/ready")

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "not_ready",
        "model_loaded": False,
        "model": "laya-multilingual",
    }


def test_ready_returns_200_after_model_is_loaded() -> None:
    app = create_app({"TESTING": True, "MODEL_LOADED": True})
    response = app.test_client().get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ready",
        "model_loaded": True,
        "model": "laya-multilingual",
    }


def test_classify_only_returns_category_without_routing() -> None:
    app = create_app({"TESTING": True, "CLASSIFIER": StubClassifier()})
    response = app.test_client().post(
        "/v1/classify-only",
        json={
            "ticket_id": "INC-12345",
            "subject": "Não consigo entrar no ERP",
            "body": "Aparece invalid credentials.",
        },
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["ticket_id"] == "INC-12345"
    assert result["classification"]["category"] == "IT_SUPPORT"
    assert result["classification"]["category_confidence"] == 0.91
    assert "routing" not in result
    assert result["model"]["name"] == "laya-multilingual"
    assert isinstance(result["latency_ms"], int)


def test_classify_only_rejects_invalid_json() -> None:
    app = create_app({"TESTING": True, "CLASSIFIER": StubClassifier()})
    response = app.test_client().post(
        "/v1/classify-only", data="not-json", content_type="application/json"
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_json"


def test_classify_only_requires_subject() -> None:
    app = create_app({"TESTING": True, "CLASSIFIER": StubClassifier()})
    response = app.test_client().post("/v1/classify-only", json={"body": "Text"})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_ticket"


def test_classify_only_rejects_oversized_subject() -> None:
    app = create_app({"TESTING": True, "CLASSIFIER": StubClassifier()})
    response = app.test_client().post(
        "/v1/classify-only", json={"subject": "x" * 501}
    )

    assert response.status_code == 400
    assert "500 characters" in response.get_json()["error"]["message"]


def test_classify_only_returns_not_ready_without_classifier() -> None:
    app = create_app({"TESTING": True, "LOAD_MODEL": False})
    response = app.test_client().post(
        "/v1/classify-only", json={"subject": "Ticket"}
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "model_not_ready"


def test_classify_only_returns_json_for_oversized_request() -> None:
    app = create_app({"TESTING": True, "CLASSIFIER": StubClassifier()})
    response = app.test_client().post(
        "/v1/classify-only",
        data='{"subject":"' + ("x" * 65_536) + '"}',
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "request_too_large"
