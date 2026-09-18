from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .assignment import preview_assignments
from .data_loader import load_absences, load_leads, load_users
from .models import Assignment
from .models import Lead
from .groq_provider import GroqProvider
from .snowflake_repository import SnowflakeRepository


class PreviewRequest(BaseModel):
    execution_date: date = Field(default_factory=date.today)
    current_load: dict[int, int] = Field(default_factory=dict)
    lead_ids: list[int] | None = None
    method: str = "weighted_score"
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "zone": 0.35,
            "segment": 0.25,
            "capacity": 0.25,
            "balance": 0.15,
        }
    )


class SnowflakeExecutionRequest(PreviewRequest):
    executed_by: str
    method: str = "weighted_score"
    parameters: dict[str, object] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    run_id: int
    approved_by: str


class ExecutionRequest(BaseModel):
    run_id: int


app = FastAPI(
    title="Bia Assignment Engine",
    version="0.1.0",
    description="API para previsualizar asignaciones comerciales.",
)


def _data_path(filename: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / filename


def _load_demo_data():
    paths = {
        "users": _data_path("usuarios.csv"),
        "leads": _data_path("registros.csv"),
        "absences": _data_path("ausencias.csv"),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Los datos de demostracion no estan disponibles.",
                "missing_files": missing,
            },
        )
    return (
        load_users(paths["users"]),
        load_leads(paths["leads"]),
        load_absences(paths["absences"]),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze-lead")
def analyze_lead(lead: Lead) -> dict[str, object]:
    provider = GroqProvider()
    signals, prompt, response = provider.analyze_lead(lead)
    return {
        "lead_id": lead.id,
        "model": provider.model,
        "signals": signals,
        "prompt": prompt,
        "response": response,
    }


@app.post("/preview", response_model=list[Assignment])
def preview(request: PreviewRequest) -> list[Assignment]:
    users, leads, absences = _load_demo_data()
    if request.lead_ids is not None:
        selected_ids = set(request.lead_ids)
        leads = [lead for lead in leads if lead.id in selected_ids]

    return preview_assignments(
        leads=leads,
        users=users,
        absences=absences,
        current_load=request.current_load,
        execution_date=request.execution_date,
        method=request.method,
        weights=request.weights,
    )


def _select_leads(leads, lead_ids: list[int] | None):
    if lead_ids is None:
        return [lead for lead in leads if lead.estado == "nuevo"]
    selected_ids = set(lead_ids)
    return [
        lead for lead in leads
        if lead.estado == "nuevo" and lead.id in selected_ids
    ]


@app.post("/preview-snowflake", response_model=list[Assignment])
def preview_snowflake(request: PreviewRequest) -> list[Assignment]:
    data = SnowflakeRepository().load_operational_data()
    return preview_assignments(
        leads=_select_leads(data.leads, request.lead_ids),
        users=data.users,
        absences=data.absences,
        current_load=request.current_load or data.current_load,
        execution_date=request.execution_date,
        method=request.method,
        weights=request.weights,
    )


@app.post("/prepare-snowflake")
def prepare_snowflake(request: SnowflakeExecutionRequest) -> dict[str, object]:
    repository = SnowflakeRepository()
    data = repository.load_operational_data()
    selected_leads = _select_leads(data.leads, request.lead_ids)
    ai_signals = {}
    ai_prompts = []
    if request.method == "ai_assisted":
        provider = GroqProvider()
        for lead in selected_leads:
            signals, prompt, response = provider.analyze_lead(lead)
            ai_signals[lead.id] = signals.model_dump()
            ai_prompts.append(
                {
                    "lead_id": lead.id,
                    "model": provider.model,
                    "prompt": prompt,
                    "response": response,
                }
            )
    assignments = preview_assignments(
        leads=selected_leads,
        users=data.users,
        absences=data.absences,
        current_load=request.current_load or data.current_load,
        execution_date=request.execution_date,
        method=request.method,
        weights=request.weights,
        ai_signals=ai_signals,
    )
    run_id = repository.create_run(
        method=request.method,
        parameters={**request.parameters, "weights": request.weights},
        executed_by=request.executed_by,
        execution_date=request.execution_date,
    )
    repository.save_decisions(run_id, assignments)
    repository.save_prompts(run_id, ai_prompts)
    return {
        "run_id": run_id,
        "status": "previewed",
        "decisions": len(assignments),
        "expires_in_hours": 24,
        "assignments": assignments,
    }


@app.post("/approve-snowflake")
def approve_snowflake(request: ApprovalRequest) -> dict[str, object]:
    SnowflakeRepository().approve_run(request.run_id, request.approved_by)
    return {"run_id": request.run_id, "status": "approved"}


@app.post("/execute-snowflake")
def execute_snowflake(request: ExecutionRequest) -> dict[str, object]:
    SnowflakeRepository().mark_run_executed(request.run_id)
    return {"run_id": request.run_id, "status": "executed"}
