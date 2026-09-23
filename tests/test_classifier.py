import pytest

from app.classifier import CATEGORY_QUESTION, LayaClassifier


class StubAgent:
    """Expose the prediction shape returned by Laya's SDK."""

    def __init__(self, result: dict[str, object]) -> None:
        self.result = result

    def predict(
        self,
        state: dict[str, str],
        questions: dict[str, dict[str, object]],
    ) -> dict[str, object]:
        assert state["subject"] == "Cannot access ERP"
        assert state["body"] == "Login fails"
        assert questions == CATEGORY_QUESTION
        return self.result


def test_classifier_normalizes_laya_category_answer() -> None:
    classifier = LayaClassifier(
        StubAgent(
            {
                "answers": {
                    "category": {
                        "choice": "IT_SUPPORT",
                        "confidence": 0.91,
                        "probabilities": {"IT_SUPPORT": 0.91, "OTHER": 0.09},
                    }
                }
            }
        )
    )

    result = classifier.classify("Cannot access ERP", "Login fails")

    assert result == {
        "category": "IT_SUPPORT",
        "category_confidence": 0.91,
        "category_probabilities": {"IT_SUPPORT": 0.91, "OTHER": 0.09},
    }


def test_classifier_rejects_invalid_confidence() -> None:
    classifier = LayaClassifier(
        StubAgent(
            {
                "answers": {
                    "category": {
                        "choice": "IT_SUPPORT",
                        "confidence": float("nan"),
                        "probabilities": {"IT_SUPPORT": 1.0},
                    }
                }
            }
        )
    )

    with pytest.raises(ValueError, match="invalid category or confidence"):
        classifier.classify("Cannot access ERP", "Login fails")


def test_classifier_rejects_malformed_laya_payload() -> None:
    classifier = LayaClassifier(StubAgent({"answers": {}}))

    with pytest.raises(ValueError, match="missing the category answer"):
        classifier.classify("Cannot access ERP", "Login fails")
