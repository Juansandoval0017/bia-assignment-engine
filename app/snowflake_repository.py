import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .models import (
    Absence,
    Assignment,
    CurrentAssignment,
    Lead,
    LegacyReview,
    User,
)
from .snowflake_client import SnowflakeClient


@dataclass(frozen=True)
class OperationalData:
    users: list[User]
    leads: list[Lead]
    absences: list[Absence]
    current_load: dict[int, int]


USERS_QUERY = """
SELECT id, nombre, rol, equipo_id, zona, segmento_experto,
       capacidad_maxima, fecha_ingreso, activo
FROM usuarios
"""

LEADS_QUERY = """
SELECT id, razon_social, sector, empleados, ingresos_estimados,
       ciudad, zona, fuente, notas, estado, fecha_creacion
FROM registros
"""

ABSENCES_QUERY = """
SELECT usuario_id, desde, hasta
FROM ausencias
"""

LEGACY_ACTIVITY_QUERY = """
SELECT r.id AS registro_id, r.razon_social, r.estado,
       a.usuario_id, a.fecha, a.id AS actividad_id
FROM registros r
LEFT JOIN actividad a ON a.registro_id = r.id
WHERE LOWER(r.estado) IN ('asignado', 'en_gestion')
  AND NOT EXISTS (
      SELECT 1
      FROM assignment_decisions ad
      JOIN assignment_runs ar ON ar.run_id = ad.run_id
      WHERE ad.registro_id = r.id
        AND ar.status = 'executed'
  )
ORDER BY r.id, a.fecha DESC, a.id DESC
"""

TRACE_QUERY = """
SELECT d.registro_id, d.usuario_id, d.score, d.reasons, d.candidates,
       d.created_at AS decision_created_at,
       r.run_id, r.method, r.parameters, r.executed_by,
       r.execution_date, r.status, r.approved_by, r.approved_at,
       p.provider, p.model, p.prompt_text, p.response_text
FROM assignment_decisions d
JOIN assignment_runs r ON r.run_id = d.run_id
LEFT JOIN assignment_prompts p
  ON p.run_id = d.run_id AND p.registro_id = d.registro_id
WHERE d.registro_id = %s
ORDER BY d.created_at DESC, d.decision_id DESC
LIMIT 1
"""

CURRENT_ASSIGNMENTS_QUERY = """
WITH latest_decisions AS (
    SELECT d.registro_id, d.usuario_id,
           ROW_NUMBER() OVER (
               PARTITION BY d.registro_id
               ORDER BY d.created_at DESC, d.decision_id DESC
           ) AS row_number
    FROM assignment_decisions d
    JOIN assignment_runs r ON r.run_id = d.run_id
    WHERE r.status = 'executed' AND d.usuario_id IS NOT NULL
), latest_activity AS (
    SELECT registro_id, MAX(fecha) AS ultima_actividad
    FROM actividad
    GROUP BY registro_id
)
SELECT d.registro_id, d.usuario_id, r.razon_social, r.estado,
       a.ultima_actividad
FROM latest_decisions d
JOIN registros r ON r.id = d.registro_id
LEFT JOIN latest_activity a ON a.registro_id = d.registro_id
WHERE d.row_number = 1
"""

CURRENT_LOAD_QUERY = """
WITH latest_decisions AS (
    SELECT registro_id, usuario_id,
           ROW_NUMBER() OVER (
               PARTITION BY registro_id
               ORDER BY d.created_at DESC, d.decision_id DESC
           ) AS row_number
    FROM assignment_decisions d
    JOIN assignment_runs r ON r.run_id = d.run_id
    WHERE r.status = 'executed'
)
SELECT usuario_id, COUNT(*) AS load
FROM latest_decisions
WHERE row_number = 1 AND usuario_id IS NOT NULL
GROUP BY usuario_id
"""


def _lowercase_row(columns: list[str], values: tuple[Any, ...]) -> dict[str, Any]:
    return dict(zip((column.lower() for column in columns), values))


class SnowflakeRepository:
    def __init__(self, client: SnowflakeClient | None = None):
        self.client = client or SnowflakeClient()

    @staticmethod
    def _fetch(cursor: Any, query: str) -> list[dict[str, Any]]:
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        return [_lowercase_row(columns, row) for row in cursor.fetchall()]

    def load_operational_data(self) -> OperationalData:
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                users = [User.model_validate(row) for row in self._fetch(cursor, USERS_QUERY)]
                leads = [Lead.model_validate(row) for row in self._fetch(cursor, LEADS_QUERY)]
                absences = [
                    Absence.model_validate(row)
                    for row in self._fetch(cursor, ABSENCES_QUERY)
                ]
                load_rows = self._fetch(cursor, CURRENT_LOAD_QUERY)

        current_load = {
            int(row["usuario_id"]): int(row["load"])
            for row in load_rows
        }
        return OperationalData(users, leads, absences, current_load)

    def load_current_assignments(self) -> list[CurrentAssignment]:
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                rows = self._fetch(cursor, CURRENT_ASSIGNMENTS_QUERY)
        return [CurrentAssignment.model_validate(row) for row in rows]

    def load_legacy_review(self) -> list[LegacyReview]:
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                rows = self._fetch(cursor, LEGACY_ACTIVITY_QUERY)

        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            record = grouped.setdefault(
                row["registro_id"],
                {
                    "registro_id": row["registro_id"],
                    "razon_social": row["razon_social"],
                    "estado": row["estado"],
                    "historical_user_ids": set(),
                    "activity_count": 0,
                    "latest_activity": None,
                },
            )
            if row["usuario_id"] is not None:
                record["historical_user_ids"].add(int(row["usuario_id"]))
                record["activity_count"] += 1
                if record["latest_activity"] is None:
                    record["latest_activity"] = row["fecha"]

        reviews = []
        for record in grouped.values():
            user_ids = sorted(record["historical_user_ids"])
            record["historical_user_ids"] = user_ids
            if not user_ids:
                classification = "needs_review"
                reason = "sin actividad con usuario asociado"
                inferred_user_id = None
            elif len(user_ids) == 1:
                classification = "provisional"
                reason = "un solo usuario histórico; requiere confirmación"
                inferred_user_id = user_ids[0]
            else:
                classification = "needs_review"
                reason = "múltiples usuarios históricos"
                inferred_user_id = None

            reviews.append(
                LegacyReview(
                    **record,
                    classification=classification,
                    reason=reason,
                    inferred_user_id=inferred_user_id,
                )
            )
        return reviews

    def load_trace(self, registro_id: int) -> dict[str, Any] | None:
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(TRACE_QUERY, (registro_id,))
                columns = [description[0] for description in cursor.description]
                rows = [
                    _lowercase_row(columns, row)
                    for row in cursor.fetchall()
                ]
        if not rows:
            return None
        trace = rows[0]
        for field in ("reasons", "candidates", "parameters"):
            if isinstance(trace[field], str):
                trace[field] = json.loads(trace[field])
        return trace

    def create_run(
        self,
        method: str,
        parameters: dict[str, Any],
        executed_by: str,
        execution_date: date,
        status: str = "previewed",
        expires_in_hours: int = 24,
    ) -> int:
        query = """
        INSERT INTO assignment_runs
            (method, parameters, executed_by, execution_date, status, expires_at)
        SELECT %s, PARSE_JSON(%s), %s, %s, %s, %s
        """
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        method,
                        json.dumps(parameters),
                        executed_by,
                        execution_date,
                        status,
                        expires_at,
                    ),
                )
                cursor.execute(
                    """
                    SELECT run_id
                    FROM assignment_runs
                    WHERE method = %s
                      AND executed_by = %s
                      AND execution_date = %s
                      AND status = %s
                    ORDER BY created_at DESC, run_id DESC
                    LIMIT 1
                    """,
                    (method, executed_by, execution_date, status),
                )
                run_id = cursor.fetchone()[0]
            connection.commit()
        return int(run_id)

    def approve_run(self, run_id: int, approved_by: str) -> None:
        query = """
        UPDATE assignment_runs
        SET status = 'approved', approved_by = %s, approved_at = CURRENT_TIMESTAMP()
        WHERE run_id = %s
          AND status = 'previewed'
          AND expires_at > CURRENT_TIMESTAMP()
        """
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (approved_by, run_id))
                if cursor.rowcount != 1:
                    raise ValueError("La corrida no existe, expiró o ya fue procesada")
            connection.commit()

    def cancel_run(self, run_id: int) -> None:
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE assignment_runs
                    SET status = 'cancelled'
                    WHERE run_id = %s AND status = 'previewed'
                    """,
                    (run_id,),
                )
                if cursor.rowcount != 1:
                    raise ValueError("La corrida no existe o ya fue procesada")
            connection.commit()

    def expire_runs(self) -> int:
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE assignment_runs
                    SET status = 'expired'
                    WHERE status = 'previewed'
                      AND expires_at <= CURRENT_TIMESTAMP()
                    """
                )
                expired_count = cursor.rowcount
            connection.commit()
        return expired_count

    def mark_run_executed(self, run_id: int) -> None:
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE assignment_runs
                    SET status = 'executed'
                    WHERE run_id = %s AND status = 'approved'
                    """,
                    (run_id,),
                )
                if cursor.rowcount != 1:
                    raise ValueError("La corrida debe estar aprobada antes de ejecutarse")
            connection.commit()

    def save_decisions(self, run_id: int, assignments: list[Assignment]) -> None:
        if not assignments:
            return
        value_placeholders = ", ".join("(%s, %s, %s, %s, %s, %s)" for _ in assignments)
        query = f"""
        INSERT INTO assignment_decisions
            (run_id, registro_id, usuario_id, score, reasons, candidates)
        SELECT column1, column2, column3, column4,
               PARSE_JSON(column5), PARSE_JSON(column6)
        FROM VALUES {value_placeholders}
        """
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                rows = [
                    (
                        run_id,
                        assignment.lead_id,
                        assignment.user_id,
                        assignment.score,
                        json.dumps(assignment.reasons),
                        json.dumps(
                            [candidate.model_dump() for candidate in assignment.candidates]
                        ),
                    )
                    for assignment in assignments
                ]
                parameters = [value for row in rows for value in row]
                cursor.execute(query, parameters)
            connection.commit()

    def save_prompts(self, run_id: int, prompts: list[dict[str, Any]]) -> None:
        if not prompts:
            return
        placeholders = ", ".join("(%s, %s, %s, %s, %s, %s)" for _ in prompts)
        query = f"""
        INSERT INTO assignment_prompts
            (run_id, registro_id, provider, model, prompt_text, response_text)
        SELECT column1, column2, column3, column4, column5, column6
        FROM VALUES {placeholders}
        """
        rows = [
            (
                run_id,
                prompt["lead_id"],
                "groq",
                prompt["model"],
                prompt["prompt"],
                prompt["response"],
            )
            for prompt in prompts
        ]
        parameters = [value for row in rows for value in row]
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
            connection.commit()

    def save_legacy_confirmations(
        self,
        reviews: list[LegacyReview],
        confirmed_ids: list[int],
        executed_by: str,
    ) -> tuple[int, int]:
        selected = [review for review in reviews if review.registro_id in confirmed_ids]
        assignments = [
            Assignment(
                lead_id=review.registro_id,
                user_id=review.inferred_user_id,
                score=None,
                reasons=[
                    "asignación histórica confirmada manualmente",
                    review.reason,
                ],
                candidates=[],
            )
            for review in selected
            if review.inferred_user_id is not None
        ]
        run_id = self.create_run(
            method="legacy_reconciliation",
            parameters={"source": "activity", "confirmed_count": len(assignments)},
            executed_by=executed_by,
            execution_date=date.today(),
            status="executed",
        )
        self.save_decisions(run_id, assignments)
        return run_id, len(assignments)
