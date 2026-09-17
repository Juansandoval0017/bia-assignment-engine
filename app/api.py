from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .assignment import preview_assignments
from .data_loader import load_absences, load_leads, load_users
from .models import Assignment


class PreviewRequest(BaseModel):
    execution_date: date = Field(default_factory=date.today)
    current_load: dict[int, int] = Field(default_factory=dict)
    lead_ids: list[int] | None = None


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
