from datetime import date
from unicodedata import normalize

from .models import Absence, Assignment, CandidateScore, Lead, User


def normalize_value(value: str | None) -> str | None:
    if not value:
        return None
    text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.casefold().split())


def _is_absent(user_id: int, when: date, absences: list[Absence]) -> bool:
    return any(
        absence.usuario_id == user_id
        and absence.desde <= when
        and (absence.hasta is None or when <= absence.hasta)
        for absence in absences
    )


def _candidate_score(
    lead: Lead,
    user: User,
    current_load: int,
) -> CandidateScore:
    zone_match = bool(
        normalize_value(lead.zona)
        and normalize_value(lead.zona) == normalize_value(user.zona)
    )
    segment_match = bool(
        normalize_value(lead.sector)
        and normalize_value(lead.sector) == normalize_value(user.segmento_experto)
    )
    capacity_ratio = max(
        0.0,
        (user.capacidad_maxima - current_load) / user.capacidad_maxima,
    )

    score = (
        (0.35 if zone_match else 0.0)
        + (0.25 if segment_match else 0.0)
        + (0.25 * capacity_ratio)
        + (0.15 * (1 - current_load / user.capacidad_maxima))
    )
    reasons = [
        "zona compatible" if zone_match else "zona no compatible o desconocida",
        "segmento experto compatible"
        if segment_match
        else "segmento sin coincidencia exacta",
        f"capacidad disponible: {user.capacidad_maxima - current_load:.0f}",
    ]
    return CandidateScore(user_id=user.id, score=round(score, 4), reasons=reasons)


def preview_assignments(
    leads: list[Lead],
    users: list[User],
    absences: list[Absence],
    current_load: dict[int, int] | None = None,
    execution_date: date | None = None,
) -> list[Assignment]:
    """Previsualiza asignaciones sin escribir en la base de datos."""
    projected_load = dict(current_load or {})
    execution_date = execution_date or date.today()
    assignments: list[Assignment] = []

    for lead in leads:
        if lead.estado != "nuevo":
            continue

        candidates: list[CandidateScore] = []
        for user in users:
            load = projected_load.get(user.id, 0)
            if (
                user.rol.casefold() != "vendedor"
                or not user.activo
                or user.capacidad_maxima is None
                or user.capacidad_maxima <= load
                or _is_absent(user.id, execution_date, absences)
            ):
                continue
            candidates.append(_candidate_score(lead, user, load))

        candidates.sort(key=lambda candidate: (-candidate.score, candidate.user_id))
        if not candidates:
            assignments.append(
                Assignment(
                    lead_id=lead.id,
                    user_id=None,
                    score=None,
                    reasons=["sin vendedores elegibles para la fecha de ejecución"],
                    candidates=[],
                )
            )
            continue

        winner = candidates[0]
        projected_load[winner.user_id] = projected_load.get(winner.user_id, 0) + 1
        assignments.append(
            Assignment(
                lead_id=lead.id,
                user_id=winner.user_id,
                score=winner.score,
                reasons=winner.reasons,
                candidates=candidates,
            )
        )
    return assignments
