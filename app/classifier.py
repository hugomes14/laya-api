"""Laya runtime and category-only ticket classification."""

from __future__ import annotations

import math
import os
from typing import Protocol, TypedDict


class LayaAgent(Protocol):
    """Minimal interface used from the external Laya SDK."""

    def predict(
        self,
        state: dict[str, str],
        questions: dict[str, dict[str, object]],
    ) -> dict[str, object]: ...


class Classification(TypedDict):
    """Normalized category result returned by this milestone."""

    category: str
    category_confidence: float
    category_probabilities: dict[str, float]


CATEGORY_QUESTION: dict[str, dict[str, object]] = {
    "category": {
        "type": "choice",
        "instructions": (
            "Classify this internal company support ticket into the single "
            "most appropriate operational category. Choose based on the "
            "request's main subject, not the team that should handle it."
        ),
        "criteria": {
            "IT_SUPPORT": (
                "Software, hardware, ERP, applications, email, printers, "
                "networking and technical failures. Suporte informático, "
                "hardware, aplicações, correio eletrónico e rede."
            ),
            "ACCESS_SECURITY": (
                "Accounts, passwords, MFA, permissions, administrator access "
                "and security incidents. Contas, palavras-passe, permissões "
                "e incidentes de segurança."
            ),
            "FINANCE_ADMIN": (
                "Invoices, payments, expenses, suppliers, procurement and "
                "reimbursements. Faturas, pagamentos, despesas, fornecedores "
                "e reembolsos."
            ),
            "HR_PEOPLE": (
                "Employees, leave, payroll, contracts, onboarding, "
                "offboarding and benefits. Recursos humanos, férias, salários, "
                "contratos e benefícios."
            ),
            "FACILITIES": (
                "Buildings, air conditioning, electricity, furniture, "
                "cleaning and physical maintenance. Instalações, climatização, "
                "eletricidade, limpeza e manutenção."
            ),
            "OTHER": (
                "Requests which clearly do not belong to another category. "
                "Pedidos que não pertencem claramente às restantes categorias."
            ),
        },
    }
}


class LayaClassifier:
    """Wrap a loaded Laya agent and normalize its category answer."""

    def __init__(self, agent: LayaAgent) -> None:
        self._agent = agent

    def classify(self, subject: str, body: str) -> Classification:
        """Return the best category, confidence and option probabilities."""

        result = self._agent.predict(
            {"subject": subject, "body": body}, CATEGORY_QUESTION
        )
        answers = result.get("answers")
        if not isinstance(answers, dict):
            raise ValueError("Laya result is missing the answers mapping")
        answer = answers.get("category")
        if not isinstance(answer, dict):
            raise ValueError("Laya result is missing the category answer")

        category = answer.get("choice")
        confidence = answer.get("confidence")
        probabilities = answer.get("probabilities")
        if (
            not isinstance(category, str)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            raise ValueError("Laya returned an invalid category or confidence")
        if not isinstance(probabilities, dict):
            raise ValueError("Laya result is missing category probabilities")
        if not all(
            isinstance(label, str)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and 0 <= value <= 1
            for label, value in probabilities.items()
        ):
            raise ValueError("Laya returned invalid category probabilities")
        if category not in probabilities:
            raise ValueError("Laya category is missing from its probabilities")

        return {
            "category": category,
            "category_confidence": float(confidence),
            "category_probabilities": {
                label: float(value) for label, value in probabilities.items()
            },
        }


def load_classifier() -> LayaClassifier:
    """Configure CPU inference and load the multilingual checkpoint once."""

    os.environ["USE_TF"] = "0"
    import torch
    import laya

    intra_threads = int(os.getenv("TORCH_NUM_THREADS", "4"))
    inter_threads = int(os.getenv("TORCH_NUM_INTEROP_THREADS", "1"))
    torch.set_num_threads(intra_threads)
    torch.set_num_interop_threads(inter_threads)

    agent = laya.load(
        os.getenv("LAYA_MODEL_ID", "convaiinnovations/laya"),
        subfolder=os.getenv("LAYA_MODEL_SUBFOLDER", "multilingual"),
        device=os.getenv("LAYA_DEVICE", "cpu"),
    )
    return LayaClassifier(agent)
