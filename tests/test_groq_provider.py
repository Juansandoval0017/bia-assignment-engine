from datetime import date

import pytest

from app.groq_provider import GroqConfigurationError, build_lead_prompt
from app.models import Lead


def test_build_lead_prompt_includes_auditable_lead_data():
    lead = Lead(
        id=7,
        razon_social="Empresa Demo",
        notas="Pidió hablar con alguien senior.",
        estado="nuevo",
        fecha_creacion=date(2026, 9, 17),
    )

    prompt = build_lead_prompt(lead)

    assert "Empresa Demo" in prompt
    assert "Pidió hablar con alguien senior." in prompt
    assert '"requires_senior_contact"' in prompt


def test_groq_requires_api_key(monkeypatch):
    monkeypatch.setattr("app.settings.load_dotenv", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(GroqConfigurationError):
        from app.groq_provider import GroqProvider

        GroqProvider()
