from datetime import date, timedelta

from .assignment import preview_assignments
from .models import (
    Absence,
    CurrentAssignment,
    Lead,
    ReassignmentProposal,
    User,
)


def preview_reassignments(
    leads: list[Lead],
    users: list[User],
    absences: list[Absence],
    current_assignments: list[CurrentAssignment],
    current_load: dict[int, int],
    execution_date: date,
    overload_threshold: float = 0.8,
    recent_activity_days: int = 14,
) -> list[ReassignmentProposal]:
    users_by_id = {user.id: user for user in users}
    leads_by_id = {lead.id: lead for lead in leads}
    projected_load = dict(current_load)
    proposals: list[ReassignmentProposal] = []
    cutoff = execution_date - timedelta(days=recent_activity_days)

    overloaded_users = {
        user_id
        for user_id, load in current_load.items()
        if user_id in users_by_id
        and users_by_id[user_id].capacidad_maxima
        and load / users_by_id[user_id].capacidad_maxima >= overload_threshold
    }

    for assignment in current_assignments:
        if assignment.usuario_id not in overloaded_users:
            continue
        lead = leads_by_id.get(assignment.registro_id)
        if lead is None:
            continue
        if assignment.ultima_actividad and assignment.ultima_actividad >= cutoff:
            proposals.append(
                ReassignmentProposal(
                    registro_id=assignment.registro_id,
                    razon_social=assignment.razon_social,
                    current_user_id=assignment.usuario_id,
                    proposed_user_id=None,
                    reasons=["actividad reciente; requiere revisión manual"],
                )
            )
            continue

        candidates = preview_assignments(
            leads=[lead.model_copy(update={"estado": "nuevo"})],
            users=[user for user in users if user.id != assignment.usuario_id],
            absences=absences,
            current_load=projected_load,
            execution_date=execution_date,
            method="weighted_score",
        )
        candidate = candidates[0] if candidates else None
        if candidate and candidate.user_id is not None:
            projected_load[candidate.user_id] = projected_load.get(candidate.user_id, 0) + 1
            proposals.append(
                ReassignmentProposal(
                    registro_id=assignment.registro_id,
                    razon_social=assignment.razon_social,
                    current_user_id=assignment.usuario_id,
                    proposed_user_id=candidate.user_id,
                    reasons=[
                        "vendedor actual sobrecargado",
                        "sin actividad reciente",
                        *candidate.reasons,
                    ],
                )
            )
        else:
            proposals.append(
                ReassignmentProposal(
                    registro_id=assignment.registro_id,
                    razon_social=assignment.razon_social,
                    current_user_id=assignment.usuario_id,
                    proposed_user_id=None,
                    reasons=["vendedor actual sobrecargado; sin reemplazo elegible"],
                )
            )
    return proposals
