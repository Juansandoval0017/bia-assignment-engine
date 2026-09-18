from datetime import date

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    nombre: str
    rol: str
    equipo_id: int | None = None
    zona: str | None = None
    segmento_experto: str | None = None
    capacidad_maxima: float | None = None
    fecha_ingreso: date | None = None
    activo: bool


class Lead(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    razon_social: str
    sector: str | None = None
    empleados: float | None = None
    ingresos_estimados: float | None = None
    ciudad: str | None = None
    zona: str | None = None
    fuente: str | None = None
    notas: str | None = None
    estado: str
    fecha_creacion: date


class Absence(BaseModel):
    usuario_id: int
    desde: date
    hasta: date | None = None


class CandidateScore(BaseModel):
    user_id: int
    score: float | None
    reasons: list[str]


class Assignment(BaseModel):
    lead_id: int
    user_id: int | None
    score: float | None
    reasons: list[str]
    candidates: list[CandidateScore]


class LegacyReview(BaseModel):
    registro_id: int
    razon_social: str
    estado: str
    inferred_user_id: int | None
    historical_user_ids: list[int]
    activity_count: int
    latest_activity: date | None
    classification: str
    reason: str


class CurrentAssignment(BaseModel):
    registro_id: int
    usuario_id: int
    razon_social: str
    estado: str
    ultima_actividad: date | None = None


class ReassignmentProposal(BaseModel):
    registro_id: int
    razon_social: str
    current_user_id: int
    proposed_user_id: int | None
    reasons: list[str]
