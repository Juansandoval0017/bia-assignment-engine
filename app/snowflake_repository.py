import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .models import Absence, Assignment, Lead, User
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
        RETURNING run_id
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
        query = """
        INSERT INTO assignment_decisions
            (run_id, registro_id, usuario_id, score, reasons, candidates)
        SELECT %s, %s, %s, %s, PARSE_JSON(%s), PARSE_JSON(%s)
        """
        with self.client.connect() as connection:
            with connection.cursor() as cursor:
                for assignment in assignments:
                    cursor.execute(
                        query,
                        (
                            run_id,
                            assignment.lead_id,
                            assignment.user_id,
                            assignment.score,
                            json.dumps(assignment.reasons),
                            json.dumps(
                                [candidate.model_dump() for candidate in assignment.candidates]
                            ),
                        ),
                    )
            connection.commit()
