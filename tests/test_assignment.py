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


def test_round_robin_has_no_misleading_score():
    assignments = preview_assignments(
        [make_lead()],
        [make_user()],
        [],
        execution_date=date(2026, 9, 17),
        method="round_robin",
    )

    assert assignments[0].score is None


def test_ai_assisted_prioritizes_and_matches_ai_segment_signal():
    assignments = preview_assignments(
        [make_lead(id=1), make_lead(id=2, sector="Retail")],
        [
            make_user(id=1, segmento_experto="Alimentos y bebidas"),
            make_user(id=2, segmento_experto="Retail"),
        ],
        [],
        execution_date=date(2026, 9, 17),
        method="ai_assisted",
        ai_signals={
            1: {"priority": 1, "likely_segment": "Alimentos y bebidas"},
            2: {"priority": 5, "likely_segment": "Retail"},
        },
    )

    assert [assignment.lead_id for assignment in assignments] == [2, 1]
    assert assignments[0].user_id == 2


def test_projected_capacity_is_updated_between_records():
    assignments = preview_assignments(
        [make_lead(id=1), make_lead(id=2)],
        [make_user(id=1, capacidad_maxima=1), make_user(id=2, zona="Costa")],
        [],
        execution_date=date(2026, 9, 17),
        method="balanced",
    )

    assert assignments[0].user_id == 1
    assert assignments[1].user_id == 2


def test_invalid_weights_are_rejected():
    import pytest

    with pytest.raises(ValueError, match="sumar 1.0"):
        preview_assignments(
            [make_lead()],
            [make_user()],
            [],
            method="weighted_score",
            weights={"zone": 1.0, "segment": 1.0, "capacity": 0.0, "balance": 0.0},
        )
