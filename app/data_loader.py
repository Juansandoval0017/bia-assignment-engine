import csv
from datetime import date
from pathlib import Path
from typing import Any

from .models import Absence, Lead, User


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _as_int(value: str | None) -> int | None:
    value = _empty_to_none(value)
    return int(value) if value is not None else None


def _as_float(value: str | None) -> float | None:
    value = _empty_to_none(value)
    return float(value) if value is not None else None


def _as_date(value: str | None) -> date | None:
    value = _empty_to_none(value)
    return date.fromisoformat(value) if value is not None else None


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_users(path: Path) -> list[User]:
    return [
        User(
            id=int(row["id"]),
            nombre=row["nombre"],
            rol=row["rol"],
            equipo_id=_as_int(row["equipo_id"]),
            zona=_empty_to_none(row["zona"]),
            segmento_experto=_empty_to_none(row["segmento_experto"]),
            capacidad_maxima=_as_float(row["capacidad_maxima"]),
            fecha_ingreso=_as_date(row["fecha_ingreso"]),
            activo=row["activo"].strip().lower() == "true",
        )
        for row in _read_csv(path)
    ]


def load_leads(path: Path) -> list[Lead]:
    return [
        Lead(
            id=int(row["id"]),
            razon_social=row["razon_social"],
            sector=_empty_to_none(row["sector"]),
            empleados=_as_float(row["empleados"]),
            ingresos_estimados=_as_float(row["ingresos_estimados"]),
            ciudad=_empty_to_none(row["ciudad"]),
            zona=_empty_to_none(row["zona"]),
            fuente=_empty_to_none(row["fuente"]),
            notas=_empty_to_none(row["notas"]),
            estado=row["estado"].strip().lower(),
            fecha_creacion=_as_date(row["fecha_creacion"]),
        )
        for row in _read_csv(path)
    ]


def load_absences(path: Path) -> list[Absence]:
    return [
        Absence(
            usuario_id=int(row["usuario_id"]),
            desde=_as_date(row["desde"]),
            hasta=_as_date(row["hasta"]),
        )
        for row in _read_csv(path)
    ]
