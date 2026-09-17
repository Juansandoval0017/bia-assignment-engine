from datetime import date

from app.assignment import normalize_value, preview_assignments
from app.models import Absence, Lead, User


def make_lead(**overrides):
    values = {
        "id": 1,
        "razon_social": "Empresa Demo",
        "sector": "Alimentos y bebidas",
        "zona": "CENTRO ",
        "estado": "nuevo",
        "fecha_creacion": date(2026, 9, 17),
    }
    values.update(overrides)
    return Lead(**values)


def make_user(**overrides):
    values = {
        "id": 1,
        "nombre": "Vendedor Demo",
        "rol": "vendedor",
        "zona": "Centro",
        "segmento_experto": "Alimentos y bebidas",
        "capacidad_maxima": 10,
        "activo": True,
    }
    values.update(overrides)
    return User(**values)


def test_normalize_value_ignores_case_accents_and_spaces():
    assert normalize_value("  Antioquía ") == "antioquia"


def test_assigns_best_matching_available_user():
    assignments = preview_assignments(
        [make_lead()],
        [make_user(), make_user(id=2, zona="Costa")],
        [],
        execution_date=date(2026, 9, 17),
    )

    assert assignments[0].user_id == 1
    assert "zona compatible" in assignments[0].reasons


def test_does_not_assign_user_on_absence():
    assignments = preview_assignments(
        [make_lead()],
        [make_user()],
        [Absence(usuario_id=1, desde=date(2026, 9, 1), hasta=None)],
        execution_date=date(2026, 9, 17),
    )

    assert assignments[0].user_id is None


def test_does_not_assign_user_without_capacity():
    assignments = preview_assignments(
        [make_lead()],
        [make_user()],
        [],
        current_load={1: 10},
        execution_date=date(2026, 9, 17),
    )

    assert assignments[0].user_id is None


def test_balanced_method_prefers_lower_utilization():
    assignments = preview_assignments(
        [make_lead()],
        [make_user(), make_user(id=2, capacidad_maxima=10)],
        [],
        current_load={1: 8, 2: 1},
        execution_date=date(2026, 9, 17),
        method="balanced",
    )

    assert assignments[0].user_id == 2


def test_round_robin_method_distributes_sequentially():
    assignments = preview_assignments(
        [make_lead(id=1), make_lead(id=2)],
        [make_user(id=1), make_user(id=2, zona="Costa")],
        [],
        execution_date=date(2026, 9, 17),
        method="round_robin",
    )

    assert [assignment.user_id for assignment in assignments] == [1, 2]
