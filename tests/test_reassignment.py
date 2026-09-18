from datetime import date

from app.models import Absence, CurrentAssignment, Lead, User
from app.reassignment import preview_reassignments


def test_reassignment_skips_recent_activity():
    users = [
        User(id=1, nombre="A", rol="vendedor", capacidad_maxima=10, activo=True),
        User(id=2, nombre="B", rol="vendedor", capacidad_maxima=10, activo=True),
    ]
    lead = Lead(
        id=1,
        razon_social="Empresa",
        estado="en_gestion",
        fecha_creacion=date(2026, 1, 1),
    )
    proposals = preview_reassignments(
        [lead],
        users,
        [],
        [
            CurrentAssignment(
                registro_id=1,
                usuario_id=1,
                razon_social="Empresa",
                estado="en_gestion",
                ultima_actividad=date(2026, 9, 16),
            )
        ],
        {1: 9, 2: 1},
        date(2026, 9, 17),
    )

    assert proposals[0].proposed_user_id is None
    assert "actividad reciente" in proposals[0].reasons[0]


def test_reassignment_proposes_available_replacement():
    users = [
        User(id=1, nombre="A", rol="vendedor", zona="Centro", capacidad_maxima=10, activo=True),
        User(id=2, nombre="B", rol="vendedor", zona="Centro", capacidad_maxima=10, activo=True),
    ]
    lead = Lead(
        id=1,
        razon_social="Empresa",
        zona="Centro",
        estado="en_gestion",
        fecha_creacion=date(2026, 1, 1),
    )
    proposals = preview_reassignments(
        [lead],
        users,
        [],
        [
            CurrentAssignment(
                registro_id=1,
                usuario_id=1,
                razon_social="Empresa",
                estado="en_gestion",
                ultima_actividad=None,
            )
        ],
        {1: 9, 2: 1},
        date(2026, 9, 17),
    )

    assert proposals[0].proposed_user_id == 2
