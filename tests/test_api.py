from app.api import create_app


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
