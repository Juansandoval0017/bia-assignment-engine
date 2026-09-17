from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .assignment import preview_assignments
from .data_loader import load_absences, load_leads, load_users
from .models import Assignment
from .snowflake_repository import SnowflakeRepository


class PreviewRequest(BaseModel):
    execution_date: date = Field(default_factory=date.today)
    current_load: dict[int, int] = Field(default_factory=dict)
    lead_ids: list[int] | None = None


class SnowflakeExecutionRequest(PreviewRequest):
    executed_by: str
    method: str = "weighted_score"
    parameters: dict[str, object] = Field(default_factory=dict)


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
    )


@app.post("/execute-snowflake")
def execute_snowflake(request: SnowflakeExecutionRequest) -> dict[str, object]:
    repository = SnowflakeRepository()
    data = repository.load_operational_data()
    assignments = preview_assignments(
        leads=_select_leads(data.leads, request.lead_ids),
        users=data.users,
        absences=data.absences,
        current_load=request.current_load or data.current_load,
        execution_date=request.execution_date,
    )
    run_id = repository.create_run(
        method=request.method,
        parameters=request.parameters,
        executed_by=request.executed_by,
        execution_date=request.execution_date,
        status="previewed",
    )
    repository.save_decisions(run_id, assignments)
    repository.mark_run_executed(run_id)
    return {
        "run_id": run_id,
        "status": "executed",
        "decisions": len(assignments),
    }
