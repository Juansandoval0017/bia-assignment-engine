import json
from pydantic import BaseModel, Field

from .models import Lead
from .settings import get_setting


class GroqConfigurationError(RuntimeError):
    """La configuración requerida para Groq no está completa."""


class LeadSignals(BaseModel):
    urgency: int = Field(ge=0, le=5)
    priority: int = Field(ge=0, le=5)
    requires_senior_contact: bool
    likely_segment: str | None = None
    alerts: list[str] = Field(default_factory=list)
    rationale: str


def build_lead_prompt(lead: Lead) -> str:
    return f"""Analiza este registro comercial y devuelve únicamente JSON válido.

Registro:
- id: {lead.id}
- empresa: {lead.razon_social}
- sector: {lead.sector or 'desconocido'}
- empleados: {lead.empleados if lead.empleados is not None else 'desconocido'}
- ingresos_estimados: {lead.ingresos_estimados if lead.ingresos_estimados is not None else 'desconocido'}
- ciudad: {lead.ciudad or 'desconocida'}
- zona: {lead.zona or 'desconocida'}
- fuente: {lead.fuente or 'desconocida'}
- notas: {lead.notas or 'sin notas'}

Esquema JSON exacto:
{{
  "urgency": 0,
  "priority": 0,
  "requires_senior_contact": false,
  "likely_segment": "string o null",
  "alerts": ["string"],
  "rationale": "explicación breve"
}}

No inventes datos. Usa 0 cuando no haya evidencia suficiente."""



class GroqProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or get_setting("GROQ_API_KEY")
        self.model = model or get_setting("GROQ_MODEL", "openai/gpt-oss-20b")
        if not self.api_key:
            raise GroqConfigurationError("Falta la variable de entorno GROQ_API_KEY")

    def analyze_lead(self, lead: Lead) -> tuple[LeadSignals, str, str]:
        try:
            from groq import Groq
        except ImportError as error:
            raise RuntimeError('Instala Groq con: pip install -e ".[groq]"') from error

        prompt = build_lead_prompt(lead)
        client = Groq(api_key=self.api_key, timeout=30.0, max_retries=1)
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un analista comercial preciso y conservador.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        response_text = response.choices[0].message.content or "{}"
        signals = LeadSignals.model_validate(json.loads(response_text))
        return signals, prompt, response_text
